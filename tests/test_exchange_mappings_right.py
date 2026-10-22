"""Strict resource and projection boundaries beyond the usable W slice."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from specroad.mappings import ExchangeMapping, ExternalIdentityRegistry, MappingError, select_mapping
from specroad.model.canonical import canonical_json_bytes
from support.artifacts import artifact_bytes
from support.exchange_mappings import fields_value, mapping_value, registry_value, selected
from support.read_only import inventory, no_write_attempts


@pytest.mark.parametrize("field,bad", [
    ("mapping_id", "1invalid"), ("mapping_id", "a" * 129), ("mapping_id", "a/b"),
    ("mapping_version", "v1.0.0"), ("mapping_version", "1.0"),
    ("mapping_version", "01.0.0"), ("mapping_version", "1.0.0-01"),
    ("mapping_version", ">=1.0.0"), ("mapping_version", "1.0.0 "),
    ("mapping_version", None), ("mapping_id", True)])
def test_resource_identity_is_an_exact_key_not_a_version_query(field, bad):
    value = mapping_value(**{field: bad})
    with pytest.raises(MappingError) as caught:
        ExchangeMapping(artifact_bytes(value))
    assert caught.value.reason == "mapping_exact_identity_required"
    assert caught.value.pointer == "/" + field


@pytest.mark.parametrize("key", [None, "example:requirements", "example:requirements@latest",
    "example:requirements@1.0.0@other", "Example:requirements@1.0.0", "example:requirements@1.0.1"])
def test_selection_never_falls_back_from_a_missing_or_inexact_key(key):
    resource = selected().resource
    with pytest.raises(MappingError):
        select_mapping([resource], key=key, expected_sha256=resource.sha256)


@pytest.mark.parametrize("bad", [None, True, "ABCDEF" * 10 + "ABCD", "0" * 63, "sha256:" + "0" * 64])
def test_selection_requires_the_full_lowercase_canonical_digest(bad):
    resource = selected().resource
    with pytest.raises(MappingError) as caught:
        select_mapping([resource], key=resource.key, expected_sha256=bad)
    assert caught.value.reason == "mapping_sha256_required"


def test_valid_new_versions_are_independent_of_input_order_and_formatting():
    older = selected().resource
    value = mapping_value(mapping_version="2.0.0-rc.10+build.02", mapping_id="A" + "x" * 127)
    newer = ExchangeMapping(artifact_bytes(value))
    formatted = ExchangeMapping(json.dumps(value, indent=1, sort_keys=True).encode())
    assert newer.sha256 == formatted.sha256 and newer.source_sha256 != formatted.source_sha256
    expected = select_mapping([newer], key=newer.key, expected_sha256=newer.sha256).artifact("Requirement", fields_value())
    for resources in ([newer, older], (older, formatted)):
        mapper = select_mapping(resources, key=newer.key, expected_sha256=newer.sha256)
        assert mapper.artifact("Requirement", fields_value()) == expected
    with pytest.raises(MappingError) as caught:
        select_mapping([newer], key=newer.key, expected_sha256=newer.source_sha256)
    assert caught.value.reason == "mapping_hash_mismatch"


@pytest.mark.parametrize("location", ["root", "type", "field", "value", "relation", "hierarchy"])
@pytest.mark.parametrize("mutation", ["missing", "control", "nonobject"])
def test_closed_declarations_neither_default_missing_data_nor_execute_unknown_controls(location, mutation):
    value = mapping_value()
    containers = {"root": (None, None, "source_format"), "type": (value["types"], 0, "artifact_type"),
        "field": (value["fields"], 0, "target_field"),
        "value": (value["fields"][2]["value_map"], 0, "target_value"),
        "relation": (value["relations"], 0, "direction"),
        "hierarchy": (value["hierarchies"], 0, "direction")}
    parent, index, required = containers[location]
    node = value if parent is None else parent[index]
    if mutation == "missing":
        del node[required]
    elif mutation == "control":
        node["converter/path~"] = "__import__('os').system('not executed')"
    elif parent is None:
        value = []
    else:
        parent[index] = []
    with no_write_attempts(), pytest.raises(MappingError) as caught:
        ExchangeMapping(artifact_bytes(value))
    if mutation == "missing":
        assert caught.value.reason == "mapping_missing_field"
    elif mutation == "control":
        assert caught.value.reason == "mapping_unknown_field"
        assert caught.value.pointer.endswith("/converter~1path~0")
    assert "not executed" not in json.dumps(caught.value.diagnostic())


@pytest.mark.parametrize("family", ["types", "fields", "relations", "hierarchies"])
def test_rule_collections_are_arrays_and_never_implicit_objects(family):
    with pytest.raises(MappingError) as caught:
        ExchangeMapping(artifact_bytes(mapping_value(**{family: {}})))
    assert caught.value.reason == "mapping_array_required"
    assert caught.value.pointer == "/" + family


@pytest.mark.parametrize("table,reason", [([], "mapping_empty_value_table"), ({}, "mapping_array_required")])
def test_empty_or_illtyped_value_tables_are_not_copy_rules(table, reason):
    value = mapping_value()
    value["fields"][0]["value_map"] = table
    with pytest.raises(MappingError) as caught:
        ExchangeMapping(artifact_bytes(value))
    assert caught.value.reason == reason and caught.value.pointer == "/fields/0/value_map"


@pytest.mark.parametrize("left,right", [(0, -0.0), ({"a": 1, "b": None}, {"b": None, "a": 1.0}),
    ([1, {"nested": True}], [1.0, {"nested": True}])])
def test_structured_and_numeric_canonical_aliases_are_ambiguous(left, right):
    value = mapping_value()
    value["fields"][2]["value_map"] = [
        {"external_value": left, "target_value": "a"}, {"external_value": right, "target_value": "b"}]
    with pytest.raises(MappingError) as caught:
        ExchangeMapping(artifact_bytes(value))
    assert caught.value.reason == "mapping_duplicate_key"
    assert caught.value.pointer == "/fields/2/value_map/1"


@pytest.mark.parametrize("source", [None, "", False, 0, "0", [1, 2], [2, 1], {"b": None, "a": 1}])
def test_empty_null_boolean_numeric_and_structured_table_values_remain_distinct(source):
    values = [None, "", False, 0, "0", [1, 2], [2, 1], {"a": 1, "b": None}]
    table = [{"external_value": item, "target_value": {"result": [i]}} for i, item in enumerate(values)]
    value = mapping_value(fields=[{"external_type": "Requirement", "external_field": "value",
        "target_field": "result", "value_map": table}])
    mapper = selected(value)
    index = next(i for i, item in enumerate(values) if canonical_json_bytes(item) == canonical_json_bytes(source))
    first = mapper.artifact("Requirement", {"value": source})
    assert first["artifact"]["result"] == {"result": [index]}
    first["artifact"]["result"]["result"].clear()
    assert mapper.artifact("Requirement", {"value": source})["artifact"]["result"] == {"result": [index]}
    with pytest.raises(MappingError) as caught:
        mapper.artifact("Requirement", {})
    assert caught.value.reason == "mapping_source_field_missing"


def test_field_uniqueness_is_per_external_type_but_not_per_target():
    value = mapping_value(types=[{"external_type": name, "artifact_type": "requirement"}
                                for name in ("Requirement", "Other")], fields=[
        {"external_type": name, "external_field": "text", "target_field": "statement", "value_map": None}
        for name in ("Requirement", "Other")])
    mapper = selected(value)
    assert mapper.artifact("Requirement", {"text": 1})["artifact"]["statement"] == 1
    assert mapper.artifact("Other", {"text": 2})["artifact"]["statement"] == 2
    value["fields"].append({**value["fields"][0], "target_field": "different"})
    with pytest.raises(MappingError) as caught:
        ExchangeMapping(artifact_bytes(value))
    assert caught.value.reason == "mapping_duplicate_key"
    assert caught.value.pointer == "/fields/2/external_field"


@pytest.mark.parametrize("method,external_type", [("relation", "Derivation"), ("hierarchy", "DocumentTree")])
@pytest.mark.parametrize("endpoint", [None, "", 1, "\ud800"])
def test_edges_require_two_literal_scalar_unicode_endpoints(method, external_type, endpoint):
    mapper = selected()
    with pytest.raises(MappingError) as caught:
        getattr(mapper, method)(external_type, "supplied", endpoint)
    assert caught.value.pointer == "/endpoints/1"
    json.dumps(caught.value.diagnostic(), ensure_ascii=False).encode("utf-8")


def test_pure_edge_projection_does_not_invent_ids_or_apply_graph_validation():
    mapper = selected()
    for method, name in ((mapper.relation, "Derivation"), (mapper.hierarchy, "DocumentTree")):
        result = method(name, "same-external-id", "same-external-id")
        assert result["source"] == result["target"] == "same-external-id"
        with pytest.raises(MappingError) as caught:
            method(name.lower(), "a", "b")
        assert caught.value.reason == "mapping_type_unmapped"


@pytest.mark.parametrize("fields", [None, [], {1: "bad-key"}, {"Text": "\ud800"}, {"Text": float("inf")}])
def test_bad_projected_values_fail_with_the_mapping_error_contract(fields):
    with pytest.raises(MappingError) as caught:
        selected().artifact("Requirement", fields)
    assert caught.value.path == "example:requirements@1.0.0"
    assert caught.value.code == "SRV090" and caught.value.exit_code == 3
    json.dumps(caught.value.diagnostic(), ensure_ascii=False).encode("utf-8")


@pytest.mark.parametrize("family", ["mapping", "registry"])
@pytest.mark.parametrize("fault", ["utf8", "duplicate", "trailing", "surrogate", "precision", "nonfinite"])
def test_resource_bytes_use_strict_json_and_byte_identified_diagnostics(family, fault):
    value = mapping_value() if family == "mapping" else registry_value(selected().resource)
    raw = artifact_bytes(value)
    if fault == "utf8":
        raw = b"\xff" + raw
    elif fault == "duplicate":
        raw = raw.replace(b'"schema_version": "0.2.0"', b'"schema_version":"secret-value", "schema_version":"0.2.0"')
    elif fault == "trailing":
        raw += b" {}"
    else:
        token = {"surrogate": b'"\\ud800"', "precision": b'9007199254740993', "nonfinite": b'NaN'}[fault]
        raw = raw[:-1] + b', "extra":' + token + b'}'
    resource_type = ExchangeMapping if family == "mapping" else ExternalIdentityRegistry
    with pytest.raises(MappingError) as caught:
        resource_type(raw)
    diagnostic = caught.value.diagnostic()
    assert diagnostic["code"] == "SRV090" and diagnostic["exit_code"] == 3
    assert diagnostic["path"] == "sha256:" + sha256(raw).hexdigest()
    assert diagnostic["reason"] not in ("mapping_unknown_field", "mapping_missing_field")
    assert "secret-value" not in json.dumps(diagnostic)
    if fault == "duplicate":
        assert diagnostic["reason"] == "duplicate_key" and diagnostic["pointer"] == "/schema_version"


def test_collection_types_are_rejected_without_running_user_iterators_or_properties():
    class DangerousSequence:
        def __iter__(self):
            raise AssertionError("must not iterate")
    class DangerousMapping(ExchangeMapping):
        @property
        def source_bytes(self):
            raise AssertionError("must not read")
    resource = selected().resource
    for collection in (DangerousSequence(), {resource.key: resource}, [object.__new__(DangerousMapping)]):
        with pytest.raises(MappingError):
            select_mapping(collection, key=resource.key, expected_sha256=resource.sha256)


def test_duplicate_unselected_resources_cannot_hide_ambiguous_collections():
    resource = selected().resource
    other = ExchangeMapping(artifact_bytes(mapping_value(mapping_version="2.0.0")))
    with pytest.raises(MappingError) as caught:
        select_mapping([other, resource, other], key=resource.key, expected_sha256=resource.sha256)
    assert caught.value.reason == "mapping_duplicate_resource"


def test_selection_owns_bytes_even_when_originals_and_exposed_resources_are_reinitialized():
    original = selected().resource
    mapper = select_mapping([original], key=original.key, expected_sha256=original.sha256)
    expected = mapper.artifact("Requirement", fields_value())
    changed = mapping_value()
    changed["fields"][0]["target_field"] = "changed"
    replacement = artifact_bytes(changed)
    original.__init__(replacement)
    mapper.resource.__init__(replacement)
    mapper.resource.data["fields"].clear()
    mapper.resource.binding()["sha256"] = "0" * 64
    assert mapper.artifact("Requirement", fields_value()) == expected
    assert mapper.resource.sha256 == expected["mapping"]["sha256"] != original.sha256


def test_selection_reconstructs_identity_and_hash_from_bytes_not_cached_claims():
    old = selected().resource
    changed = ExchangeMapping(artifact_bytes(mapping_value(mapping_version="2.0.0")))
    object.__setattr__(changed, "sha256", old.sha256)
    object.__setattr__(changed, "mapping_version", old.mapping_version)
    with pytest.raises(MappingError) as caught:
        select_mapping([changed], key=old.key, expected_sha256=old.sha256)
    assert caught.value.reason == "mapping_resource_missing"


def test_success_and_late_failure_preserve_project_bytes_modes_and_source_values(tmp_path, monkeypatch):
    mapper = selected()
    resource_path = tmp_path / "rules.json"
    resource_path.write_bytes(mapper.resource.source_bytes)
    resource_path.chmod(0o444)
    before = inventory(tmp_path)
    fields = fields_value()
    fields["Unmapped"] = {"url": "file:///never-read", "converter": "__import__('os')", "path": "../../private"}
    saved = deepcopy(fields)
    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected external input")
    with no_write_attempts(), monkeypatch.context() as patch:
        for name in ("builtins.open", "io.open", "os.open", "time.time", "socket.getaddrinfo", "secrets.token_bytes"):
            patch.setattr(name, forbidden)
        result = mapper.artifact("Requirement", fields)
        bad = deepcopy(fields)
        bad["Force"] = "sensitive-unmapped-source"
        with pytest.raises(MappingError) as caught:
            mapper.artifact("Requirement", bad)
    assert fields == saved and result["unmapped"] == {"Unmapped": fields["Unmapped"]}
    assert bad["Force"] == "sensitive-unmapped-source"
    assert "sensitive-unmapped-source" not in json.dumps(caught.value.diagnostic())
    assert inventory(tmp_path) == before
