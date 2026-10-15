"""Reference retention, collision refusal and actual native storage failure boundaries."""
import json
import os

import pytest

from specroad.archive import (ObjectReference, SnapshotObject, SnapshotObjectStore,
                              check_object_retention, read_snapshot_object)
from specroad.changes.lock_values import ProjectLockError
from specroad.changes.staging_values import StagingError
from specroad.model.errors import ModelError
from specroad.security import ProjectBoundary, SafetyViolation
from support.processes import run_core
from support.read_only import inventory, make_project, no_write_attempts


def store_at(tmp_path):
    project = tmp_path / 'project'; project.mkdir(); make_project(project)
    root = tmp_path / 'objects'; root.mkdir(mode=0o700)
    return SnapshotObjectStore(root, protected_roots=(ProjectBoundary(project),))


def test_two_reference_owners_share_one_unchanged_object_during_addition(tmp_path):
    store = store_at(tmp_path); shared = SnapshotObject(b'shared'); first = store.put(shared)
    second = ObjectReference(first.sha256, first.size); original = (store.root / first.path).stat()
    added = SnapshotObject(b'new')
    result = store.put(added, retained_references=(first, second))
    assert store.get(first) == store.get(second) == b'shared' and store.get(result) == b'new'
    assert (store.root / first.path).stat().st_ino == original.st_ino
    checked = check_object_retention([shared, shared], [added, shared], references=[first, second])
    assert checked['referenced_paths'] == checked['retained_paths'] == [first.path]
    assert checked['added_paths'] == [result.path] and checked['removed_paths'] == []
    assert not checked['write_authorized'] and not checked['baseline_completeness_verified']


def test_removing_a_shared_referenced_object_is_rejected_even_with_another_object_present():
    first, second = SnapshotObject(b'first'), SnapshotObject(b'second')
    with pytest.raises(ModelError) as caught:
        check_object_retention([first, second], [second], references=[first.reference, first.reference])
    assert caught.value.reason == 'snapshot_referenced_object_removal' and caught.value.path == first.reference.path


def test_unreferenced_candidate_removal_is_only_a_data_observation_without_write_authority():
    first, second = SnapshotObject(b'first'), SnapshotObject(b'second')
    with no_write_attempts(): result = check_object_retention([first, second], [second], references=[second.reference])
    assert result['removed_paths'] == [first.reference.path] and not result['write_authorized']
    assert result['scope'] == 'supplied_snapshot_objects_and_references'


@pytest.mark.parametrize('where', ['within_inventory', 'replacement'])
def test_even_a_hash_collision_cannot_alias_distinct_original_bytes(monkeypatch, where):
    monkeypatch.setattr(SnapshotObject, 'reference', property(lambda item: ObjectReference('a' * 64, len(item.content))))
    first, second = SnapshotObject(b'one'), SnapshotObject(b'two')
    with pytest.raises(ModelError) as caught:
        if where == 'within_inventory': check_object_retention([first, second], [], references=[])
        else: check_object_retention([first], [second], references=[])
    assert caught.value.reason == ('snapshot_object_content_collision' if where == 'within_inventory'
                                    else 'snapshot_object_replacement_forbidden')


def test_reference_must_bind_a_real_supplied_predecessor_object():
    item = SnapshotObject(b'content')
    with pytest.raises(ModelError) as caught: check_object_retention([], [item], references=[item.reference])
    assert caught.value.reason == 'snapshot_referenced_object_missing'


@pytest.mark.parametrize('duplicate', [False, True])
def test_inconsistent_reference_sizes_never_validate_a_shared_hash(duplicate):
    item = SnapshotObject(b'content'); wrong = ObjectReference(item.reference.sha256, 1)
    references = [item.reference, wrong] if duplicate else [wrong]
    with pytest.raises(ModelError) as caught: check_object_retention([item], [item], references=references)
    assert caught.value.reason == 'snapshot_reference_conflict'


@pytest.mark.parametrize('value', [None, {}, 'objects'])
def test_transition_requires_explicit_object_sequences(value):
    with pytest.raises(ModelError) as caught: check_object_retention(value, [], references=[])
    assert caught.value.reason == 'snapshot_objects_required'


@pytest.mark.parametrize('value', [None, {}, 'references'])
def test_transition_requires_explicit_reference_sequences(value):
    with pytest.raises(ModelError) as caught: check_object_retention([], [], references=value)
    assert caught.value.reason == 'snapshot_references_required'


