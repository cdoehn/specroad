"""Explicit passive mapping behavior and its original-byte/hash/security boundary."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.mappings import ExchangeMapping, MappingError, select_mapping
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from support.artifacts import artifact_bytes
from support.exchange_mappings import mapping_value, fields_value, selected
from support.read_only import no_write_attempts


def test_requirement_fields_are_explicit_and_unused_data_is_preserved():
    mapper = selected(); fields = fields_value(); before = deepcopy(fields)
    result = mapper.artifact("Requirement", fields)
    assert result == {"mapping": mapper.resource.binding(),
        "artifact": {"artifact_type": "requirement", "statement": fields["Text"],
            "language": "en", "normative_force": "shall", "extensions": fields["Extra"]},
        "unmapped": {"Unmapped": fields["Unmapped"]}}
    assert fields == before
    assert set(result) == {"mapping", "artifact", "unmapped"}


@pytest.mark.parametrize("source_format", ["reqif", "reqifz", "csv", "ndjson"])
def test_declared_formats_select_rules_without_parsing_or_converting(source_format):
    mapper = selected(mapping_value(source_format=source_format))
    fields = fields_value(); fields["Text"] = "true,01,null"
    assert mapper.artifact("Requirement", fields)["artifact"]["statement"] == "true,01,null"
    assert mapper.resource.data["source_format"] == source_format


@pytest.mark.parametrize("family,direction,expected", [
    ("relations", "forward", ("first", "second")),
    ("relations", "reverse", ("second", "first")),
    ("hierarchies", "parent_to_child", ("first", "second")),
    ("hierarchies", "child_to_parent", ("second", "first"))])
def test_each_direction_preserves_only_the_explicit_endpoints(family, direction, expected):
    value = mapping_value(); row = value[family][0]; row["direction"] = direction
    mapper = selected(value)
    method = mapper.relation if family == "relations" else mapper.hierarchy
    assert method(row["external_type"], "first", "second") == {
        "mapping": mapper.resource.binding(), "relation_type": row["relation_type"],
        "source": expected[0], "target": expected[1]}


def test_content_version_is_explicit_and_not_a_grammar_version():
    old = ExchangeMapping(artifact_bytes(mapping_value()))
    new = ExchangeMapping(artifact_bytes(mapping_value(mapping_version="42.3.7-rc.2+local")))
    mapper = select_mapping([new, old], key=old.key, expected_sha256=old.sha256)
    assert mapper.resource.source_bytes == old.source_bytes
    assert select_mapping([old, new], key=new.key, expected_sha256=new.sha256).resource.key == new.key
    with pytest.raises(MappingError) as failure:
        select_mapping([old], key=new.key, expected_sha256=new.sha256)
    assert failure.value.reason == "mapping_resource_missing"


@pytest.mark.parametrize("mutation", ["identical", "changed"])
def test_duplicate_resource_key_is_ambiguous_even_with_expected_hash(mutation):
    old = ExchangeMapping(artifact_bytes(mapping_value()))
    value = mapping_value()
    if mutation == "changed": value["extensions"]["example.other"] = True
    other = ExchangeMapping(artifact_bytes(value))
    with pytest.raises(MappingError) as failure:
        select_mapping([old, other], key=old.key, expected_sha256=old.sha256)
    assert failure.value.reason == "mapping_duplicate_resource"


def test_wrong_expected_hash_never_selects_a_resource():
    resource = selected().resource
    with pytest.raises(MappingError) as failure:
        select_mapping([resource], key=resource.key, expected_sha256="0" * 64)
    assert failure.value.reason == "mapping_hash_mismatch"
    assert failure.value.path == resource.key


def test_original_and_canonical_identity_are_separate_and_results_are_owned():
    value = mapping_value()
    a = ExchangeMapping(artifact_bytes(value)); b = ExchangeMapping(canonical_json_bytes(value))
    assert a.sha256 == b.sha256 == canonical_json_sha256(value)
    assert a.source_sha256 == sha256(a.source_bytes).hexdigest() != b.source_sha256
    data = a.data; data["fields"].clear()
    binding = a.binding(); binding["sha256"] = "0" * 64
    with pytest.raises(FrozenInstanceError): a.source_bytes = b"{}"
    mapper = select_mapping([a], key=a.key, expected_sha256=a.sha256)
    fields = fields_value(); result = mapper.artifact("Requirement", fields)
    original = deepcopy(result)
    result["artifact"]["extensions"]["example.metadata"]["values"].clear()
    result["unmapped"]["Unmapped"]["original"].clear()
    assert mapper.artifact("Requirement", fields) == original
    assert a.data == value and fields == fields_value()


@pytest.mark.parametrize("field_value", [None, "", {"nested": [None, True]}])
def test_null_empty_and_structured_copy_values_are_present(field_value):
    mapper = selected(); fields = fields_value(); fields["Text"] = field_value
    assert mapper.artifact("Requirement", fields)["artifact"]["statement"] == field_value


def test_missing_field_and_unmapped_value_fail_without_partial_output():
    mapper = selected(); fields = fields_value(); del fields["Text"]
    with pytest.raises(MappingError) as missing: mapper.artifact("Requirement", fields)
    assert missing.value.reason == "mapping_source_field_missing"
    assert missing.value.pointer == "/fields/0"
    fields = fields_value(); fields["Force"] = "private external payload"
    with pytest.raises(MappingError) as unmapped: mapper.artifact("Requirement", fields)
    diagnostic = unmapped.value.diagnostic()
    assert diagnostic["reason"] == "mapping_value_unmapped"
    assert diagnostic["code"] == "SRV090" and diagnostic["exit_code"] == 3
    assert diagnostic["pointer"] == "/fields/2/value_map"
    assert "private external payload" not in json.dumps(diagnostic)


@pytest.mark.parametrize("external,target", [(True, "boolean"), (1, "number"), (1.0, "number"), ("1", "text")])
def test_value_tables_use_typed_canonical_keys(external, target):
    value = mapping_value()
    value["fields"][2]["value_map"] = [
        {"external_value": True, "target_value": "boolean"},
        {"external_value": 1, "target_value": "number"},
        {"external_value": "1", "target_value": "text"}]
    fields = fields_value(); fields["Force"] = external
    assert selected(value).artifact("Requirement", fields)["artifact"]["normative_force"] == target


def test_status_and_unit_names_are_only_explicit_value_tables():
    value = mapping_value(fields=[
        {"external_type": "Requirement", "external_field": "Status", "target_field": "maturity",
         "value_map": [{"external_value": "reviewed elsewhere", "target_value": "draft"}]},
        {"external_type": "Requirement", "external_field": "Unit", "target_field": "example.unit",
         "value_map": [{"external_value": "milliseconds", "target_value": "ms"}]}])
    result = selected(value).artifact("Requirement", {"Status": "reviewed elsewhere", "Unit": "milliseconds", "Magnitude": 1000})
    assert result["artifact"] == {"artifact_type": "requirement", "maturity": "draft", "example.unit": "ms"}
    assert result["unmapped"] == {"Magnitude": 1000}


def test_literal_member_names_and_unicode_external_names_are_not_paths_or_patterns():
    value = mapping_value(types=[{"external_type": " É/* ", "artifact_type": "requirement"}],
        fields=[{"external_type": " É/* ", "external_field": "a/b", "target_field": "x/y.z", "value_map": None}])
    mapper = selected(value)
    assert mapper.artifact(" É/* ", {"a/b": 3})["artifact"] == {"artifact_type": "requirement", "x/y.z": 3}
    for other in ("É/*", " é/* ", " E\u0301/* "):
        with pytest.raises(MappingError) as failure: mapper.artifact(other, {"a/b": 3})
        assert failure.value.reason == "mapping_type_unmapped"


@pytest.mark.parametrize("family", ["types", "fields", "relations", "hierarchies"])
def test_duplicate_rows_never_use_first_or_last_match(family):
    value = mapping_value(); value[family].append(deepcopy(value[family][0]))
    with pytest.raises(MappingError) as failure: ExchangeMapping(artifact_bytes(value))
    assert failure.value.reason == "mapping_duplicate_key"
    assert failure.value.pointer.startswith("/" + family + "/")


def test_competing_target_and_reserved_type_target_are_rejected():
    value = mapping_value(); value["fields"][1]["target_field"] = "statement"
    with pytest.raises(MappingError) as failure: ExchangeMapping(artifact_bytes(value))
    assert failure.value.reason == "mapping_duplicate_key"
    value["fields"][1]["target_field"] = "artifact_type"
    with pytest.raises(MappingError) as failure: ExchangeMapping(artifact_bytes(value))
    assert failure.value.reason == "mapping_reserved_target"


def test_numeric_aliases_cannot_make_two_value_keys():
    value = mapping_value(); value["fields"][2]["value_map"] = [
        {"external_value": 1, "target_value": "a"}, {"external_value": 1.0, "target_value": "b"}]
    with pytest.raises(MappingError) as failure: ExchangeMapping(artifact_bytes(value))
    assert failure.value.reason == "mapping_duplicate_key"


@pytest.mark.parametrize("mutation", ["grammar", "schema", "version", "field_type", "native_type", "relation_type", "direction", "executable"])
def test_invalid_or_executable_declarations_are_not_rules(mutation):
    value = mapping_value()
    if mutation == "grammar": value["mapping_format_version"] = "exchange-mapping-v2"
    elif mutation == "schema": value["schema_version"] = "0.3.0"
    elif mutation == "version": value["mapping_version"] = "latest"
    elif mutation == "field_type": value["fields"][0]["external_type"] = "Other"
    elif mutation == "native_type": value["types"][0]["artifact_type"] = "registry"
    elif mutation == "relation_type": value["relations"][0]["relation_type"] = "inverse_contains"
    elif mutation == "direction": value["hierarchies"][0]["direction"] = "guess"
    else: value["script"] = "import os"
    with pytest.raises(MappingError) as failure: ExchangeMapping(artifact_bytes(value))
    assert failure.value.code == "SRV090" and failure.value.exit_code == 3
    assert failure.value.pointer and failure.value.path.startswith("sha256:")


def test_strict_reader_rejects_duplicate_json_keys_without_source_disclosure():
    raw = artifact_bytes(mapping_value()).replace(b'"source_format": "reqif"', b'"source_format":"private", "source_format":"reqif"')
    with pytest.raises(MappingError) as failure: ExchangeMapping(raw)
    assert failure.value.reason == "duplicate_key" and failure.value.pointer == "/source_format"
    assert "private" not in json.dumps(failure.value.diagnostic())


def test_empty_tables_mean_no_mapping_and_missing_table_has_no_default():
    value = mapping_value(types=[], fields=[], relations=[], hierarchies=[])
    mapper = selected(value)
    with pytest.raises(MappingError): mapper.artifact("Requirement", {})
    del value["fields"]
    with pytest.raises(MappingError) as failure: ExchangeMapping(artifact_bytes(value))
    assert failure.value.reason == "mapping_missing_field"


def test_row_order_is_not_priority_but_remains_in_resource_hash():
    value = mapping_value(); other = deepcopy(value); other["fields"].reverse()
    a = selected(value); b = selected(other)
    assert a.resource.sha256 != b.resource.sha256
    assert a.artifact("Requirement", fields_value())["artifact"] == b.artifact("Requirement", fields_value())["artifact"]


def test_passive_text_is_not_executed_or_resolved():
    fields = fields_value(); fields["Text"] = "__import__('os').system('never run')"
    fields["Unmapped"] = {"template": "${ENV}", "url": "https://unused.invalid", "path": "../../private"}
    with no_write_attempts():
        mapper = selected()
        result = mapper.artifact("Requirement", fields)
    assert result["artifact"]["statement"] == fields["Text"]
    assert result["unmapped"] == {"Unmapped": fields["Unmapped"]}
