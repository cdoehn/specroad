"""14.f.R: exact CSV boundaries, safe diagnostics and inverse field values."""
from copy import deepcopy
from hashlib import sha256
import csv
import json

import pytest

from specroad.exchange import select_csv_profile
from specroad.mappings import CSVError, CSVProfile, ExchangeMapping, MappingError, select_mapping
from support.artifacts import artifact_bytes
from support.csv_codec import column, record, resources, selected
from support.read_only import inventory, make_project, no_write_attempts


def quoted(text):
    return '"' + text.replace('"', '""') + '"'


def check_error(error, codec, *, raw=None, record_number=None, column_number=None):
    data = error.diagnostic()
    assert data["code"] == "SRV090" and data["exit_code"] == 3
    assert data["profile"]["sha256"] == codec.profile.sha256
    assert data["mapping"]["sha256"] == codec.mapping.sha256
    assert data.get("record") == record_number and data.get("column") == column_number
    if raw is not None:
        assert data["source_sha256"] == sha256(raw).hexdigest()
    assert "sensitive-value" not in json.dumps(data)


@pytest.mark.parametrize("bom", [b"", b"\xef\xbb\xbf"])
@pytest.mark.parametrize("header", ["ID", "\ufeffID"])
def test_only_the_initial_bom_is_signature_and_real_feff_data_roundtrips(bom, header):
    codec = selected([column("Text")], identity_column=header)
    raw = bom + (quoted(header) + ',Text\r\n' + quoted('\ufeffid') + ',' + quoted('a\ufeffb') + '\r\n').encode()
    observed = codec.decode(raw)
    assert observed.records == [record({"Text": "a\ufeffb"}, identity="\ufeffid")]
    assert observed.source_bytes == raw and observed.observation()["source_sha256"] == sha256(raw).hexdigest()
    output = codec.encode(observed.records)
    assert not output.startswith(b"\xef\xbb\xbf")
    assert output.startswith(('"\ufeffID"' if header.startswith('\ufeff') else 'ID').encode())
    assert codec.decode(output).records == observed.records


def test_second_initial_bom_is_header_data_and_never_silently_stripped():
    raw = b"\xef\xbb\xbf\xef\xbb\xbfID,Text\r\nx,kept\r\n"
    assert selected([column("Text")], identity_column="\ufeffID").decode(raw).records == [record({"Text": "kept"}, identity="x")]
    codec = selected([column("Text")])
    with pytest.raises(CSVError) as caught:
        codec.decode(raw)
    check_error(caught.value, codec, raw=raw, record_number=1, column_number=1)


@pytest.mark.parametrize("raw", [b"ID,Text,Count", b"Count,Text,ID\r\n"])
def test_header_only_is_complete_zero_record_observation(raw):
    codec = selected([column("Text"), column("Count", "integer")])
    observed = codec.decode(raw)
    assert observed.records == [] and observed.observation()["record_count"] == 0
    assert codec.encode(observed.records) == b"ID,Text,Count\r\n"


def test_reordered_unicode_headers_are_literal_and_export_uses_declared_order():
    codec = selected([column(" e\u0301 "), column("\u00e9", "integer")])
    raw = '\u00e9,ID, e\u0301 \r\n7,x, kept \r\n'.encode()
    rows = [record({" e\u0301 ": " kept ", "\u00e9": 7}, identity="x")]
    assert codec.decode(raw).records == rows
    assert codec.encode(rows) == 'ID, e\u0301 ,\u00e9\r\nx, kept ,7\r\n'.encode()


@pytest.mark.parametrize("header,at", [("ID,Text,Text", 3), ("ID,,Text", 2),
    ("ID,Text,sensitive-value", 3), ("ID,text", 2), (" ID,Text", 1)])