def test_missing_retained_file_refuses_put_before_creating_any_archive_storage(tmp_path):
    store = store_at(tmp_path); before = inventory(store.root)
    with pytest.raises(ModelError) as caught:
        store.put(SnapshotObject(b'new'), retained_references=[SnapshotObject(b'missing').reference])
    assert caught.value.reason == 'snapshot_referenced_object_missing' and inventory(store.root) == before


def test_retained_inputs_are_owned_before_native_preparation_callbacks(tmp_path, monkeypatch):
    import specroad.archive.objects as module
    store = store_at(tmp_path); retained = store.put(SnapshotObject(b'old')); expected = ObjectReference(retained.sha256, retained.size)
    original = module._write_new
    def changed(*args):
        identity = original(*args); object.__setattr__(retained, 'sha256', '0' * 64); return identity
    monkeypatch.setattr(module, '_write_new', changed)
    added = store.put(SnapshotObject(b'new'), retained_references=[retained])
    assert store.get(expected) == b'old' and store.get(added) == b'new'


@pytest.mark.parametrize('phase', ['prepared', 'published'])
def test_external_removal_of_retained_bytes_cannot_return_a_successful_put(tmp_path, monkeypatch, phase):
    import specroad.archive.objects as module
    store = store_at(tmp_path); retained = store.put(SnapshotObject(b'old')); item = SnapshotObject(b'new')
    path = store.root / retained.path
    if phase == 'prepared':
        original = module._write_new
        def changed(*args):
            result = original(*args); path.unlink(); return result
        monkeypatch.setattr(module, '_write_new', changed)
    else:
        original = os.link
        def changed(*args, **kwargs):
            result = original(*args, **kwargs); path.unlink(); return result
        monkeypatch.setattr(os, 'link', changed)
    with pytest.raises(ModelError) as caught: store.put(item, retained_references=[retained])
    assert caught.value.reason == 'snapshot_referenced_object_missing'
    assert not path.exists()
    assert (store.root / item.reference.path).exists() is (phase == 'published')


def test_tampered_preparation_image_is_rejected_before_the_hash_path_is_published(tmp_path, monkeypatch):
    import specroad.archive.objects as module
    store = store_at(tmp_path); item = SnapshotObject(b'content'); original = module._write_new
    def changed(directory, name, raw):
        identity = original(directory, name, raw)
        path = store.root / item.reference.path.rsplit('/', 1)[0] / name
        path.write_bytes(b'damaged'); return identity
    monkeypatch.setattr(module, '_write_new', changed)
    with pytest.raises(StagingError): store.put(item)
    assert not (store.root / item.reference.path).exists()
    assert [p.read_bytes() for p in store.root.rglob('.snapshot-*')] == [b'damaged']


def test_swapped_object_directory_is_refused_before_publication(tmp_path, monkeypatch):
    import specroad.archive.objects as module
    store = store_at(tmp_path); item = SnapshotObject(b'content'); original = module._write_new
    parent = store.root / item.reference.path.rsplit('/', 1)[0]
    def changed(*args):
        identity = original(*args); parent.rename(parent.with_name(parent.name + '-retained')); parent.mkdir(); return identity
    monkeypatch.setattr(module, '_write_new', changed)
    with pytest.raises(SafetyViolation): store.put(item)
    assert not (store.root / item.reference.path).exists()
    assert [p.read_bytes() for p in store.root.rglob('.snapshot-*')] == [item.content]


def test_a_late_specroad_project_marker_blocks_publication(tmp_path, monkeypatch):
    import specroad.archive.objects as module
    store = store_at(tmp_path); item = SnapshotObject(b'content'); original = module._write_new
    def changed(*args):
        identity = original(*args); (store.root / 'specroad.json').write_bytes(b'{}'); return identity
    monkeypatch.setattr(module, '_write_new', changed)
    with pytest.raises(SafetyViolation): store.put(item)
    assert not (store.root / item.reference.path).exists()


@pytest.mark.parametrize('component', ['archive', 'objects', 'bucket', 'object'])
def test_linked_object_components_cannot_be_read_or_reused(tmp_path, component):
    store = store_at(tmp_path); item = SnapshotObject(b'content'); reference = store.put(item)
    parts = reference.path.split('/'); depth = {'archive':1, 'objects':2, 'bucket':3, 'object':4}[component]
    path = store.root.joinpath(*parts[:depth]); saved = path.with_name(path.name + '-original')
    path.rename(saved); path.symlink_to(saved, target_is_directory=component != 'object'); before = inventory(tmp_path)
    with pytest.raises((SafetyViolation, ProjectLockError)): store.get(reference)
    with pytest.raises((SafetyViolation, ProjectLockError)): store.put(item)
    assert inventory(tmp_path) == before


