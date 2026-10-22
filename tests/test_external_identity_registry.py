"""Bound non-artifact identities, namespace separation and read-only projections."""
from copy import deepcopy
import json

import pytest

from specroad.mappings import (ExchangeMapping, ExternalIdentityRegistry, MappingError,
                               select_mapping, select_registries)
from specroad.validation import ModelDocument
from support.artifacts import artifact_bytes
from support.exchange_mappings import mapping_value, fields_value, entry_value, registry_value, registry, selected
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from support.targets import model, SCOPE


def test_all_four_classes_are_distinct_namespaces_and_preserve_entries():
    mapping = selected().resource; resource = registry(mapping)
    with no_write_attempts():
        index = select_registries([resource], bindings=[resource.binding()], mappings=[mapping])
        for entry in resource.data["entries"]:
            result = index.lookup(entry["object_class"], "supplier", "document-a", "same-id")
            assert result == {"registry": resource.binding(), "mapping": mapping.binding(), "entry": entry}


def test_source_document_and_system_namespaces_are_exact_and_missing_lookup_creates_nothing():
    mapping = selected().resource
    entries = [entry_value(), entry_value(source_document="document-b"), entry_value(source_system="other")]
    resource = registry(mapping, entries=entries)
    index = select_registries([resource], bindings=[resource.binding()], mappings=[mapping])
    for entry in entries:
        assert index.lookup("type", entry["source_system"], entry["source_document"], "same-id")["entry"] == entry
    with no_write_attempts():
        assert index.lookup("type", "supplier", "document-c", "same-id") is None
        assert index.lookup("type", "Supplier", "document-a", "same-id") is None
    assert resource.data["entries"] == entries


def test_revision_is_data_and_cannot_disambiguate_duplicate_identity():
    mapping = selected().resource
    value = registry_value(mapping, entries=[entry_value(), entry_value(external_revision="revision-2")])
    with pytest.raises(MappingError) as failure: ExternalIdentityRegistry(artifact_bytes(value))
    assert failure.value.reason == "mapping_duplicate_key"
    resource = registry(mapping, entries=[entry_value(external_revision="revision-2")])
    index = select_registries([resource], bindings=[resource.binding()], mappings=[mapping])
    assert index.lookup("type", "supplier", "document-a", "same-id")["entry"]["external_revision"] == "revision-2"


def test_joint_registry_collection_rejects_collisions_before_any_lookup():
    mapping = selected().resource; a = registry(mapping)
    b = registry(mapping, mapping_id="other:registry")
    with pytest.raises(MappingError) as failure:
        select_registries([a, b], bindings=[a.binding(), b.binding()], mappings=[mapping])
    assert failure.value.reason == "mapping_duplicate_registry_entry" and failure.value.path == b.key


def test_two_nonoverlapping_registries_keep_their_own_hash_bindings():
    mapping = selected().resource; a = registry(mapping)
    b = registry(mapping, mapping_id="other:registry", entries=[entry_value(source_document="document-b")])
    index = select_registries([b, a], bindings=[a.binding(), b.binding()], mappings=[mapping])
    result = index.lookup("type", "supplier", "document-b", "same-id")
    assert result["registry"] == b.binding()
    result["entry"]["data"]["nested"].clear()
    assert index.lookup("type", "supplier", "document-b", "same-id")["entry"] == b.data["entries"][0]


@pytest.mark.parametrize("mutation", ["missing", "wrong_hash", "wrong_version", "self_reference"])
def test_registry_requires_actual_rules_with_exact_identity_and_hash(mutation):
    mapping = selected().resource; value = registry_value(mapping)
    if mutation == "wrong_hash": value["mapping"]["sha256"] = "0" * 64
    elif mutation == "wrong_version": value["mapping"]["mapping_version"] = "2.0.0"
    elif mutation == "self_reference": value["mapping_id"] = mapping.mapping_id
    with pytest.raises(MappingError):
        resource = ExternalIdentityRegistry(artifact_bytes(value))
        select_registries([resource], bindings=[resource.binding()], mappings=[] if mutation == "missing" else [mapping])