def test_first_invalid_header_column_is_reported_without_echoing_names(header, at):
    codec = selected([column("Text")])
    raw = (header + "\r\n").encode()
    with pytest.raises(CSVError) as caught:
        codec.decode(raw)
    assert caught.value.reason == "csv_invalid_header"
    check_error(caught.value, codec, raw=raw, record_number=1, column_number=at)


@pytest.mark.parametrize("raw,reason", [(b"ID\r\nx\r\n", "csv_column_required"),
    (b"Text\r\nkept\r\n", "csv_identity_header_required"),
    (b"", "csv_header_required"), (b"\xef\xbb\xbf", "csv_header_required")])
def test_missing_required_header_is_not_assigned_a_fictional_column(raw, reason):
    codec = selected([column("Text")])
    with pytest.raises(CSVError) as caught:
        codec.decode(raw)
    assert caught.value.reason == reason
    check_error(caught.value, codec, raw=raw, record_number=1)


def test_absent_header_preserves_absence_and_mapping_still_requires_its_source():
    codec = selected([column("Optional", "typed-json-v1", missing="absent"), column("Text")])
    observed = codec.decode(b"ID,Text\r\nx,kept\r\n")
    assert observed.records == [record({"Text": "kept"}, identity="x")]
    mapper = select_mapping([codec.mapping], key=codec.mapping.key, expected_sha256=codec.mapping.sha256)
    with pytest.raises(MappingError) as caught:
        mapper.artifact("Requirement", observed.records[0]["fields"])
    assert caught.value.reason == "mapping_source_field_missing"
    assert codec.decode(codec.encode(observed.records)).records == observed.records
    with pytest.raises(CSVError) as caught:
        codec.decode(b"ID,Optional,Text\r\nx,kept\r\n")
    assert caught.value.reason == "csv_row_width"
    check_error(caught.value, codec, record_number=2, column_number=3)


@pytest.mark.parametrize("tail,at", [(b"x\r\n", 2), (b"x,a,extra\r\n", 3), (b"\r\n", 2)])
def test_bad_width_including_blank_record_is_not_skipped_after_a_valid_prefix(tail, at):
    codec = selected([column("Text")])
    raw = b'ID,Text\r\ngood,"one\r\ntwo"\r\n' + tail
    with pytest.raises(CSVError) as caught:
        codec.decode(raw)
    assert caught.value.reason == "csv_row_width"
    check_error(caught.value, codec, raw=raw, record_number=3, column_number=at)


@pytest.mark.parametrize("raw,reason,rec,col", [
    (b'ID,Text\r\nx,bare"sensitive-value\r\n', "csv_invalid_quote", 2, 2),
    (b'ID,Text\r\nx,"sensitive-value"after\r\n', "csv_after_quote", 2, 2),
    (b'ID,Text\r\nx,"sensitive-value', "csv_unclosed_quote", 2, 2),
    (b'ID,Text\r\nx,"one\r\ntwo"\r\ny,"sensitive-value', "csv_unclosed_quote", 3, 2),
    (b'ID,Text\nx,sensitive-value\n', "csv_record_separator", 1, 2),
    (b'ID,Text\r\nx,sensitive-value\r', "csv_record_separator", 2, 2),
    (b'ID,Text\r\nx,sensitive-value\n', "csv_record_separator", 2, 2),
    (b'ID,Text\r\nx,one\r\nx,sensitive-value\r\n', "csv_duplicate_identity", 3, 1),
    (b'Text,ID\r\nsensitive-value,\r\n', "csv_identity_required", 2, 2),
    (b'ID,Text\r\nx,sensitive-value\xff', "csv_invalid_utf8", None, None),
])
def test_malformed_input_has_safe_bindings_and_logical_locations(raw, reason, rec, col):
    codec = selected([column("Text")])
    with no_write_attempts(), pytest.raises(CSVError) as caught:
        codec.decode(raw)
    assert caught.value.reason == reason
    check_error(caught.value, codec, raw=raw, record_number=rec, column_number=col)