def test_hardlinked_object_is_not_accepted_or_rewritten(tmp_path):
    store = store_at(tmp_path); item = SnapshotObject(b'content'); reference = store.put(item)
    os.link(store.root / reference.path, store.root / 'alias'); before = inventory(store.root)
    with pytest.raises(SafetyViolation): store.get(reference)
    with pytest.raises(SafetyViolation): store.put(item)
    assert inventory(store.root) == before


def test_replaced_root_cannot_be_used_through_an_earlier_store_binding(tmp_path):
    store = store_at(tmp_path); store.root.rename(tmp_path / 'original'); store.root.mkdir(mode=0o700)
    before = inventory(tmp_path)
    with pytest.raises(SafetyViolation): store.put(SnapshotObject(b'content'))
    assert inventory(tmp_path) == before


def test_late_content_change_during_read_is_not_returned_as_verified_bytes(tmp_path, monkeypatch):
    store = store_at(tmp_path); reference = store.put(SnapshotObject(b'content')); path = store.root / reference.path
    original = os.read; changed = []
    def reading(fd, size):
        result = original(fd, size)
        if result and not changed: path.write_bytes(b'damaged'); changed.append(True)
        return result
    monkeypatch.setattr(os, 'read', reading)
    with pytest.raises(SafetyViolation): store.get(reference)
    assert path.read_bytes() == b'damaged'


def test_size_mismatch_is_refused_before_reading_any_object_bytes(tmp_path, monkeypatch):
    store = store_at(tmp_path); reference = store.put(SnapshotObject(b'content'))
    def forbidden(*unused): raise AssertionError('Unexpected payload read')
    monkeypatch.setattr(os, 'read', forbidden)
    with pytest.raises(ModelError) as caught: store.get(ObjectReference(reference.sha256, 1000))
    assert caught.value.reason == 'snapshot_object_size_mismatch'


def test_a_racing_target_is_preserved_without_clobber_or_cleanup(tmp_path, monkeypatch):
    store = store_at(tmp_path); item = SnapshotObject(b'content'); target = store.root / item.reference.path
    original = os.link
    def racing(*args, **kwargs): target.write_bytes(b'foreign'); return original(*args, **kwargs)
    monkeypatch.setattr(os, 'link', racing)
    with pytest.raises(FileExistsError): store.put(item)
    assert target.read_bytes() == b'foreign'
    assert [p.read_bytes() for p in store.root.rglob('.snapshot-*')] == [item.content]


def test_failure_after_publication_keeps_both_actual_links_and_cannot_fake_success(tmp_path, monkeypatch):
    store = store_at(tmp_path); item = SnapshotObject(b'content'); original = os.unlink
    def failed(name, *args, **kwargs):
        if str(name).startswith('.snapshot-'): raise OSError('injected unlink failure')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(os, 'unlink', failed)
    with pytest.raises(OSError): store.put(item)
    target = store.root / item.reference.path
    assert target.read_bytes() == item.content and target.stat().st_nlink == 2
    before = inventory(store.root)
    with pytest.raises(SafetyViolation): store.get(item.reference)
    with pytest.raises(SafetyViolation): store.put(item)
    assert inventory(store.root) == before


def test_retention_result_is_owned_order_independent_and_read_only():
    first, second = SnapshotObject(b'first'), SnapshotObject(b'second'); references = [second.reference, first.reference]
    with no_write_attempts():
        expected = check_object_retention([first, second], [second, first], references=references)
        actual = check_object_retention([second, first], [first, second], references=list(reversed(references)))
    assert actual == expected
    actual['referenced_paths'].clear()
    assert check_object_retention([first, second], [second, first], references=references) == expected


def test_reference_retention_contract_runs_in_a_fresh_isolated_core(tmp_path):
    body = '''import json
from specroad.archive import SnapshotObject, check_object_retention
from specroad.model.errors import ModelError
obj=SnapshotObject(b'shared')
try: check_object_retention([obj], [], references=[obj.reference])
except ModelError as error: print(json.dumps(error.diagnostic()))
else: raise AssertionError('Referenced removal accepted')
'''
    result = run_core(body, tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['reason'] == 'snapshot_referenced_object_removal'
