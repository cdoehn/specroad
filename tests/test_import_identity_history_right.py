"""Native data roundtrips, explicit import projections and legacy compatibility."""
from copy import deepcopy
from hashlib import sha256
import json
from unittest.mock import patch

import pytest

from specroad.exchange import ExternalIdentity, ImportIdentityError, NativeIdentityIndex
from specroad.graph.relations import SourceRelations
from support.artifacts import artifact_bytes
from support.import_identities import history, TIME, MAPPING, LOCAL, SOURCE, PAYLOAD
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from support.relations import artifact, edge, external


@pytest.mark.parametrize("bound", [False, True])
@pytest.mark.parametrize("revision", [None, "", "007", "e\u0301/東京"])
def test_full_native_roundtrip_preserves_identity_and_unknown_extensions_at_each_level(bound, revision):
    identity = history().data if bound else external()
    identity.pop("external_revision", None)
    if revision is not None: identity["external_revision"] = revision
    opaque = {"native-looking": {"artifact_type": "unknown", "mapping_id": "passive"},
              "json": [None, False, 1, "1", [], {}, "\0\n", "e\u0301", "東京"]}
    identity["extensions"] = {"unknown.日本語": opaque}
    native = artifact(external_identities=[identity], extensions={"unknown.artifact": opaque},
        relations=[edge(external_identities=[identity], extensions={"unknown.relation": opaque})])
    original = deepcopy(native); raw = json.dumps(native, indent=3, ensure_ascii=True).encode() + b"\n"
    source = SourceRelations(raw); index = NativeIdentityIndex([source])
    loaded = source.data
    for kind in ("artifact", "relation"):
        match = index.lookup(kind, *ExternalIdentity(identity).key)
        value = ExternalIdentity(match["identity"])
        assert value.data == identity and value.import_bound == bound
        if kind == "artifact": loaded["external_identities"] = [value.data]
        else: loaded["relations"][0]["external_identities"] = [value.data]
    replay = SourceRelations(artifact_bytes(loaded))
    assert replay.data == original and source.source_bytes == raw
    assert ("external_revision" in replay.data["external_identities"][0]) == (revision is not None)
    assert replay.data["updated_at"] == original["updated_at"] and replay.data["revision"] == 1


def test_history_uses_only_explicit_projection_values_not_revision_extensions_or_time():
    a = history(); changed = a.data; changed["external_revision"] = "next"
    changed["extensions"]["vendor.other"] = {"payload": "opaque"}
    b = ExternalIdentity(changed).with_import_history(mapping_id=MAPPING, imported_projection=LOCAL,
        source_projection=SOURCE, source_payload=PAYLOAD, imported_at="2026-09-02T00:00:00Z")
    for name in ("last_imported_projection_sha256", "last_source_projection_sha256", "last_source_payload_sha256"):
        assert a.data[name] == b.data[name]
    assert b.data["external_revision"] == "next" and b.data["extensions"] == changed["extensions"]
    assert b.data["imported_at"] != a.data["imported_at"]


@pytest.mark.parametrize("field", ["imported_projection", "source_projection"])
def test_changed_projection_changes_only_its_own_history_hash(field):
    a = history(); b = history(**{field: {"statement": "changed", "extra": [True, None, 1]}})
    changed = [k for k in a.data if a.data[k] != b.data[k]]
    assert changed == ["last_" + field + "_sha256"]


def test_payload_hash_uses_arbitrary_original_bytes_without_decoding_or_format_inference():
    payload = b"\0\xffPK\x03\x04\r\nopaque"; value = history(source_payload=payload)
    assert value.data["last_source_payload_sha256"] == sha256(payload).hexdigest()
    assert value.data["last_source_projection_sha256"] == history().data["last_source_projection_sha256"]


@pytest.mark.parametrize("time", ["2026-09-01t18:00:00Z", "2026-09-01T18:00:00.000123Z", "2024-02-29T00:00:00Z"])
def test_explicit_utc_spelling_is_preserved_using_the_existing_native_time_contract(time):
    assert history(imported_at=time).data["imported_at"] == time


@pytest.mark.parametrize("time", ["2026-02-29T00:00:00Z", "2026-09-01T24:00:00Z", "2026-09-01T18:00:60Z", "2026-09-01T18:00:00", "2026-09-01T18:00:00Z\n"])
def test_invalid_explicit_time_is_not_replaced_by_a_clock(time):
    with patch("time.time", side_effect=AssertionError("clock")), pytest.raises(ImportIdentityError) as caught:
        history(imported_at=time)
    assert caught.value.reason == "invalid_utc_timestamp" and caught.value.pointer == "/imported_at"