@pytest.mark.parametrize("control", ["\0", "\t", "\x1f", "\x7f"])
@pytest.mark.parametrize("quote", [False, True])
def test_forbidden_raw_controls_are_rejected_even_in_quotes(control, quote):
    codec = selected([column("Text")])
    cell = "sensitive-value" + control
    raw = ("ID,Text\r\nx," + (quoted(cell) if quote else cell) + "\r\n").encode()
    with pytest.raises(CSVError) as caught:
        codec.decode(raw)
    assert caught.value.reason == "csv_invalid_character"
    check_error(caught.value, codec, raw=raw, record_number=2, column_number=2)


@pytest.mark.parametrize("kind,text", [
    ("boolean", "1"), ("boolean", "False"), ("boolean", " true"),
    ("integer", "01"), ("integer", "+1"), ("integer", "1.0"), ("integer", "1e1"),
    ("integer", "9007199254740993"), ("number", "NaN"), ("number", "Infinity"),
    ("number", "1e400"), ("number", "1,5"), ("number", "1 "), ("number", "true"),
    ("list", "{}"), ("list", "[NaN]"), ("list", '[{"sensitive-value":1,"sensitive-value":2}]'),
    ("list", '["\\ud800"]'), ("list", "[] []"), ("list", '[],"sensitive-value":1'),
    ("typed-json-v1", "null"), ("typed-json-v1", '{"type":"missing","value":null}'),
    ("typed-json-v1", '{"type":"null","value":"null"}'),
    ("typed-json-v1", '{"type":"boolean","value":0}'),
    ("typed-json-v1", '{"type":"number","value":false}'),
    ("typed-json-v1", '{"type":"array","value":{}}'),
    ("typed-json-v1", '{"type":"string","value":"sensitive-value","extra":0}'),
    ("typed-json-v1", '{"type":"string","type":"string","value":"sensitive-value"}'),
])
def test_invalid_typed_cells_reject_complete_input_and_do_not_leak_json_positions(kind, text):
    codec = selected([column("V", kind)])
    raw = ("V,ID\r\n" + quoted(text) + ",x\r\n").encode()
    with no_write_attempts(), pytest.raises(CSVError) as caught:
        codec.decode(raw)
    check_error(caught.value, codec, raw=raw, record_number=2, column_number=1)


@pytest.mark.parametrize("kind", ["string", "boolean", "integer", "number", "list"])
@pytest.mark.parametrize("policy", ["value", "null", "error"])
def test_quoted_and_unquoted_empty_cells_share_the_explicit_policy(kind, policy):
    codec = selected([column("V", kind, empty=policy)])
    for cell in ('', '""'):
        raw = ('ID,V\r\nx,' + cell + '\r\n').encode()
        if policy == "null" or (kind == "string" and policy == "value"):
            assert codec.decode(raw).records[0]["fields"]["V"] == (None if policy == "null" else "")
        else:
            with pytest.raises(CSVError) as caught:
                codec.decode(raw)
            check_error(caught.value, codec, raw=raw, record_number=2, column_number=2)


def inverse_codec(table, kind="typed-json-v1"):
    profile, mapping = resources([column("V", kind)])
    rules = mapping.data
    rules["fields"][0]["value_map"] = table
    mapping = ExchangeMapping(artifact_bytes(rules))
    declaration = profile.data
    declaration["mapping"] = mapping.binding()
    profile = CSVProfile(artifact_bytes(declaration))
    return select_csv_profile([mapping, profile], key=profile.key, expected_sha256=profile.sha256)


