"""Exact external namespaces, native source binding and failure atomicity."""
import json
from unittest.mock import patch

import pytest

from specroad.exchange import ExternalIdentity, ImportIdentityError, NativeIdentityIndex
from specroad.graph.relations import SourceRelations
from specroad.model.identity_values import artifact_identity
from support.artifacts import artifact_bytes
from support.import_identities import history
from support.read_only import no_write_attempts, inventory
from support.relations import artifact, edge, external, aid, rid


def source_for(kind, identity, number=1, **changes):
    native = artifact(number=number, **changes)
    if kind == "artifact": native["external_identities"] = [identity]
    else: native["relations"] = [edge(number=number, external_identities=[identity])]
    return SourceRelations(artifact_bytes(native))


@pytest.mark.parametrize("kind", ["artifact", "relation"])
@pytest.mark.parametrize("field", ["source_system", "source_document", "external_id"])
@pytest.mark.parametrize("pair", [("Document-A", "document-a"), ("a", " a "), ("é", "e\u0301")])
def test_literal_external_names_are_not_casefolded_trimmed_or_unicode_normalized(kind, field, pair):
    a = {**external(), field: pair[0]}; b = {**external(), field: pair[1]}
    index = NativeIdentityIndex([source_for(kind, a), source_for(kind, b, 2)])
    first = index.lookup(kind, *ExternalIdentity(a).key); second = index.lookup(kind, *ExternalIdentity(b).key)
    assert first["artifact_id"] == aid() and second["artifact_id"] == aid(number=2)
    assert first["identity"] == a and second["identity"] == b
    if kind == "relation": assert (first["relation_id"], second["relation_id"]) == (rid(), rid(2))


@pytest.mark.parametrize("kind", ["artifact", "relation"])
def test_reordered_sources_and_equal_ids_in_distinct_documents_keep_separate_history(kind):
    a = history().data; b = history(source_payload=b"other document").data
    b.update(source_document="supplier-b.reqif", external_revision="different")
    originals = [source_for(kind, a), source_for(kind, b, 2)]
    index = NativeIdentityIndex(originals); reverse = NativeIdentityIndex(list(reversed(originals)))
    for identity, owner in ((a, aid()), (b, aid(number=2))):
        key = ExternalIdentity(identity).key
        assert index.lookup(kind, *key) == reverse.lookup(kind, *key)
        assert index.lookup(kind, *key)["artifact_id"] == owner
        assert index.lookup(kind, *key)["identity"] == identity
    assert index.lookup(kind, "reqif", "supplier-c.reqif", "_req-10") is None


def test_native_artifact_types_do_not_disambiguate_duplicate_external_artifact_identity():
    identity = history().data
    records = [source_for("artifact", identity),
               SourceRelations(artifact_bytes(artifact("document", external_identities=[identity])))]
    with pytest.raises(ImportIdentityError) as caught: NativeIdentityIndex(records)
    assert caught.value.reason == "duplicate_external_artifact_identity" and caught.value.code == "SRV147"


@pytest.mark.parametrize("kind", ["artifact", "relation"])
def test_changed_mapping_revision_or_history_cannot_hide_a_duplicate_external_key(kind):
    a = history().data; b = history(mapping_id="other:rules@2.0.0", source_payload=b"changed").data
    b["external_revision"] = "next"
    with pytest.raises(ImportIdentityError) as caught:
        NativeIdentityIndex([source_for(kind, a), source_for(kind, b, 2)])
    assert caught.value.code == "SRV147" and caught.value.exit_code == 3
    assert caught.value.path == artifact_identity(artifact(number=2)).path
    assert caught.value.pointer == ("" if kind == "artifact" else "/relations/0") + "/external_identities/0"


def test_failed_index_reinitialization_keeps_prior_complete_bindings_without_partial_entries():
    old = external(source_document="retained.reqif")
    index = NativeIdentityIndex([source_for("artifact", old)])
    new = external(source_document="new.reqif")
    expected = index.lookup("artifact", *ExternalIdentity(old).key)
    with pytest.raises(ImportIdentityError):
        index.__init__([source_for("artifact", new, 2), source_for("artifact", new, 3)])
    assert index.lookup("artifact", *ExternalIdentity(old).key) == expected
    assert index.lookup("artifact", *ExternalIdentity(new).key) is None


def test_cache_fields_cannot_redirect_owner_or_hide_bytes_and_relations():
    identity = history().data; original = source_for("relation", identity)
    object.__setattr__(original, "identity", artifact_identity(artifact(number=99)))
    object.__setattr__(original, "relations", ())
    object.__setattr__(original, "validation_scope", "invented-approval")
    index = NativeIdentityIndex([original])
    match = index.lookup("relation", *ExternalIdentity(identity).key)
    assert match["artifact_id"] == aid() and match["relation_id"] == rid()
    assert match["identity"] == identity


