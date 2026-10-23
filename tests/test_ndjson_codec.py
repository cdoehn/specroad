"""14.g.W: exact native envelopes, ordered roundtrips and passive rejection."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.changes import ChangePlan
from specroad.exchange import (NDJSONError, NDJSONObservation, decode_ndjson,
                              encode_ndjson, iter_decode_ndjson, iter_encode_ndjson)
from specroad.model.canonical import canonical_json_bytes
from specroad.model.domain_schemas import DOMAIN_TYPES
from specroad.model.record_schemas import RECORD_TYPES
from support.artifacts import common_artifact
from support.domain import domain_value, relation
from support.ndjson_codec import envelope, plan_value
from support.read_only import no_write_attempts
from support.records import record_value, ref


def wire(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode() + b"\n"


def check_rejected(value, direction):
    before = deepcopy(value)
    with no_write_attempts(), pytest.raises(NDJSONError) as caught:
        if direction == "decode":
            decode_ndjson(wire(value))
        else:
            encode_ndjson([value])
    assert value == before
    assert caught.value.exit_code == 3 and caught.value.line == 1
    return caught.value


@pytest.mark.parametrize("kind", (*DOMAIN_TYPES, *RECORD_TYPES))
def test_every_native_core_type_survives_the_transport(kind):
    payload = domain_value(kind) if kind in DOMAIN_TYPES else record_value(kind)
    item = envelope(payload)
    with no_write_attempts():
        observed = decode_ndjson(wire(item))
        output = encode_ndjson(observed.objects)
        again = decode_ndjson(output)
    assert observed.objects == again.objects == [item]
    assert again.objects[0]["object"] == payload
    assert "format_version" not in again.objects[0]["object"]
    assert again.write_authorized is False and again.execution_ready is False


def test_mixed_stream_keeps_order_revisions_duplicates_and_native_plan_hashes():
    plan = plan_value()
    requirement = domain_value("requirement", language="zh-Hant-TW", normative_force="must_not",
                               statement="e\u0301 é 日本語 العربية", revision=4,
                               external_identities=[{"system": "literal", "external_id": "A-1", "revision": "04"}])
    requirement["relations"] = [relation("refines", ref("REQ", "2")), relation("refines", ref("REQ", "1"))]
    requirement["relations"][1]["relation_id"] = "REL-" + "1" * 26
    requirement["extensions"] = {"example.data": {"null": None, "list": [False, 0, 1.25, "", [], {}, None],
                                                  "schema_url": "https://example.invalid/never-read"}}
    rows = [envelope(requirement), envelope(plan, "change_plan"), envelope(domain_value("goal", revision=2)),
            envelope(requirement), envelope(record_value("proposal")), envelope(plan, "change_plan")]
    before = deepcopy(rows)
    raw = b"".join(wire(row) for row in rows)
    observed = decode_ndjson(raw)
    output = encode_ndjson(observed.objects)
    assert decode_ndjson(output).objects == observed.objects == before == rows
    recovered = observed.objects[1]["object"]
    assert recovered["format_version"] == "1.2.0" and observed.objects[1]["format_version"] == "1.0.0"
    assert recovered["metadata_policy_version"] == "change-metadata-v1"
    assert recovered["change_plan_sha256"] == plan["change_plan_sha256"]
    assert ChangePlan(canonical_json_bytes(recovered)).canonical_bytes == canonical_json_bytes(plan)
    assert recovered["operations"] == plan["operations"]
    assert observed.source_bytes == raw and observed.source_sha256 == sha256(raw).hexdigest()
    assert observed.source_bytes != output and observed.source_sha256 != sha256(output).hexdigest()
    facts = observed.observation()
    assert facts == {"format_version": "1.0.0", "source_sha256": sha256(raw).hexdigest(),
                     "object_count": 6, "complete": True, "validation_scope": "ndjson_native_fields_only",
                     "write_authorized": False, "execution_ready": False}


def test_native_null_absence_and_nested_lists_are_not_filled_or_flattened():
    absent = record_value("configuration")
    explicit = record_value("configuration", parent=None)
    absent["extensions"] = {"example.data": {"items": [[], [None, ["a", "a"]]], "text": "null"}}
    explicit["extensions"] = {"example.data": {"items": [[], [None, ["a", "a"]]], "text": "null", "empty": None}}
    rows = [envelope(absent), envelope(explicit)]
    recovered = decode_ndjson(encode_ndjson(rows)).objects
    assert recovered == rows
    assert "parent" not in recovered[0]["object"] and recovered[1]["object"]["parent"] is None
    assert "empty" not in recovered[0]["object"]["extensions"]["example.data"]


def test_canonical_export_has_exact_envelope_bytes_lf_and_no_transport_metadata_in_payload():
    rows = [envelope(domain_value()), envelope(plan_value(), "change_plan")]
    expected = b"".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() + b"\n"
                        for row in rows)
    assert encode_ndjson(rows) == expected == encode_ndjson(deepcopy(rows))
    assert list(iter_encode_ndjson(iter(rows))) == expected.splitlines(keepends=True)
    assert not expected.startswith(b"\xef\xbb\xbf") and expected.count(b"\n") == 2
    assert [json.loads(line)["object"] for line in expected.splitlines()] == [row["object"] for row in rows]


@pytest.mark.parametrize("raw", [b"", b"\n", b"\n\n\n"])
def test_empty_stream_has_no_objects_and_exports_zero_bytes(raw):
    result = NDJSONObservation(raw)
    assert result.objects == [] and list(iter_decode_ndjson(raw)) == []
    assert encode_ndjson(result.objects) == b"" and list(iter_encode_ndjson(iter(()))) == []
    assert result.source_bytes == raw and result.observation()["object_count"] == 0


def test_objects_and_observation_are_detached_and_observation_is_immutable():
    original = envelope(domain_value(extensions={"example.data": {"items": [1]}}))
    raw = wire(original)
    observed = decode_ndjson(raw)
    observed.objects[0]["object"]["extensions"]["example.data"]["items"].append(2)
    observed.observation()["complete"] = False
    original["object"]["title"] = "caller mutation"
    assert observed.objects == [json.loads(raw)] and observed.observation()["complete"] is True
    with pytest.raises(FrozenInstanceError):
        observed.source_bytes = b""


@pytest.mark.parametrize("direction", ["decode", "encode"])
@pytest.mark.parametrize("defect", ["format_version", "object_kind", "object", "extra", "bare-artifact", "bare-plan"])
def test_closed_envelope_cannot_be_filled_in_or_inferred(defect, direction):
    item = envelope(domain_value())
    if defect in ("format_version", "object_kind", "object"):
        item.pop(defect)
    elif defect == "extra":
        item["schema_url"] = "https://example.invalid/never-read"
    elif defect == "bare-artifact":
        item = domain_value()
    else:
        item = plan_value()
    assert check_rejected(item, direction).reason == "ndjson_envelope_fields"


@pytest.mark.parametrize("direction", ["decode", "encode"])
@pytest.mark.parametrize("field,value", [
    ("format_version", 1), ("format_version", "1.2.0"), ("format_version", "0.2.0"),
    ("format_version", None), ("format_version", []),
    ("object_kind", "goal"), ("object_kind", "plan"), ("object_kind", "Artifact"),
    ("object_kind", False), ("object_kind", {}),
    ("object", []), ("object", None), ("object", True), ("object", "{}"), ("object", 1),
])
def test_wrong_discriminators_and_payload_types_are_rejected(field, value, direction):
    item = envelope(domain_value()); item[field] = value
    error = check_rejected(item, direction)
    assert error.pointer == "/" + field


@pytest.mark.parametrize("direction", ["decode", "encode"])
@pytest.mark.parametrize("defect", ["common-only", "missing-language", "missing-force", "schema-version", "type",
                                    "id", "unknown-field", "bool-revision", "local-record", "local-domain", "plan-as-artifact"])
def test_type_specific_native_validation_is_required(defect, direction):
    payload = domain_value("requirement")
    if defect == "common-only": payload = common_artifact()
    if defect == "missing-language": del payload["language"]
    if defect == "missing-force": del payload["normative_force"]
    if defect == "schema-version": payload["schema_version"] = "99.0.0"
    if defect == "type": payload["artifact_type"] = ["requirement"]
    if defect == "id": payload["id"] = ref("GOAL")
    if defect == "unknown-field": payload["schema_url"] = "file:///never-read"
    if defect == "bool-revision": payload["revision"] = True
    if defect == "local-record": payload = record_value("configuration", selection={"unknown-dimension": "linux"})
    if defect == "local-domain": payload = domain_value("milestone", relations=[])
    if defect == "plan-as-artifact": payload = plan_value()
    error = check_rejected(envelope(payload), direction)
    assert error.pointer.startswith("/object")


@pytest.mark.parametrize("direction", ["decode", "encode"])
@pytest.mark.parametrize("defect", ["draft", "version", "policy", "self-hash", "tamper", "result-hash", "owners",
                                    "operation", "extra", "artifact-as-plan", "proposal-as-plan", "import-plan"])
def test_native_regular_plan_binding_is_verified_without_repair(defect, direction):
    value = plan_value()
    if defect == "draft": del value["change_plan_sha256"]
    if defect == "version": value["format_version"] = "1.0.0"
    if defect == "policy": value["metadata_policy_version"] = "merge-metadata-v1"
    if defect == "self-hash": value["change_plan_sha256"] = "0" * 64
    if defect == "tamper": value["request_id"] = "tampered:request"
    if defect == "result-hash": value["result_artifacts"][0]["sha256"] = "f" * 64
    if defect == "owners": value["result_artifacts"] = []
    if defect == "operation": value["operations"][0]["op"] = "shell"
    if defect == "extra": value["schema_url"] = "file:///never-read"
    if defect == "artifact-as-plan": value = domain_value()
    if defect == "proposal-as-plan": value = record_value("proposal")
    if defect == "import-plan": value = {"format_version": "import-plan-v1", "operations": []}
    error = check_rejected(envelope(value, "change_plan"), direction)
    assert error.pointer.startswith("/object")
    if defect in ("self-hash", "tamper"):
        assert error.reason == "change_plan_hash_mismatch" and error.pointer == "/object/change_plan_sha256"


@pytest.mark.parametrize("raw", [b"// comment\n", b"{}\r\n", b"[]\n", b'{}{}\n', b'{"x":1,"x":2}\n', b'\xff\n'])
def test_invalid_wire_is_never_an_empty_success(raw):
    with pytest.raises(NDJSONError) as caught:
        decode_ndjson(raw)
    assert caught.value.line == 1 and caught.value.exit_code == 3


def test_late_failure_keeps_streaming_prefix_partial_and_prevents_complete_result():
    good = envelope(domain_value())
    raw = wire(good) + b"\n" + wire(envelope({"secret": "do-not-disclose"}))
    iterator = iter_decode_ndjson(raw)
    assert next(iterator) == good
    with pytest.raises(NDJSONError) as caught:
        next(iterator)
    assert caught.value.line == 3 and "do-not-disclose" not in json.dumps(caught.value.diagnostic())
    with pytest.raises(NDJSONError): decode_ndjson(raw)
    with pytest.raises(NDJSONError): encode_ndjson([good, envelope({})])
    # The reader advances one record at a time, independent of caller mutations.
    assert decode_ndjson(wire(good)).objects == [good]


def test_export_iterates_only_as_requested_without_claiming_prefix_success():
    item = envelope(domain_value())
    progress = []
    def records():
        for number in range(3):
            progress.append(number)
            yield item
    output = iter_encode_ndjson(records())
    assert next(output) == encode_ndjson([item]) and progress == [0]
    assert b"".join(output) == encode_ndjson([item, item]) and progress == [0, 1, 2]


@pytest.mark.parametrize("raw", [None, "", [], bytearray(), {}])
def test_decoder_requires_explicit_complete_bytes(raw):
    with pytest.raises(NDJSONError): decode_ndjson(raw)


@pytest.mark.parametrize("objects", [None, "", b"", {}, bytearray(), True, 0])
def test_encoder_requires_an_object_iterable(objects):
    with pytest.raises(NDJSONError): encode_ndjson(objects)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), 9007199254740993, "\ud800", ("not", "json")])
def test_export_does_not_coerce_non_json_or_lossy_values(bad):
    value = envelope(domain_value(extensions={"example.data": {"bad": bad}}))
    with pytest.raises(NDJSONError) as caught:
        encode_ndjson([value])
    assert caught.value.exit_code == 3 and caught.value.line == 1
    assert caught.value.pointer.startswith("/object/extensions")


def test_export_cannot_serialize_a_cycle_or_invoke_foreign_value_hooks():
    calls = []
    class Foreign:
        def __str__(self):
            calls.append(True)
            raise AssertionError("Foreign conversion")
        def __iter__(self):
            calls.append(True)
            raise AssertionError("Foreign traversal")
    for bad in (Foreign(), []):
        if type(bad) is list: bad.append(bad)
        with pytest.raises(NDJSONError):
            encode_ndjson([envelope(domain_value(extensions={"example.data": {"bad": bad}}))])
    assert calls == []


@pytest.mark.parametrize("mode", ["core", "pyz"])
def test_passive_codec_runs_in_isolated_core_and_pyz(mode, tmp_path):
    from support.portable import build_distribution
    from support.processes import run_core, run_python
    rows = [envelope(domain_value("requirement")), envelope(plan_value(), "change_plan")]
    body = "\n".join([
        "from specroad.exchange import decode_ndjson, encode_ndjson",
        "rows=" + repr(rows),
        "observed=decode_ndjson(encode_ndjson(rows))",
        "assert observed.objects == rows and not observed.write_authorized and not observed.execution_ready"])
    if mode == "core":
        result = run_core(body, tmp_path)
    else:
        _, app = build_distribution(tmp_path / "dist")
        result = run_python(["-I", "-S", "-B", "-c", "import sys;sys.path.insert(0," + repr(str(app)) + ");" + body], tmp_path)
    assert result.returncode == 0, result.stderr


def test_transport_cannot_load_execute_allocate_or_write(monkeypatch):
    import builtins
    import io
    import os
    import secrets
    import uuid
    import specroad.changes as changes
    import specroad.changes.execution as execution
    import specroad.changes.core as core
    import specroad.changes.receipt_finalization as receipts

    rows = [envelope(record_value("source", locator="https://example.invalid/never-read")),
            envelope(record_value("view")), envelope(plan_value(), "change_plan")]
    raw = b"".join(wire(row) for row in rows)
    calls = []
    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("Unexpected I/O, generation or execution")
    with no_write_attempts(), monkeypatch.context() as patcher:
        for module, name in ((builtins, "open"), (io, "open"), (os, "open"), (os, "urandom"),
                             (secrets, "token_bytes"), (uuid, "uuid4"),
                             (changes, "prepare_change_plan"), (core, "prepare_change_plan"),
                             (changes, "apply_change_plan"), (execution, "apply_change_plan"),
                             (receipts, "finalize_committing_journal")):
            patcher.setattr(module, name, forbidden)
        observed = decode_ndjson(raw)
        assert decode_ndjson(encode_ndjson(observed.objects)).objects == rows
        assert not observed.execution_ready and not observed.write_authorized
    assert calls == []
