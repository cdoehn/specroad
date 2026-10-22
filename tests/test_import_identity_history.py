"""Native identity preservation and distinct projection/payload provenance."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
from unittest.mock import patch

import pytest

from specroad.exchange import ExternalIdentity, ImportIdentityError, NativeIdentityIndex
from specroad.graph.relations import Relation, SourceRelations
from specroad.model.identity_values import artifact_identity
from support.artifacts import artifact_bytes
from support.exchange_mappings import selected, fields_value
from support.import_identities import history, TIME, MAPPING, LOCAL, SOURCE, PAYLOAD
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from support.relations import artifact, edge, external
from support.targets import model, SCOPE


@pytest.mark.parametrize("revision", [None, "", "007", "revision:東京"])
def test_legacy_identity_stays_unbound_without_inventing_revision_or_history(revision):
    data = external()
    if revision is not None: data["external_revision"] = revision
    with no_write_attempts(): value = ExternalIdentity(data)
    assert value.data == data and not value.import_bound
    assert value.key == ("reqif", "supplier.reqif", "_req-10")


def test_history_uses_exact_three_inputs_and_explicit_utc_without_mutating_identity():
    initial = ExternalIdentity(external(external_revision="007"))
    with no_write_attempts(), patch("time.time", side_effect=AssertionError("clock")):
        value = initial.with_import_history(mapping_id=MAPPING, imported_projection=LOCAL,
            source_projection=SOURCE, source_payload=PAYLOAD, imported_at=TIME)
    assert value.data == {**initial.data, "mapping_id": MAPPING, "imported_at": TIME,
        "last_imported_projection_sha256": sha256(b'{"extra":[true,null,1],"statement":"local"}').hexdigest(),
        "last_source_projection_sha256": sha256(b'{"extra":[true,null,1],"statement":"external"}').hexdigest(),
        "last_source_payload_sha256": sha256(PAYLOAD).hexdigest()}
    assert value.key == initial.key and value.import_bound and not initial.import_bound


def test_projection_member_order_is_irrelevant_but_payload_bytes_remain_distinct():
    a = history(); b = history(imported_projection=dict(reversed(list(LOCAL.items()))),
        source_projection=dict(reversed(list(SOURCE.items()))), source_payload=PAYLOAD.strip())
    for key in ("last_imported_projection_sha256", "last_source_projection_sha256"):
        assert a.data[key] == b.data[key]
    assert a.data["last_source_payload_sha256"] != b.data["last_source_payload_sha256"]


@pytest.mark.parametrize("value", [None, False, 1, "1", [], {}])
def test_explicit_projection_values_are_not_conflated(value):
    actual = history(source_projection={"value": value}).data["last_source_projection_sha256"]
    encoded = json.dumps({"value": value}, separators=(",", ":")).encode()
    assert actual == sha256(encoded).hexdigest()


def test_refreshing_history_preserves_external_key_revision_extensions_and_prior_value():
    a = history(); before = a.data
    b = a.with_import_history(mapping_id="next:rules@2.0.0", imported_projection={"value": 2},
        source_projection={"value": 2}, source_payload=b"new payload", imported_at="2026-09-02T00:00:00Z")
    assert a.data == before
    for key in ("source_system", "source_document", "external_id", "external_revision", "extensions"):
        assert b.data[key] == before[key]
    assert b.data["mapping_id"] == "next:rules@2.0.0"
    assert b.data["last_source_payload_sha256"] == sha256(b"new payload").hexdigest()
    assert b.data["last_source_projection_sha256"] == b.data["last_imported_projection_sha256"]
    assert b.data["imported_at"] == "2026-09-02T00:00:00Z"


def test_actual_mapping_output_can_be_recorded_on_artifact_and_relation_candidates():
    mapper = selected(); projection = mapper.artifact("Requirement", fields_value())["artifact"]
    identity = ExternalIdentity(external()).with_import_history(mapping_id=mapper.resource.key,
        imported_projection=projection, source_projection=projection,
        source_payload=b"explicit source payload", imported_at=TIME)
    relation = edge(external_identities=[identity.data], extensions={"vendor.edge": [None, "opaque"]})
    native = artifact(external_identities=[identity.data], relations=[relation], **projection)
    raw = artifact_bytes(native); source = SourceRelations(raw)
    index = NativeIdentityIndex([source])
    assert source.source_bytes == raw and source.data == native
    assert index.lookup("artifact", *identity.key)["artifact_id"] == native["id"]
    assert index.lookup("relation", *identity.key)["relation_id"] == relation["relation_id"]
    assert source.relations[0].data == relation


def test_native_model_roundtrip_keeps_history_and_includes_it_in_model_root():
    value = history().data
    native = artifact(external_identities=[value], relations=[edge(external_identities=[value])])
    supplied = model([native]); root = supplied.manifest(supplied.artifacts, SCOPE).sha256
    source = SourceRelations(supplied.documents[0].content)
    assert source.data == native and source.data["revision"] == 1
    assert source.relations[0].data["external_identities"] == [value]
    altered = deepcopy(native); altered["external_identities"][0]["imported_at"] = "2026-09-02T00:00:00Z"
    changed = model([altered])
    assert changed.manifest(changed.artifacts, SCOPE).sha256 != root
    assert supplied.manifest(supplied.artifacts, SCOPE).sha256 == root


def test_owned_identity_ignores_mutations_of_inputs_and_observations():
    data = history().data; before = deepcopy(data); value = ExternalIdentity(data)
    data["extensions"]["vendor.opaque"]["original"].clear()
    exposed = value.data; exposed["extensions"].clear()
    assert value.data == before
    with pytest.raises(FrozenInstanceError): value._encoded = b"{}"


@pytest.mark.parametrize("field", ["mapping_id", "last_imported_projection_sha256", "last_source_projection_sha256",
                                  "last_source_payload_sha256", "imported_at"])
def test_incomplete_stored_history_is_not_repaired(field):
    value = history().data; del value[field]
    with pytest.raises(ImportIdentityError) as caught: ExternalIdentity(value)
    assert caught.value.reason == "incomplete_import_binding"
    assert caught.value.code == "SRV090" and caught.value.exit_code == 3


@pytest.mark.parametrize("changes", [
    {"source_system": ""}, {"source_document": "  "}, {"external_id": None}, {"external_revision": None},
    {"external_revision": 7}, {"mapping_id": ""}, {"imported_at": "2026-09-01T18:00:00+00:00"},
    {"last_source_payload_sha256": "A" * 64}, {"extensions": {"plain": True}}, {"loader": "file:///secret"}])
def test_invalid_native_identity_fields_use_structured_errors(changes):
    data = history().data; data.update(changes)
    with pytest.raises(ImportIdentityError) as caught: ExternalIdentity(data)
    assert caught.value.diagnostic()["code"] == "SRV090" and caught.value.exit_code == 3


@pytest.mark.parametrize("changes", [
    {"source_payload": "text"}, {"source_payload": bytearray(b"bytes")}, {"imported_projection": []},
    {"source_projection": None}, {"source_projection": {"value": float("nan")}},
    {"source_projection": {"value": object()}}, {"imported_at": "yesterday"}, {"mapping_id": None}])
def test_bad_history_inputs_leave_original_identity_unchanged(changes):
    value = ExternalIdentity(external()); before = value.data
    arguments = dict(mapping_id=MAPPING, imported_projection=LOCAL, source_projection=SOURCE,
                     source_payload=PAYLOAD, imported_at=TIME)
    arguments.update(changes)
    with no_write_attempts(), pytest.raises(ImportIdentityError): value.with_import_history(**arguments)
    assert value.data == before and not value.import_bound


def test_legacy_mapping_labels_keep_the_existing_relation_contract():
    data = history(mapping_id="m").data
    assert ExternalIdentity(data).data == data
    assert Relation(artifact_identity(artifact()), edge(external_identities=[data])).data["external_identities"] == [data]


@pytest.mark.parametrize("mode", ["core", "pyz"])
def test_native_identity_lookup_is_packaged_for_isolated_runtimes(tmp_path, mode):
    value = history().data; source = artifact(external_identities=[value])
    body = '''import json
from specroad.exchange import ExternalIdentity, NativeIdentityIndex
from specroad.graph.relations import SourceRelations
'''
    body += "identity=ExternalIdentity(" + repr(value) + ")\n"
    body += "index=NativeIdentityIndex([SourceRelations(" + repr(artifact_bytes(source)) + ")])\n"
    body += "print(json.dumps(index.lookup('artifact', *identity.key)))\n"
    if mode == "core": result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / "distribution")
        result = run_python(["-I", "-S", "-B", "-c", "import sys;sys.path.insert(0," + repr(str(package)) + ")\n" + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"object_class": "artifact", "artifact_id": source["id"],
        "relation_id": None, "path": artifact_identity(source).path, "identity": value}
