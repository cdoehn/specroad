"""Exact registry collection bindings, observation ownership and legacy boundaries."""
from copy import deepcopy
import json

import pytest

from specroad.mappings import ExchangeMapping, ExternalIdentityRegistry, MappingError, select_registries
from specroad.validation import ModelDocument
from support.artifacts import artifact_bytes
from support.exchange_mappings import entry_value, mapping_value, registry, registry_value, selected
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.targets import SCOPE, model


def lookup(index, **changes):
    row = entry_value(**changes)
    return index.lookup(*(row[k] for k in ("object_class", "source_system", "source_document", "external_id")))


@pytest.mark.parametrize("location,field", [("root", "mapping"), ("root", "entries"),
    ("binding", "sha256"), ("binding", "mapping_version"), ("entry", "external_id"), ("entry", "data")])
@pytest.mark.parametrize("mutation", ["missing", "control", "nonobject"])
def test_registry_control_objects_are_closed_and_required(location, field, mutation):
    value = registry_value(selected().resource)
    node = value if location == "root" else value["mapping"] if location == "binding" else value["entries"][0]
    if mutation == "missing":
        del node[field]
    elif mutation == "control":
        node["loader"] = "https://unused.invalid/secret-loader"
    elif location == "root":
        value = []
    elif location == "binding":
        value["mapping"] = []
    else:
        value["entries"][0] = None
    with no_write_attempts(), pytest.raises(MappingError) as caught:
        ExternalIdentityRegistry(artifact_bytes(value))
    assert caught.value.code == "SRV090" and caught.value.exit_code == 3
    if mutation == "missing":
        assert caught.value.reason == "mapping_missing_field"
        assert caught.value.pointer.endswith("/" + field)
    if mutation == "control":
        assert caught.value.reason == "mapping_unknown_field"
    assert "secret-loader" not in json.dumps(caught.value.diagnostic())


@pytest.mark.parametrize("field,bad", [("source_system", ""), ("source_document", None),
    ("external_id", 1), ("external_revision", False), ("data", None), ("extensions", [])])
def test_registry_entries_do_not_default_or_coerce_identity_and_passive_data(field, bad):
    value = registry_value(selected().resource, entries=[entry_value(**{field: bad})])
    with pytest.raises(MappingError) as caught:
        ExternalIdentityRegistry(artifact_bytes(value))
    assert caught.value.pointer == "/entries/0/" + field


@pytest.mark.parametrize("bad", [None, (), {}, [None], [{1: "value"}], [{"\ud800": "value"}]])
def test_selection_binding_errors_remain_machine_readable_for_direct_python_inputs(bad):
    mapping = selected().resource
    resource = registry(mapping)
    with pytest.raises(MappingError) as caught:
        select_registries([resource], bindings=bad, mappings=[mapping])
    assert caught.value.code == "SRV090" and caught.value.exit_code == 3
    json.dumps(caught.value.diagnostic(), ensure_ascii=False).encode("utf-8")


def test_selection_binding_rejects_a_bad_unicode_extra_key_without_echoing_it():
    mapping = selected().resource
    resource = registry(mapping)
    binding = {**resource.binding(), "\ud800": "hidden"}
    with pytest.raises(MappingError) as caught:
        select_registries([resource], bindings=[binding], mappings=[mapping])
    assert caught.value.reason == "mapping_invalid_unicode"
    assert caught.value.pointer == "/bindings/0"
    json.dumps(caught.value.diagnostic(), ensure_ascii=False).encode("utf-8")


def test_registry_entry_arrays_and_exact_own_versions_do_not_have_fallbacks():
    mapping = selected().resource
    resource = registry(mapping)
    for entries in (None, {}):
        with pytest.raises(MappingError) as caught:
            registry(mapping, entries=entries)
        assert caught.value.reason == "mapping_array_required"
    binding = {**resource.binding(), "mapping_version": "2.0.0"}
    with pytest.raises(MappingError) as caught:
        select_registries([resource], bindings=[binding], mappings=[mapping])
    assert caught.value.reason == "mapping_resource_missing"


def test_empty_selection_and_unselected_registries_do_not_discover_or_import_entries():
    mapping = selected().resource
    first = registry(mapping)
    unselected = registry(mapping, mapping_id="other:registry", entries=[entry_value(), entry_value(external_id="only-unselected")])
    empty = select_registries([first, unselected], bindings=[], mappings=[mapping])
    assert empty.resources == () and lookup(empty) is None
    index = select_registries([unselected, first], bindings=[first.binding()], mappings=[mapping])
    assert lookup(index)["registry"] == first.binding()
    assert lookup(index, external_id="only-unselected") is None


