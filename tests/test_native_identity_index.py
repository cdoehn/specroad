"""Repeated import identity matching over supplied native source bytes."""
from copy import deepcopy
import json
from unittest.mock import patch

import pytest

from specroad.exchange import ExternalIdentity, ImportIdentityError, NativeIdentityIndex
from specroad.graph.relations import SourceRelations
from support.artifacts import artifact_bytes
from support.import_identities import history
from support.read_only import no_write_attempts
from support.relations import artifact, edge, external, aid, rid


def sources(*values):
    return [SourceRelations(artifact_bytes(value)) for value in values]


def test_repeated_import_and_new_external_revision_find_same_native_owner():
    identity = history(); native = artifact(external_identities=[identity.data])
    index = NativeIdentityIndex(sources(native))
    current = index.lookup("artifact", *identity.key)
    next_revision = ExternalIdentity({**identity.data, "external_revision": "008"})
    with no_write_attempts(), patch("secrets.token_bytes", side_effect=AssertionError("new identity")):
        assert index.lookup("artifact", *identity.key) == current
        assert index.lookup("artifact", *next_revision.key) == current
    assert current["artifact_id"] == native["id"] and current["identity"] == identity.data


def test_artifact_and_relation_with_same_external_key_have_distinct_owners():
    identity = history(); relation = edge(number=5, external_identities=[identity.data])
    index = NativeIdentityIndex(sources(artifact(external_identities=[identity.data], relations=[relation])))
    assert index.lookup("artifact", *identity.key)["relation_id"] is None
    assert index.lookup("relation", *identity.key)["relation_id"] == rid(5)


@pytest.mark.parametrize("field", ["source_system", "source_document", "external_id"])
def test_equal_external_names_in_other_source_namespaces_are_distinct(field):
    first = external(); second = {**first, field: "other"}
    index = NativeIdentityIndex(sources(artifact(external_identities=[first]), artifact(number=2, external_identities=[second])))
    assert index.lookup("artifact", *ExternalIdentity(first).key)["artifact_id"] == aid()
    assert index.lookup("artifact", *ExternalIdentity(second).key)["artifact_id"] == aid(number=2)


def test_aliases_on_one_object_resolve_to_the_same_owner_without_collapsing_history():
    a = history().data; b = {**a, "source_document": "another.reqif", "external_revision": "003"}
    index = NativeIdentityIndex(sources(artifact(external_identities=[a, b])))
    assert index.lookup("artifact", *ExternalIdentity(a).key)["artifact_id"] == aid()
    assert index.lookup("artifact", *ExternalIdentity(b).key)["identity"] == b


@pytest.mark.parametrize("kind", ["artifact", "relation"])
def test_duplicate_external_identity_across_objects_rejects_ambiguous_inventory(kind):
    a = external(external_revision="1"); b = external(external_revision="2")
    if kind == "artifact": values = [artifact(external_identities=[a]), artifact(number=2, external_identities=[b])]
    else: values = [artifact(relations=[edge(external_identities=[a])]),
                    artifact(number=2, relations=[edge(number=2, external_identities=[b])])]
    with no_write_attempts(), pytest.raises(ImportIdentityError) as caught: NativeIdentityIndex(sources(*values))
    assert caught.value.code == "SRV147" and caught.value.exit_code == 3
    assert caught.value.reason == "duplicate_external_" + kind + "_identity"
    assert caught.value.path == SourceRelations(artifact_bytes(values[1])).identity.path
    assert caught.value.pointer.endswith("/external_identities/0")


def test_one_artifact_cannot_repeat_external_key_with_different_revision():
    with pytest.raises(ImportIdentityError) as caught:
        NativeIdentityIndex(sources(artifact(external_identities=[external(external_revision="1"), external(external_revision="2")])))
    assert caught.value.reason == "duplicate_external_identity" and caught.value.code == "SRV147"