def test_registry_own_expected_hash_is_also_required():
    mapping = selected().resource; resource = registry(mapping); binding = resource.binding()
    binding["sha256"] = "0" * 64
    with pytest.raises(MappingError) as failure:
        select_registries([resource], bindings=[binding], mappings=[mapping])
    assert failure.value.reason == "mapping_hash_mismatch"


@pytest.mark.parametrize("mutation", ["class", "missing_revision", "empty_revision", "nonobject_data", "extension", "loader"])
def test_registry_rejects_bad_entries_and_executable_controls(mutation):
    mapping = selected().resource; value = registry_value(mapping); entry = value["entries"][0]
    if mutation == "class": entry["object_class"] = "artifact"
    elif mutation == "missing_revision": del entry["external_revision"]
    elif mutation == "empty_revision": entry["external_revision"] = ""
    elif mutation == "nonobject_data": entry["data"] = []
    elif mutation == "extension": entry["extensions"] = {"not_namespaced": 1}
    else: value["loader"] = "https://unused.invalid/registry"
    with pytest.raises(MappingError) as failure: ExternalIdentityRegistry(artifact_bytes(value))
    assert failure.value.code == "SRV090" and failure.value.exit_code == 3 and failure.value.pointer


def test_registry_change_changes_model_root_but_not_mapping_rules():
    mapping = selected().resource; a = registry(mapping); changed = a.data
    changed["entries"].append(entry_value(external_id="new-id"))
    b = ExternalIdentityRegistry(artifact_bytes(changed))
    assert a.sha256 != b.sha256 and a.data["mapping"] == b.data["mapping"] == mapping.binding()
    def project(resource):
        supplied = model([], resource_files=[ModelDocument("mappings/rules.json", mapping.source_bytes),
            ModelDocument("mappings/identities.json", resource.source_bytes)])
        return supplied.manifest(supplied.artifacts, SCOPE).sha256
    assert project(a) != project(b)
    assert ExchangeMapping(mapping.source_bytes).sha256 == mapping.sha256


def test_generic_legacy_mapping_is_preserved_but_not_selected_as_v1():
    legacy = artifact_bytes({"schema_version": "0.2.0", "mapping_id": "old", "version": "1.0.0", "settings": {"field": "source"}})
    supplied = model([], resource_files=[ModelDocument("mappings/old.json", legacy)])
    first = supplied.manifest(supplied.artifacts, SCOPE).sha256
    with pytest.raises(MappingError): ExchangeMapping(legacy)
    assert supplied.source_files["mappings/old.json"] == legacy
    assert supplied.manifest(supplied.artifacts, SCOPE).sha256 == first


@pytest.mark.parametrize("mode", ["core", "pyz"])
def test_mapping_and_registry_are_available_in_isolated_read_only_runtimes(tmp_path, mode):
    mapping = selected().resource; resource = registry(mapping)
    expected = {"projection": selected().artifact("Requirement", fields_value()),
        "entry": {"registry": resource.binding(), "mapping": mapping.binding(), "entry": entry_value()}}
    body = '''import json, os, sys
from specroad.mappings import ExchangeMapping, ExternalIdentityRegistry, select_mapping, select_registries
def guard(event, args):
    if event.startswith(('socket.', 'subprocess.')) or event in ('os.system', 'os.mkdir', 'os.remove', 'os.rename'):
        raise AssertionError(event)
    if event == 'open':
        mode, flags = args[1], args[2]
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
            raise AssertionError(event)
sys.addaudithook(guard)
'''
    body += 'mapping=ExchangeMapping(' + repr(mapping.source_bytes) + ')\n'
    body += 'registry=ExternalIdentityRegistry(' + repr(resource.source_bytes) + ')\n'
    body += 'mapper=select_mapping([mapping],key=' + repr(mapping.key) + ',expected_sha256=' + repr(mapping.sha256) + ')\n'
    body += 'registries=select_registries([registry],bindings=' + repr([resource.binding()]) + ',mappings=[mapping])\n'
    body += 'print(json.dumps({"projection":mapper.artifact("Requirement",' + repr(fields_value()) + '),"entry":registries.lookup("type","supplier","document-a","same-id")}))\n'
    if mode == "core": result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / "distribution")
        result = run_python(["-I", "-S", "-B", "-c", "import sys;sys.path.insert(0," + repr(str(package)) + ")\n" + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