@pytest.mark.parametrize("field", ["imported_projection", "source_projection"])
@pytest.mark.parametrize("bad", [{1: "key"}, {"bad~name/": "\ud800"}, {"value": 9007199254740993}, {"value": float("inf")}])
def test_invalid_projected_data_has_a_safe_location_and_no_partial_history(field, bad):
    value = history(); original = value.data
    arguments = dict(mapping_id=MAPPING, imported_projection=LOCAL, source_projection=SOURCE,
                     source_payload=PAYLOAD, imported_at=TIME); arguments[field] = bad
    with no_write_attempts(), pytest.raises(ImportIdentityError) as caught: value.with_import_history(**arguments)
    assert caught.value.code == "SRV090" and caught.value.pointer.startswith("/" + field)
    json.dumps(caught.value.diagnostic(), ensure_ascii=False).encode("utf-8")
    assert value.data == original


def test_cycles_and_foreign_json_values_never_run_conversion_hooks():
    class Foreign:
        def __str__(self): raise AssertionError("conversion")
        def __float__(self): raise AssertionError("numeric conversion")
    cyclic = {}; cyclic["child"] = cyclic
    for value in (cyclic, {"value": Foreign()}):
        with pytest.raises(ImportIdentityError): history(source_projection=value)
    identity = external(extensions={"vendor.opaque": Foreign()})
    with pytest.raises(ImportIdentityError): ExternalIdentity(identity)


def test_legacy_identity_unknown_extensions_are_not_promoted_to_active_history():
    payload = {"mapping_id": MAPPING, "last_source_payload_sha256": "0" * 64, "imported_at": TIME,
               "command": "touch never", "url": "https://unused.invalid/next", "script": "raise RuntimeError()"}
    value = ExternalIdentity(external(extensions={"future.import": payload}))
    with no_write_attempts(), patch("builtins.open", side_effect=AssertionError("no external lookup")):
        assert not value.import_bound and value.data["extensions"]["future.import"] == payload
        refreshed = value.with_import_history(mapping_id="m", imported_projection={}, source_projection={},
            source_payload=b"", imported_at=TIME)
    assert refreshed.data["extensions"] == value.data["extensions"] and refreshed.import_bound
    assert refreshed.data["last_source_payload_sha256"] == sha256(b"").hexdigest()


@pytest.mark.parametrize("mode", ["core", "pyz"])
def test_isolated_runtime_keeps_document_namespaces_extensions_and_failure_contract(tmp_path, mode):
    a = history().data; b = deepcopy(a); b["source_document"] = "different.reqif"
    first = artifact(external_identities=[a]); second = artifact(number=2, external_identities=[b])
    body = '''import json, os, sys
from specroad.exchange import ExternalIdentity, ImportIdentityError, NativeIdentityIndex
from specroad.graph.relations import SourceRelations
def guard(event, args):
    if event.startswith(('socket.', 'subprocess.')) or event in ('os.system', 'os.mkdir', 'os.remove', 'os.rename'):
        raise AssertionError(event)
    if event == 'open':
        mode, flags = args[1], args[2]
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
            raise AssertionError(event)
sys.addaudithook(guard)
'''
    body += 'sources=[SourceRelations(b) for b in ' + repr([artifact_bytes(first), artifact_bytes(second)]) + ']\n'
    body += 'index=NativeIdentityIndex(sources)\n'
    body += 'matches=[index.lookup("artifact", *ExternalIdentity(v).key) for v in ' + repr([a, b]) + ']\n'
    body += 'try:\n    NativeIdentityIndex(sources + sources[:1])\nexcept ImportIdentityError as error:\n    diagnostic=error.diagnostic()\n'
    body += 'print(json.dumps({"matches":matches,"code":diagnostic["code"],"exit_code":diagnostic["exit_code"]}))\n'
    if mode == "core": result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / "distribution")
        result = run_python(["-I", "-S", "-B", "-c", "import sys;sys.path.insert(0," + repr(str(package)) + ")\n" + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed["code"] == "SRV147" and observed["exit_code"] == 3
    assert [v["identity"] for v in observed["matches"]] == [a, b]
    assert [v["artifact_id"] for v in observed["matches"]] == [first["id"], second["id"]]