@pytest.mark.parametrize("side", ["resources", "mappings", "bindings"])
def test_duplicate_registry_collections_or_selections_are_rejected_even_when_identical(side):
    mapping = selected().resource
    resource = registry(mapping)
    args = {"resources": [resource], "mappings": [mapping], "bindings": [resource.binding()]}
    args[side] *= 2
    with pytest.raises(MappingError) as caught:
        select_registries(**args)
    assert caught.value.reason == ("mapping_duplicate_key" if side == "bindings" else "mapping_duplicate_resource")


def test_registry_and_rule_resources_cannot_share_a_collection_key():
    mapping = selected().resource
    second = ExchangeMapping(artifact_bytes(mapping_value(mapping_id="other:rules")))
    resource = registry(second, mapping_id=mapping.mapping_id, mapping_version=mapping.mapping_version)
    with pytest.raises(MappingError) as caught:
        select_registries([resource], bindings=[resource.binding()], mappings=[mapping, second])
    assert caught.value.reason == "mapping_duplicate_resource"


@pytest.mark.parametrize("field", ["source_system", "source_document", "external_id"])
def test_literal_registry_identity_does_not_trim_casefold_or_normalize_unicode(field):
    mapping = selected().resource
    entries = [entry_value(**{field: text}) for text in ("é", "e\u0301", "É", " é ")]
    resource = registry(mapping, entries=entries)
    index = select_registries([resource], bindings=[resource.binding()], mappings=[mapping])
    for row in entries:
        assert lookup(index, **{field: row[field]})["entry"] == row
    assert lookup(index, **{field: "absent"}) is None


@pytest.mark.parametrize("revision", [None, "next"])
def test_selected_registry_collisions_ignore_revision_and_rule_identity(revision):
    mapping = selected().resource
    second = ExchangeMapping(artifact_bytes(mapping_value(mapping_version="2.0.0")))
    first = registry(mapping)
    other = registry(second, mapping_id="other:registry", entries=[entry_value(external_revision=revision)])
    for resources in ([first, other], [other, first]):
        with pytest.raises(MappingError) as caught:
            select_registries(resources, bindings=[r.binding() for r in resources], mappings=[mapping, second])
        assert caught.value.reason == "mapping_duplicate_registry_entry"
        assert caught.value.path == resources[1].key and caught.value.pointer == "/entries/0"


def test_noncolliding_registries_with_different_rules_preserve_each_actual_binding():
    mapping = selected().resource
    second = ExchangeMapping(artifact_bytes(mapping_value(mapping_version="2.0.0")))
    first = registry(mapping)
    other = registry(second, mapping_id="other:registry", entries=[entry_value(source_system="other")])
    expected = {"registry": other.binding(), "mapping": second.binding(), "entry": other.data["entries"][0]}
    for resources in ([first, other], [other, first]):
        index = select_registries(resources, bindings=[r.binding() for r in resources], mappings=[second, mapping])
        assert lookup(index, source_system="other") == expected
    changed = second.data
    changed["extensions"]["example.change"] = True
    with pytest.raises(MappingError) as caught:
        select_registries([other], bindings=[other.binding()], mappings=[ExchangeMapping(artifact_bytes(changed))])
    assert caught.value.reason == "mapping_hash_mismatch" and caught.value.path == second.key


def test_registry_uses_canonical_content_hash_and_revalidates_source_bytes():
    mapping = selected().resource
    resource = registry(mapping)
    formatted = ExternalIdentityRegistry(json.dumps(resource.data, indent=1).encode())
    assert resource.sha256 == formatted.sha256 and resource.source_sha256 != formatted.source_sha256
    bound = [resource.binding()]
    assert lookup(select_registries([formatted], bindings=bound, mappings=[mapping]))["registry"] == bound[0]
    with pytest.raises(MappingError) as caught:
        select_registries([resource], bindings=[{**bound[0], "sha256": resource.source_sha256}], mappings=[mapping])
    assert caught.value.reason == "mapping_hash_mismatch"
    other = registry(mapping, entries=[])
    object.__setattr__(other, "sha256", resource.sha256)
    with pytest.raises(MappingError) as caught:
        select_registries([other], bindings=bound, mappings=[mapping])
    assert caught.value.reason == "mapping_hash_mismatch"


