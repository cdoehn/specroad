"""14.f.W: bound CSV values and lossless explicit dataset roundtrips."""
from copy import deepcopy
from hashlib import sha256

import pytest

from specroad.exchange import select_csv_profile
from specroad.mappings import CSVError, CSVProfile, ExchangeMapping, select_mapping
from support.artifacts import artifact_bytes
from support.csv_codec import column, record, resources, selected
from support.exchange_mappings import registry
from support.read_only import no_write_attempts


def test_roundtrip_retains_identity_order_types_and_distinct_field_presence():
    codec = selected()
    common = {"Text": ' Unicode ä e\u0301, "quoted" \r\nCR\rLF\n ', "Flag": False,
              "Count": -7, "Measure": 1.25, "Items": ["", "x,y", "a;b|c", "x,y", None, {"a": [True, 2]}]}
    rows = [record({**common}, identity="absent"), record({**common, "State": None}, identity="null"),
            record({**common, "State": ""}, identity="empty"), record({**common, "State": "null"}, identity="text"),
            record({**common, "State": {"nested": [[], {}, False, 0, None]}}, identity="object")]
    before = deepcopy(rows)
    with no_write_attempts():
        raw = codec.encode(rows)
        observed = codec.decode(raw)
    assert observed.records == before == rows
    assert type(observed.records[0]["fields"]["Flag"]) is bool
    assert type(observed.records[0]["fields"]["Count"]) is int
    assert type(observed.records[0]["fields"]["Measure"]) is float
    assert "State" not in observed.records[0]["fields"]
    assert raw.startswith(b"ID,Text,Flag,Count,Measure,Items,State\r\n") and raw.endswith(b"\r\n")
    assert observed.source_bytes == raw
    facts = observed.observation()
    assert facts["source_sha256"] == sha256(raw).hexdigest() and facts["record_count"] == 5
    for name in ("profile", "mapping"):
        resource = getattr(codec, name)
        assert facts[name] == {**resource.binding(), "source_sha256": sha256(resource.source_bytes).hexdigest()}
    detached = observed.records
    detached[0]["fields"]["Items"][5]["a"].append("mutation")
    facts["profile"]["sha256"] = "0" * 64
    assert observed.records == before and observed.observation()["profile"]["sha256"] == codec.profile.sha256


def test_known_rfc_input_preserves_embedded_line_endings_quotes_and_literal_strings():
    codec = selected([column("Text")])
    raw = 'ID,Text\r\nexternal-1," α, ""β""\r\none\rtwo\nthree "\r\nexternal-2,=1+1'.encode()
    expected = [record({"Text": ' α, "β"\r\none\rtwo\nthree '}),
                record({"Text": "=1+1"}, identity="external-2")]
    observed = codec.decode(raw)
    assert observed.records == expected
    assert codec.encode(expected) == raw + b"\r\n"


@pytest.mark.parametrize("value", [None, False, True, 0, 1.25, "", "null", [], ["", None, {}], {"a": "\x00\t"}])
def test_typed_json_cells_keep_json_types_and_escaped_controls(value):
    codec = selected([column("Value", "typed-json-v1")])
    assert codec.decode(codec.encode([record({"Value": value})])).records == [record({"Value": value})]


@pytest.mark.parametrize("value", [[], ["one;two", "x|y", "x,y", "a\nb"], [None, [], {"x": [True, 1, "1"]}]])
def test_declared_json_array_rule_keeps_empty_nested_and_separator_values(value):
    codec = selected([column("Values", "list")])
    assert codec.decode(codec.encode([record({"Values": value})])).records == [record({"Values": value})]


def test_text_that_looks_like_json_is_not_inferred_and_nullable_empty_is_explicit():
    codec = selected([column("Literal"), column("Nullable", empty="null")])
    result = codec.decode(b'ID,Literal,Nullable\r\nx,"[1,true]",\r\ny,null,null\r\n')
    assert result.records == [record({"Literal": "[1,true]", "Nullable": None}, identity="x"),
                              record({"Literal": "null", "Nullable": "null"}, identity="y")]
    assert codec.decode(codec.encode(result.records)).records == result.records


@pytest.mark.parametrize("identity", ["SR-REQ-0001", "SR-REQ-00000000000000000000000001"])
def test_native_id_and_shared_identity_column_are_retained_without_allocation(identity):
    codec = selected([column("ID"), column("Text")], identity_kind="native_id")
    rows = [record({"ID": identity, "Text": "Exact"}, identity=identity, kind="native_id")]
    raw = codec.encode(rows)
    assert raw.split(b"\r\n", 1)[0] == b"ID,Text"
    assert codec.decode(raw).records == rows


@pytest.mark.parametrize("identity", ["", "../SR-REQ-0001", "SR-RSK-0001", "SR-REQ-8" + "0" * 25])
def test_native_identity_validation_rejects_wrong_kind_or_unrepresentable_id(identity):
    codec = selected([column("Text")], identity_kind="native_id")
    with pytest.raises(CSVError):
        codec.encode([record({"Text": "kept"}, identity=identity, kind="native_id")])