@pytest.mark.parametrize("value", [False, 7, [], {}, "\ud800", "", "../other.json", "/absolute.json", "spec/./other.json", "spec\\other.json"])
def test_invalid_native_source_paths_fail_with_serializable_diagnostics(value):
    source = SourceRelations(artifact_bytes(artifact()), path=value)
    with pytest.raises(ImportIdentityError) as caught: NativeIdentityIndex([source])
    assert caught.value.code == "SRV090" and caught.value.exit_code == 3
    json.dumps(caught.value.diagnostic(), ensure_ascii=False).encode("utf-8")


def test_external_document_paths_remain_passive_while_native_source_path_is_exact():
    identity = external(source_document="../../outside.reqif", extensions={"vendor.path": "file:///private"})
    original = source_for("artifact", identity)
    source = SourceRelations(original.source_bytes, path=original.identity.path)
    with no_write_attempts(), patch("builtins.open", side_effect=AssertionError("no discovery")):
        match = NativeIdentityIndex([source]).lookup("artifact", *ExternalIdentity(identity).key)
    assert match["path"] == source.identity.path and match["identity"] == identity


def test_foreign_path_and_byte_hooks_are_not_executed_during_index_reconstruction():
    class ForeignPath:
        def __eq__(self, other): raise AssertionError("path comparison hook")
        def __str__(self): raise AssertionError("path conversion hook")
        def __fspath__(self): raise AssertionError("path resolution hook")
    class ForeignBytes(bytes):
        def decode(self, *args, **kwargs): raise AssertionError("byte decoding hook")
    source = SourceRelations(artifact_bytes(artifact()), path=ForeignPath())
    with pytest.raises(ImportIdentityError): NativeIdentityIndex([source])
    source = SourceRelations(artifact_bytes(artifact()))
    object.__setattr__(source, "source_bytes", ForeignBytes(source.source_bytes))
    with pytest.raises(ImportIdentityError): NativeIdentityIndex([source])


def test_foreign_collections_and_source_subclasses_are_not_evaluated():
    class ForeignCollection:
        def __iter__(self): raise AssertionError("iterator hook")
    class ForeignSource(SourceRelations):
        @property
        def source_bytes(self): raise AssertionError("source property hook")
    for value in (ForeignCollection(), [object.__new__(ForeignSource)]):
        with pytest.raises(ImportIdentityError): NativeIdentityIndex(value)


@pytest.mark.parametrize("raw", [b"\xff", b'{\n "id":', b'{} {}', b'{"id":"a","id":"b"}', b'{"\\ud800":0}'])
def test_corrupted_cached_source_bytes_keep_structured_reader_locations(raw):
    # Revalidation must use the bytes, not the formerly valid cached identity.
    source = source_for("artifact", external()); object.__setattr__(source, "source_bytes", raw)
    object.__setattr__(source, "path", artifact_identity(artifact()).path)
    with pytest.raises(ImportIdentityError) as caught: NativeIdentityIndex([source])
    diagnostic = caught.value.diagnostic()
    assert diagnostic["path"] == source.path and diagnostic["exit_code"] == 3 and diagnostic["code"] == "SRV090"
    json.dumps(diagnostic, ensure_ascii=False).encode("utf-8")
    if raw == b"\xff": assert diagnostic["position"] == 0
    if raw == b'{\n "id":':
        assert diagnostic["line"] == 2 and diagnostic["column"] == 7 and diagnostic["position"] == 8
    if raw == b'{"id":"a","id":"b"}': assert diagnostic["pointer"] == "/id"
    if raw == b'{"\\ud800":0}': assert diagnostic["pointer"] == ""


def test_success_unknown_identity_and_failure_leave_original_project_bytes_and_modes(tmp_path):
    identity = history().data; record = source_for("relation", identity)
    path = tmp_path / "native.json"; path.write_bytes(record.source_bytes); path.chmod(0o640)
    before = inventory(tmp_path); raw = path.read_bytes()
    source = SourceRelations(raw)
    with no_write_attempts():
        index = NativeIdentityIndex([source]); assert index.lookup("relation", *ExternalIdentity(identity).key)
        assert index.lookup("artifact", *ExternalIdentity(identity).key) is None
        with pytest.raises(ImportIdentityError): NativeIdentityIndex([source, source])
    assert inventory(tmp_path) == before and source.source_bytes == raw