def test_selected_registry_bytes_are_not_replaceable_through_returned_observations():
    mapping = selected().resource
    resource = registry(mapping)
    bindings = [resource.binding()]
    index = select_registries([resource], bindings=bindings, mappings=[mapping])
    expected = lookup(index)
    changed = registry(mapping, entries=[entry_value(data={"altered": True})])
    resource.__init__(changed.source_bytes)
    index.resources[0].__init__(changed.source_bytes)
    bindings[0]["sha256"] = "0" * 64
    first = lookup(index)
    first["entry"]["data"].clear()
    first["mapping"]["sha256"] = "0" * 64
    assert lookup(index) == expected
    assert index.resources[0].sha256 == expected["registry"]["sha256"] != resource.sha256


@pytest.mark.parametrize("field,change", [("external_revision", "next"), ("data", {"raw": "changed"}),
    ("extensions", {"example.changed": True})])
def test_passive_registry_changes_alter_model_root_and_own_hash_but_leave_rules_untouched(field, change):
    mapping = selected().resource
    first = registry(mapping, entries=[entry_value()])
    other = registry(mapping, entries=[entry_value(**{field: change})])
    def root(resource):
        project = model([], resource_files=[ModelDocument("mappings/rules.json", mapping.source_bytes),
            ModelDocument("mappings/registry.json", resource.source_bytes)])
        return project.manifest(project.artifacts, SCOPE).sha256
    assert root(first) != root(other) and first.sha256 != other.sha256
    assert first.data["mapping"] == other.data["mapping"] == mapping.binding()


@pytest.mark.parametrize("version_field", ["version", "mapping_version"])
def test_generic_legacy_resources_keep_original_bytes_and_root_without_becoming_v1(version_field):
    raw = artifact_bytes({"schema_version": "0.2.0", "mapping_id": "old", version_field: "1.0.0",
        "settings": {"converter": "passive legacy text", "fields": ["source"]}})
    project = model([], resource_files=[ModelDocument("mappings/old.json", raw)])
    root = project.manifest(project.artifacts, SCOPE).sha256
    with no_write_attempts(), pytest.raises(MappingError):
        ExchangeMapping(raw)
    assert project.source_files["mappings/old.json"] == raw
    assert project.manifest(project.artifacts, SCOPE).sha256 == root


@pytest.mark.parametrize("mode", ["core", "pyz"])
def test_isolated_runtimes_keep_selection_binding_and_fail_closed_without_side_effects(tmp_path, mode):
    mapping = selected().resource
    resource = registry(mapping)
    other = registry(mapping, entries=[])
    body = '''import json, os, sys
from specroad.mappings import ExchangeMapping, ExternalIdentityRegistry, MappingError, select_registries
def guard(event, args):
    if event.startswith(('socket.', 'subprocess.')) or event in ('os.system', 'os.mkdir', 'os.remove', 'os.rename'):
        raise AssertionError(event)
    if event == 'open':
        mode, flags = args[1], args[2]
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
            raise AssertionError(event)
sys.addaudithook(guard)
'''
    body += 'm=ExchangeMapping(' + repr(mapping.source_bytes) + ')\n'
    body += 'r=ExternalIdentityRegistry(' + repr(resource.source_bytes) + ')\n'
    body += 's=select_registries([r],bindings=[r.binding()],mappings=[m])\n'
    body += 's.resources[0].__init__(' + repr(other.source_bytes) + ')\n'
    body += '''try:
    select_registries([r],bindings=[{**r.binding(),'sha256':'0'*64}],mappings=[m])
except MappingError as error:
    failure=error.diagnostic()
else:
    raise AssertionError('Wrong hash accepted')
print(json.dumps({'entry':s.lookup('type','supplier','document-a','same-id'),'failure':failure}))
'''
    if mode == "core":
        result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / "distribution")
        result = run_python(["-I", "-S", "-B", "-c", "import sys;sys.path.insert(0," + repr(str(package)) + ")\n" + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["entry"] == {"registry": resource.binding(), "mapping": mapping.binding(), "entry": entry_value()}
    assert output["failure"]["reason"] == "mapping_hash_mismatch"
    assert output["failure"]["code"] == "SRV090" and output["failure"]["exit_code"] == 3


def test_registry_success_missing_lookup_and_failed_selection_leave_project_untouched(tmp_path):
    mapping = selected().resource
    resource = registry(mapping)
    path = tmp_path / "registry.json"
    path.write_bytes(resource.source_bytes)
    path.chmod(0o444)
    before = inventory(tmp_path)
    bindings = [resource.binding()]
    saved = deepcopy(bindings)
    with no_write_attempts():
        index = select_registries([resource], bindings=bindings, mappings=[mapping])
        assert lookup(index)["entry"] == entry_value()
        assert lookup(index, external_id="missing") is None
        with pytest.raises(MappingError):
            select_registries([resource], bindings=bindings, mappings=[])
    assert bindings == saved and inventory(tmp_path) == before