@pytest.mark.parametrize("value", [None, "", False, 0, "0", [1, 2], [2, 1], {"b": None, "a": 1.0}])
def test_inverse_uses_one_canonical_match_and_preserves_boolean_number_and_structured_types(value):
    values = [None, "", False, 0, "0", [1, 2], [2, 1], {"a": 1, "b": None}]
    codec = inverse_codec([{"external_value": {"choice": [i]}, "target_value": v} for i, v in enumerate(values)])
    # The expected index is specified by each JSON value's type and ordering,
    # not Python's equality between False and zero.
    expected = {"null": 0, "\"\"": 1, "false": 2, "0": 3, "\"0\"": 4,
                "[1, 2]": 5, "[2, 1]": 6}.get(json.dumps(value), 7)
    native = {"value-0": deepcopy(value)}
    before = deepcopy(native)
    with no_write_attempts():
        external = codec.external_fields(native)
        assert external == {"V": {"choice": [expected]}}
        output = codec.encode([record(external)])
        assert codec.decode(output).records == [record(external)]
        mapper = select_mapping([codec.mapping], key=codec.mapping.key, expected_sha256=codec.mapping.sha256)
        assert mapper.artifact("Requirement", external)["artifact"]["value-0"] == value
    external["V"]["choice"].append("changed")
    assert native == before and codec.external_fields(native) == {"V": {"choice": [expected]}}


@pytest.mark.parametrize("table,target", [
    ([{"external_value": "a", "target_value": 1}], 2),
    ([{"external_value": "a", "target_value": 1}, {"external_value": "b", "target_value": 1.0}], 1),
    ([{"external_value": "a", "target_value": {"a": 1, "b": None}},
      {"external_value": "b", "target_value": {"b": None, "a": 1.0}}], {"a": 1, "b": None}),
])
def test_noninvertible_concrete_value_is_not_resolved_by_first_row(table, target):
    codec = inverse_codec(table)
    with no_write_attempts(), pytest.raises(CSVError) as caught:
        codec.external_fields({"value-0": target})
    assert caught.value.reason == "csv_value_map_not_invertible"
    check_error(caught.value, codec, column_number=2)


def test_unrelated_noninvertible_values_do_not_block_a_unique_concrete_inverse():
    codec = inverse_codec([{"external_value": "a", "target_value": 0},
                           {"external_value": "b", "target_value": 0},
                           {"external_value": "c", "target_value": 1}])
    assert codec.external_fields({"value-0": 1}) == {"V": "c"}


def test_inverse_joins_by_field_names_and_rejects_a_late_unmapped_value():
    profile, mapping = resources([column("Flag", "boolean"), column("Nested", "list")])
    rules = mapping.data
    rules["fields"][0]["value_map"] = [{"external_value": False, "target_value": "chosen"}]
    rules["fields"].reverse()
    mapping = ExchangeMapping(artifact_bytes(rules))
    declaration = profile.data
    declaration["mapping"] = mapping.binding()
    profile = CSVProfile(artifact_bytes(declaration))
    codec = select_csv_profile([profile, mapping], key=profile.key, expected_sha256=profile.sha256)
    native = {"value-1": [{"nested": [True, None]}], "value-0": "chosen"}
    before = deepcopy(native)
    external = codec.external_fields(native)
    assert external == {"Flag": False, "Nested": [{"nested": [True, None]}]}
    external["Nested"][0]["nested"].clear()
    assert native == before
    native["value-1"] = "sensitive-value"
    with pytest.raises(CSVError) as caught:
        codec.external_fields(native)
    check_error(caught.value, codec, column_number=3)
    assert native == {**before, "value-1": "sensitive-value"}


@pytest.mark.parametrize("native", [{}, {"value-0": "ok", "extra": "sensitive-value"}, [], {1: "bad"}])
def test_inverse_requires_exact_declared_target_fields_without_loss(native):
    codec = inverse_codec(None)
    with pytest.raises(CSVError) as caught:
        codec.external_fields(native)
    assert caught.value.reason == "csv_native_field_set"
    check_error(caught.value, codec)


@pytest.mark.parametrize("kind,value", [("integer", False), ("integer", 1.0),
    ("number", float("nan")), ("string", "sensitive-value\t"), ("list", "a;b")])