@pytest.mark.parametrize("rule,value", [
    (column("V", "integer"), False), (column("V", "boolean"), 0),
    (column("V", "number"), "1.5"), (column("V", "list"), "a;b"),
    (column("V"), None), (column("V", empty="null"), ""),
    (column("V", empty="error"), ""), (column("V", "integer"), 9007199254740993),
    (column("V", "number"), float("nan")), (column("V", "number"), float("inf")),
])
def test_export_rejects_values_that_cannot_reproduce_their_type_and_value(rule, value):
    codec = selected([rule])
    rows = [record({"V": value})]
    with no_write_attempts(), pytest.raises(CSVError) as caught:
        codec.encode(rows)
    assert caught.value.code == "SRV090" and caught.value.exit_code == 3
    assert caught.value.diagnostic()["record"] == 2


@pytest.mark.parametrize("defect", ["missing", "unknown", "identity", "type", "shared-id"])
def test_export_does_not_drop_missing_fields_unknown_fields_or_record_bindings(defect):
    codec = selected([column("ID"), column("Text")])
    rows = [record({"ID": "external-1", "Text": "kept"})]
    if defect == "missing": del rows[0]["fields"]["Text"]
    if defect == "unknown": rows[0]["fields"]["extra"] = "secret"
    if defect == "identity": del rows[0]["identity"]
    if defect == "type": rows[0]["external_type"] = "Other"
    if defect == "shared-id": rows[0]["fields"]["ID"] = "different"
    before = deepcopy(rows)
    with no_write_attempts(), pytest.raises(CSVError):
        codec.encode(rows)
    assert rows == before


def test_conversion_precedes_existing_mapping_and_does_not_execute_value_map():
    profile, mapping = resources([column("Flag", "boolean")])
    rules = mapping.data
    rules["fields"][0].update(target_field="statement", value_map=[{"external_value": False, "target_value": "mapped"}])
    mapping = ExchangeMapping(artifact_bytes(rules))
    declaration = profile.data
    declaration["mapping"] = mapping.binding()
    profile = CSVProfile(artifact_bytes(declaration))
    codec = select_csv_profile([profile, mapping], key=profile.key, expected_sha256=profile.sha256)
    fields = codec.decode(b"ID,Flag\r\nx,false\r\n").records[0]["fields"]
    assert fields == {"Flag": False} and type(fields["Flag"]) is bool
    native = select_mapping([mapping], key=mapping.key, expected_sha256=mapping.sha256)
    assert native.artifact("Requirement", fields)["artifact"]["statement"] == "mapped"


@pytest.mark.parametrize("defect", ["profile-missing", "mapping-missing", "profile-hash", "mapping-hash",
                                    "profile-version", "duplicate-profile", "duplicate-mapping", "registry-collision",
                                    "source-format", "type", "field-set"])
def test_selection_requires_actual_unique_exact_bound_resources(defect):
    profile, mapping = resources([column("Text")])
    supplied, key, expected = [profile, mapping], profile.key, profile.sha256
    if defect == "profile-missing": supplied = [mapping]
    if defect == "mapping-missing": supplied = [profile]
    if defect == "profile-hash": expected = "0" * 64
    if defect == "profile-version": key = "example:csv@1.0.1"
    if defect == "duplicate-profile": supplied.append(profile)
    if defect == "duplicate-mapping": supplied.append(mapping)
    if defect == "registry-collision": supplied.append(registry(mapping, mapping_id=profile.mapping_id))
    if defect in ("mapping-hash", "source-format", "type", "field-set"):
        declaration = profile.data
        if defect == "mapping-hash": declaration["mapping"]["sha256"] = "0" * 64
        if defect == "source-format":
            value = mapping.data; value["source_format"] = "reqif"
            mapping = ExchangeMapping(artifact_bytes(value)); declaration["mapping"] = mapping.binding()
        if defect == "type": declaration["external_type"] = "Unknown"
        if defect == "field-set": declaration["columns"][0]["external_field"] = "Other"
        profile = CSVProfile(artifact_bytes(declaration)); supplied = [profile, mapping]; expected = profile.sha256
    with no_write_attempts(), pytest.raises(CSVError):
        select_csv_profile(supplied, key=key, expected_sha256=expected)


@pytest.mark.parametrize("defect", ["version", "schema", "unknown", "implicit-error", "skip", "identity-kind",
    "empty-name", "duplicate-column", "duplicate-field", "unknown-codec", "codec-extra", "list-rule",
    "typed-null", "shared-identity", "key-collision", "unversioned", "empty-policy", "missing-policy"])