@pytest.mark.parametrize("values,reason", [
    ([artifact(), artifact()], "duplicate_artifact_id"),
    ([artifact(relations=[edge()]), artifact(number=2, relations=[edge()])], "duplicate_relation_id"),
    ([artifact(), artifact(project="OTHER")], "mixed_project_prefix")])
def test_native_identity_ambiguity_is_rejected_even_without_external_identities(values, reason):
    with pytest.raises(ImportIdentityError) as caught: NativeIdentityIndex(sources(*values))
    assert caught.value.reason == reason


def test_declared_source_path_cannot_redirect_native_owner():
    source = SourceRelations(artifact_bytes(artifact()), path="spec/requirements/other.json")
    with pytest.raises(ImportIdentityError) as caught: NativeIdentityIndex([source])
    assert caught.value.reason == "artifact_path_identity_mismatch"


@pytest.mark.parametrize("identities", [[{}], [external(mapping_id="m")], [external(extensions={"plain": 0})]])
def test_artifact_identity_fields_are_validated_at_import_boundary(identities):
    source = SourceRelations(artifact_bytes(artifact(external_identities=identities)))
    with pytest.raises(ImportIdentityError) as caught: NativeIdentityIndex([source])
    assert caught.value.code == "SRV090" and caught.value.pointer.startswith("/external_identities/0")


def test_unmapped_and_absent_identities_create_nothing_and_require_no_artifact_defaults():
    no_key = artifact(); empty = artifact(number=2, external_identities=[])
    original = deepcopy([no_key, empty]); index = NativeIdentityIndex(sources(no_key, empty))
    with no_write_attempts():
        assert index.lookup("artifact", "reqif", "supplier.reqif", "new") is None
        assert NativeIdentityIndex([]).lookup("relation", "reqif", "supplier.reqif", "new") is None
    assert [no_key, empty] == original


def test_lookup_observations_and_source_reinitialization_cannot_replace_index_bindings():
    identity = history(); values = sources(artifact(external_identities=[identity.data])); source = values[0]
    index = NativeIdentityIndex(values); expected = index.lookup("artifact", *identity.key)
    observed = index.lookup("artifact", *identity.key); observed["identity"]["extensions"].clear()
    observed["artifact_id"] = aid(number=99)
    source.__init__(artifact_bytes(artifact(number=2, external_identities=[identity.data])))
    values.clear()
    assert index.lookup("artifact", *identity.key) == expected


def test_passive_identity_paths_extensions_and_source_bytes_remain_unchanged():
    identity = external(source_document="file:///private/missing", extensions={"vendor.opaque": {
        "script": "import os; os.system('never')", "url": "https://unused.invalid", "values": [None, "e\u0301", "東京"]}})
    value = artifact(external_identities=[identity], extensions={"vendor.unknown": {"preserve": True}})
    raw = json.dumps(value, indent=3, ensure_ascii=True).encode() + b"\n"; source = SourceRelations(raw)
    with no_write_attempts(), patch("builtins.open", side_effect=AssertionError("no lookup I/O")):
        index = NativeIdentityIndex([source])
        result = index.lookup("artifact", *ExternalIdentity(identity).key)
    assert result["identity"] == identity and source.source_bytes == raw and source.data == value


@pytest.mark.parametrize("arguments", [("type", "sys", "doc", "id"), (None, "sys", "doc", "id"),
    ("artifact", "", "doc", "id"), ("relation", "sys", None, "id"), ("artifact", "sys", "doc", 1)])
def test_invalid_lookup_is_not_an_unmatched_identity(arguments):
    with pytest.raises(ImportIdentityError) as caught: NativeIdentityIndex([]).lookup(*arguments)
    assert caught.value.code == "SRV090" and caught.value.exit_code == 3


@pytest.mark.parametrize("value", [None, {}, "paths", [b"{}"], [artifact()]])
def test_index_requires_explicit_native_sources_not_paths_or_registry_values(value):
    with pytest.raises(ImportIdentityError): NativeIdentityIndex(value)