@pytest.mark.parametrize("mapped", [False, True])
def test_inverse_and_export_both_reject_values_the_cell_cannot_represent(kind, value, mapped):
    # A nonfinite value cannot itself be stored in a valid mapping resource.
    if mapped and type(value) is float and value != value:
        value = "NaN"
    table = [{"external_value": value, "target_value": "target"}] if mapped else None
    codec = inverse_codec(table, kind)
    native = {"value-0": "target" if mapped else value}
    with no_write_attempts(), pytest.raises(CSVError) as caught:
        codec.external_fields(native)
    check_error(caught.value, codec, column_number=2)
    with pytest.raises(CSVError) as caught:
        codec.encode([record({"V": value})])
    check_error(caught.value, codec, record_number=2, column_number=2)


class Foreign:
    def __hash__(self):
        return 1

    def __eq__(self, other):
        raise AssertionError("Foreign equality executed")

    def __str__(self):
        raise AssertionError("Foreign conversion executed")

    def __iter__(self):
        raise AssertionError("Foreign iteration executed")


@pytest.mark.parametrize("location", ["record-key", "identity-key", "kind", "type", "field-key", "nested", "sequence"])
def test_export_rejects_foreign_objects_before_comparison_or_conversion_hooks(location):
    codec = selected([column("V", "typed-json-v1")])
    row = record({"V": {"nested": []}})
    bad = Foreign()
    if location == "record-key": row[bad] = 1
    if location == "identity-key": row["identity"][bad] = 1
    if location == "kind": row["identity"]["kind"] = bad
    if location == "type": row["external_type"] = bad
    if location == "field-key": row["fields"][bad] = 1
    if location == "nested": row["fields"]["V"]["nested"].append(bad)
    with no_write_attempts(), pytest.raises(CSVError):
        codec.encode(bad if location == "sequence" else [row])


def test_cycle_and_excessive_json_nesting_never_publish_a_prefix_or_observation():
    codec = selected([column("V", "list")])
    cycle = []
    cycle.append(cycle)
    with pytest.raises(CSVError) as caught:
        codec.encode([record({"V": []}), record({"V": cycle}, identity="bad")])
    assert caught.value.reason == "cyclic_json"
    check_error(caught.value, codec, record_number=3, column_number=2)
    deep = "[" * 2000 + "0" + "]" * 2000
    raw = ('ID,V\r\ngood,[]\r\nbad,' + quoted(deep) + '\r\n').encode()
    with pytest.raises(CSVError) as caught:
        codec.decode(raw)
    check_error(caught.value, codec, raw=raw, record_number=3, column_number=2)


def test_selected_resources_and_observations_stay_owned_after_returned_values_change():
    codec = selected([column("V", "typed-json-v1")])
    raw = codec.encode([record({"V": {"nested": [None, False, "=1+1"]}})])
    first = codec.decode(raw)
    facts, rows = first.observation(), first.records
    rows[0]["fields"]["V"]["nested"].clear()
    facts["mapping"]["sha256"] = "0" * 64
    exposed = codec.profile
    with pytest.raises(CSVError):
        exposed.__init__(b"broken")
    assert exposed.source_bytes == codec.profile.source_bytes
    replacement, _ = resources([column("Other")])
    exposed.__init__(replacement.source_bytes)
    assert codec.decode(raw).records == first.records
    assert first.observation()["mapping"]["sha256"] == codec.mapping.sha256
    changed = codec.mapping.data
    changed["fields"][0]["target_field"] = "different"
    with pytest.raises(CSVError) as caught:
        select_csv_profile([codec.profile, ExchangeMapping(artifact_bytes(changed))],
                           key=codec.profile.key, expected_sha256=codec.profile.sha256)
    assert caught.value.reason == "mapping_hash_mismatch"