def test_profile_is_closed_explicit_passive_and_unambiguous(defect):
    profile, _ = resources([column("Text"), column("Items", "list")])
    value = profile.data
    if defect == "version": value["mapping_format_version"] = "csv-profile-v2"
    if defect == "schema": value["schema_version"] = "9.0.0"
    if defect == "unknown": value["infer"] = True
    if defect == "implicit-error": del value["error_policy"]
    if defect == "skip": value["error_policy"] = "skip"
    if defect == "identity-kind": value["identity"]["kind"] = "row-number"
    if defect == "empty-name": value["columns"][0]["column"] = ""
    if defect == "duplicate-column": value["columns"][1]["column"] = "Text"
    if defect == "duplicate-field": value["columns"][1]["external_field"] = "Text"
    if defect == "unknown-codec": value["columns"][0]["codec"] = {"kind": "infer"}
    if defect == "codec-extra": value["columns"][0]["codec"]["execute"] = "anything"
    if defect == "list-rule": value["columns"][1]["codec"]["list_rule"] = "split-semicolon"
    if defect == "typed-null": value["columns"][0].update(codec={"kind": "typed-json-v1"}, empty_cell="null")
    if defect == "shared-identity": value["identity"]["column"] = "Items"
    if defect == "key-collision": value["mapping_id"] = value["mapping"]["mapping_id"]
    if defect == "unversioned": value["mapping_version"] = "latest"
    if defect == "empty-policy": del value["columns"][0]["empty_cell"]
    if defect == "missing-policy": del value["columns"][0]["missing_column"]
    raw = artifact_bytes(value)
    with no_write_attempts(), pytest.raises(CSVError) as caught:
        CSVProfile(raw)
    assert caught.value.diagnostic()["source_sha256"] == sha256(raw).hexdigest()


@pytest.mark.parametrize("raw", [b'ID,Text\r\nx,"broken', b'ID,Text\r\nx,bare"quote\r\n',
    b'ID,Text\nx,value\n', b'ID,Text\r\nx,a,extra\r\n', b'ID,Text\r\nx,one\r\nx,two\r\n'])
def test_invalid_dataset_never_returns_only_the_valid_prefix(raw):
    codec = selected([column("Text")])
    with no_write_attempts(), pytest.raises(CSVError) as caught:
        codec.decode(raw)
    assert caught.value.diagnostic()["source_sha256"] == sha256(raw).hexdigest()
    assert caught.value.diagnostic()["profile"]["sha256"] == codec.profile.sha256


def test_raw_resource_spelling_is_observed_separately_from_canonical_hash():
    profile, mapping = resources([column("Text")])
    other = CSVProfile(b" \n" + profile.source_bytes)
    assert other.sha256 == profile.sha256 and other.source_sha256 != profile.source_sha256
    codec = select_csv_profile([other, mapping], key=profile.key, expected_sha256=profile.sha256)
    observed = codec.decode(b"ID,Text\r\nx,data\r\n")
    assert observed.observation()["profile"]["source_sha256"] == other.source_sha256


@pytest.mark.parametrize("mode", ["core", "pyz"])
def test_bound_codec_is_available_without_optional_packages_or_process_environment(mode, tmp_path):
    from support.portable import build_distribution
    from support.processes import run_core, run_python
    profile, mapping = resources([column("Value", "typed-json-v1")])
    rows = [record({"Value": {"list": [None, True, "ä"]}}), record({}, identity="missing")]
    body = "\n".join([
        "from specroad.exchange import select_csv_profile",
        "from specroad.mappings import CSVProfile, ExchangeMapping",
        "p=CSVProfile(" + repr(profile.source_bytes) + ")",
        "m=ExchangeMapping(" + repr(mapping.source_bytes) + ")",
        "codec=select_csv_profile([p,m],key=p.key,expected_sha256=p.sha256)",
        "rows=" + repr(rows), "assert codec.decode(codec.encode(rows)).records == rows"])
    if mode == "core":
        result = run_core(body, tmp_path)
    else:
        _, app = build_distribution(tmp_path / "dist")
        result = run_python(["-I", "-S", "-B", "-c", "import sys;sys.path.insert(0," + repr(str(app)) + ");" + body], tmp_path)
    assert result.returncode == 0, result.stderr


def test_json_escaped_del_is_read_but_canonical_export_cannot_publish_forbidden_raw_text():
    codec = selected([column("V", "typed-json-v1")])
    raw = b'ID,V\r\nx,"{""type"":""string"",""value"":""\\u007f""}"\r\n'
    observed = codec.decode(raw)
    assert observed.records == [record({"V": "\x7f"}, identity="x")]
    # JCS leaves DEL literal. The RFC text grammar must still reject it; no
    # noncanonical escape, dropped character or partial output is substituted.
    with no_write_attempts(), pytest.raises(CSVError) as caught:
        codec.encode(observed.records)
    assert caught.value.reason == "csv_unrepresentable_character"
    assert observed.source_bytes == raw and observed.records[0]["fields"]["V"] == "\x7f"