def test_large_fields_and_many_records_are_complete_without_global_csv_limit_changes():
    codec = selected([column("Text")])
    old_limit = csv.field_size_limit()
    rows = [record({"Text": 'x,"\r\n' * 40000})]
    rows += [record({"Text": str(i)}, identity="id-" + str(i)) for i in range(150)]
    before = deepcopy(rows)
    try:
        csv.field_size_limit(8)
        with no_write_attempts():
            raw = codec.encode(rows)
            observed = codec.decode(raw)
        assert csv.field_size_limit() == 8
    finally:
        csv.field_size_limit(old_limit)
    assert rows == before == observed.records and observed.observation()["record_count"] == 151


def test_codec_never_reads_data_derived_paths_or_writes_the_project(tmp_path, monkeypatch):
    (tmp_path / "project").mkdir()
    project = make_project(tmp_path / "project")
    payload = project / "sensitive-value"
    payload.write_bytes(b"must not be read or changed")
    before = inventory(project)
    codec = inverse_codec(None, "string")
    native = {"value-0": str(payload)}
    monkeypatch.chdir(project)
    import builtins
    import io
    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected file read")
    with no_write_attempts(), monkeypatch.context() as guard:
        guard.setattr(builtins, "open", forbidden)
        guard.setattr(io, "open", forbidden)
        fields = codec.external_fields(native)
        rows = [record(fields, identity="../../external")]
        assert codec.decode(codec.encode(rows)).records == rows
        with pytest.raises(CSVError):
            codec.decode(b"ID,V\r\nx,good\r\nx,sensitive-value\r\n")
    assert inventory(project) == before and native == {"value-0": str(payload)}


@pytest.mark.parametrize("error", [RuntimeError("implementation failure"), MemoryError("resource limit")])
def test_unexpected_failures_are_not_masked_as_a_success_or_conversion_diagnostic(monkeypatch, error):
    codec = selected([column("Text")])
    import specroad.exchange.csv as module
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(module, "decode_cell", fail)
    with pytest.raises(type(error)) as caught:
        codec.decode(b"ID,Text\r\nx,value\r\n")
    assert caught.value is error


@pytest.mark.parametrize("mode", ["core", "pyz"])
def test_inverse_and_reject_contracts_are_available_in_isolated_core_and_pyz(mode, tmp_path):
    from support.portable import build_distribution
    from support.processes import run_core, run_python
    codec = inverse_codec([{"external_value": False, "target_value": "chosen"}], "boolean")
    body = "\n".join([
        "from specroad.exchange import select_csv_profile",
        "from specroad.mappings import CSVProfile, ExchangeMapping, CSVError",
        "p=CSVProfile(" + repr(codec.profile.source_bytes) + ")",
        "m=ExchangeMapping(" + repr(codec.mapping.source_bytes) + ")",
        "c=select_csv_profile([m,p],key=p.key,expected_sha256=p.sha256)",
        "assert c.external_fields({'value-0':'chosen'}) == {'V':False}",
        "assert c.decode(b'\\xef\\xbb\\xbfV,ID\\r\\nfalse,x\\r\\n').records[0]['fields'] == {'V':False}",
        "try: c.external_fields({'value-0':'absent'})",
        "except CSVError as e: assert e.code == 'SRV090' and e.exit_code == 3 and e.column == 2",
        "else: raise AssertionError('unmapped native value accepted')",
        "try: c.decode(b'ID,V\\r\\nx,false\\r\\ny,0\\r\\n')",
        "except CSVError as e: assert e.record == 3 and e.column == 2",
        "else: raise AssertionError('invalid boolean accepted')"])
    if mode == "core":
        result = run_core(body, tmp_path)
    else:
        _, app = build_distribution(tmp_path / "dist")
        result = run_python(["-I", "-S", "-B", "-c", "import sys;sys.path.insert(0," + repr(str(app)) + ");" + body], tmp_path)
    assert result.returncode == 0, result.stderr
