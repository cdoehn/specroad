"""Restore refuses actual lost bytes, unsafe roots and changes at live boundaries.

Recorded build labels and declared task evidence are fixtures. Packages, native
flocks, original bytes, publications and filesystem changes are real operations.
"""

import fcntl
from hashlib import sha256
import json
import os
import shutil

import pytest

from specroad import _build
from specroad.cli.commands import builtin_registry
from specroad.cli.requests import CommandRequest
from specroad.model.canonical import canonical_json_bytes
from specroad.security import SafetyViolation
from specroad.work import packages
from specroad.work._archive import ArchiveError, encode_archive
from specroad.work.checkpoints import CheckpointStore, CheckpointStorageError
from specroad.work.finalization import finalize_read_only_work
from specroad.work.manifest import create_work_manifest, partition_work_manifest
from specroad.work.resume import WorkResumeError, _runtime_build, resume_read_only_work
from support.read_only import inventory, no_write_attempts
from test_work_manifest import sealed
from test_work_packages import restore, unpack
from test_work_resume import recorded, setup


def reference(raw):
    return {'sha256': sha256(raw).hexdigest(), 'size': len(raw)}


def altered_initial(metadata, payloads, change):
    """Rebind the real container/record hashes, leaving a semantic reader to decide."""
    pointer = json.loads(payloads['work.json'])
    checkpoint_path = 'checkpoints/' + pointer['checkpoint']['sha256'] + '.json'
    record = json.loads(payloads.pop(checkpoint_path))
    value = json.loads(payloads.pop('objects/' + record['manifest']['sha256']))
    change(value)
    manifest = sealed(value); identity = json.loads(manifest)['checkpoint_sha256']
    record['manifest'] = reference(manifest); record['checkpoint_sha256'] = identity
    payloads['objects/' + record['manifest']['sha256']] = manifest
    checkpoint = canonical_json_bytes(record)
    pointer['checkpoint'] = reference(checkpoint); pointer['checkpoint_sha256'] = identity
    payloads['checkpoints/' + pointer['checkpoint']['sha256'] + '.json'] = checkpoint
    payloads['work.json'] = canonical_json_bytes(pointer)
    metadata['initial_manifest'] = reference(manifest)
    metadata['initial_checkpoint_sha256'] = metadata['checkpoint_sha256'] = identity
    return encode_archive('work-package.json', metadata, payloads)


@pytest.mark.parametrize('kind', ['format', 'build', 'algorithm', 'schema', 'command', 'progress', 'state'])
def test_coherently_rehashed_unknown_work_contracts_cannot_allocate_a_target(recorded, tmp_path, kind):
    _, roots, _, store = setup(tmp_path)
    metadata, payloads = unpack(packages.export_work_package(store))
    def change(value):
        if kind == 'format': value['work_format_version'] = '99.0.0'
        elif kind == 'build': value['tool_build']['version'] = 'unknown-runtime'
        elif kind == 'algorithm': value['algorithm_versions'] = {'unknown': '99'}
        elif kind == 'schema': value['schema_versions'] = {}
        elif kind == 'command': value['command_id'] = 'uninstalled.foreign-command'
        elif kind == 'progress': value['progress']['completed_units'] = True
        else: value['state'] = 'foreign-terminal-state'
    raw = altered_initial(metadata, payloads, change)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ArchiveError):
        restore(raw, roots, tmp_path / 'rejected')
    assert inventory(tmp_path) == before and not (tmp_path / 'rejected').exists()


def test_a_valid_alternate_inventory_tree_is_rejected_before_nonidentical_restore(recorded, tmp_path):
    _, roots, _, store = setup(tmp_path)
    metadata, payloads = unpack(packages.export_work_package(store))
    pointer = json.loads(payloads['work.json'])
    path = 'checkpoints/' + pointer['checkpoint']['sha256'] + '.json'
    record = json.loads(payloads.pop(path))
    index = json.loads(payloads.pop('objects/' + record['objects']['sha256']))
    rows = index['entries']; assert len(rows) > 1
    def segment(items, *, branch=False):
        raw = canonical_json_bytes({'format_version': 'work-manifest-segment-v1',
            'kind': 'checkpoint-objects', 'children' if branch else 'entries': items})
        ref = reference(raw); payloads['objects/' + ref['sha256']] = raw
        return {'id': 'SEG-' + ref['sha256'], **ref,
                'count': sum(item['count'] for item in items) if branch else len(items)}
    # Both leaves and this branch are structurally valid and retain all rows.
    record['objects'] = segment([segment(rows[:1]), segment(rows[1:])], branch=True)
    checkpoint = canonical_json_bytes(record); pointer['checkpoint'] = reference(checkpoint)
    payloads['checkpoints/' + pointer['checkpoint']['sha256'] + '.json'] = checkpoint
    payloads['work.json'] = canonical_json_bytes(pointer)
    raw = encode_archive('work-package.json', metadata, payloads)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ArchiveError) as caught:
        restore(raw, roots, tmp_path / 'rejected')
    assert caught.value.reason == 'noncanonical_work_package_inventory'
    assert inventory(tmp_path) == before and not (tmp_path / 'rejected').exists()


@pytest.mark.parametrize('kind', ['input', 'manifest', 'inventory_segment', 'ancestor', 'result'])
def test_lost_referenced_bytes_cannot_be_reconstructed_from_hashes(recorded, tmp_path, kind):
    source = tmp_path / 'source'; source.write_bytes(b'actual retained input\0\xff')
    initial = create_work_manifest(builtin_registry(), CommandRequest('version'),
        tool_build=_runtime_build(),
        source_bindings={'project_id': None, 'scope': ['declared-loss-fixture'], 'model_root_sha256': None},
        inputs=[{'root_id': 'input', 'path': 'source', 'raw': source.read_bytes()}],
        units=[{'key': str(n), 'phase': 'data-fixture', 'range': {'n': n}} for n in range(70)])
    _, roots, location, store = setup(tmp_path, initial=initial)
    evidence = b'{"declared_fixture_data":true}'
    successor = partition_work_manifest(initial, {initial.entries('tasks')[0]['unit_id']: evidence})
    store.publish(successor)
    metadata, payloads = unpack(packages.export_work_package(store))
    pointer = json.loads(payloads['work.json'])
    record = json.loads(payloads['checkpoints/' + pointer['checkpoint']['sha256'] + '.json'])
    if kind == 'input': missing = 'objects/' + initial.entries('inputs')[0]['sha256']
    elif kind == 'manifest': missing = 'objects/' + metadata['initial_manifest']['sha256']
    elif kind == 'ancestor': missing = 'checkpoints/' + record['parent']['sha256'] + '.json'
    elif kind == 'result': missing = 'objects/' + sha256(evidence).hexdigest()
    else:
        missing = next(name for name, data in payloads.items()
            if name.startswith('objects/') and b'"kind":"checkpoint-objects"' in data)
    del payloads[missing]
    raw = encode_archive('work-package.json', metadata, payloads)
    source.unlink(); shutil.rmtree(location.path)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ArchiveError) as caught:
        restore(raw, roots, tmp_path / 'rejected')
    assert caught.value.reason == 'work_package_bytes_missing'
    assert inventory(tmp_path) == before and not (tmp_path / 'rejected').exists()


def test_runtime_change_during_actual_package_validation_prevents_target_allocation(recorded, tmp_path, monkeypatch):
    _, roots, _, store = setup(tmp_path); raw = packages.export_work_package(store)
    checked = packages._checked_package
    def changed(*args, **kwargs):
        result = checked(*args, **kwargs)
        monkeypatch.setattr(_build, 'BUILD_METADATA', {'format_version': 1,
            'hash_algorithm': 'specroad-dev-payload-v1', 'build_sha256': 'b' * 64})
        return result
    monkeypatch.setattr(packages, '_checked_package', changed)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ArchiveError) as caught:
        restore(raw, roots, tmp_path / 'rejected')
    assert caught.value.reason == 'work_package_runtime_changed'
    assert inventory(tmp_path) == before and not (tmp_path / 'rejected').exists()


def test_a_live_native_mutex_on_an_empty_target_prevents_any_restore_write(recorded, tmp_path):
    _, roots, _, store = setup(tmp_path); raw = packages.export_work_package(store)
    target = tmp_path / 'busy'; target.mkdir(mode=0o700)
    fd = os.open(target, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        before = inventory(tmp_path)
        with no_write_attempts(), pytest.raises(BlockingIOError):
            restore(raw, roots, target)
        assert inventory(tmp_path) == before
    finally:
        os.close(fd)
    restored = restore(raw, roots, target)
    assert restored.read().raw == store.read().raw


@pytest.mark.parametrize('kind', ['protected_ancestor', 'symlink_ancestor'])
def test_unsafe_restore_ancestors_are_rejected_without_probe_writes(recorded, tmp_path, kind):
    _, roots, _, store = setup(tmp_path); raw = packages.export_work_package(store)
    target = tmp_path
    if kind == 'symlink_ancestor':
        parent = tmp_path / 'parent'; parent.mkdir(mode=0o700)
        alias = tmp_path / 'alias'; alias.symlink_to(parent, target_is_directory=True)
        target = alias / 'new-root'
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(SafetyViolation):
        restore(raw, roots, target)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('kind', ['pointer', 'object', 'runtime'])
def test_export_rechecks_real_source_and_runtime_after_encoding(recorded, tmp_path, monkeypatch, kind):
    initial, roots, location, store = setup(tmp_path)
    original = packages.encode_archive; project = inventory(roots[0].root); changed_paths = []
    def changed(*args, **kwargs):
        raw = original(*args, **kwargs)
        if kind == 'runtime':
            monkeypatch.setattr(_build, 'BUILD_METADATA', {'format_version': 1,
                'hash_algorithm': 'specroad-dev-payload-v1', 'build_sha256': 'b' * 64})
        else:
            path = location.path / ('work.json' if kind == 'pointer' else 'objects/' + next(iter(initial.objects)))
            path.write_bytes(b'changed actual source'); changed_paths.append(path)
        return raw
    monkeypatch.setattr(packages, 'encode_archive', changed)
    with pytest.raises((WorkResumeError, CheckpointStorageError)):
        packages.export_work_package(store)
    assert all(path.read_bytes() == b'changed actual source' for path in changed_paths)
    assert inventory(roots[0].root) == project and not (location.path / 'work-lock.json').exists()


@pytest.mark.parametrize('generation', [0, 2])
@pytest.mark.parametrize('kind', ['root_file', 'object_file', 'result_file', 'symlink', 'hardlink', 'directory', 'public_file'])
def test_foreign_arrivals_stop_restore_and_preserve_the_actual_published_prefix(recorded, tmp_path, monkeypatch, generation, kind):
    _, roots, _, store = setup(tmp_path); resume_read_only_work(store); finalize_read_only_work(store)
    raw = packages.export_work_package(store); target = tmp_path / 'restored'
    outside = tmp_path / 'foreign'; outside.write_bytes(b'foreign bytes'); outside.chmod(0o600)
    project = inventory(roots[0].root); publish = CheckpointStore._publish_held
    observed = []; pointers = []; retained = []
    def changed(self, held, manifest, before):
        result = publish(self, held, manifest, before)
        number = manifest.as_dict()['checkpoint_generation']; observed.append(number)
        pointers.append((target / 'work.json').read_bytes())
        if number == generation:
            if kind in ('root_file', 'object_file', 'result_file'):
                parent = target if kind == 'root_file' else target / ('objects' if kind == 'object_file' else 'results')
                path = parent / 'foreign'; path.write_bytes(b'foreign bytes'); path.chmod(0o600)
            else:
                path = target / 'objects' / next(iter(manifest.objects))
                if kind == 'public_file': path.chmod(0o644)
                else:
                    path.unlink()
                    if kind == 'symlink': path.symlink_to(outside)
                    elif kind == 'hardlink': os.link(outside, path)
                    else: path.mkdir(mode=0o700)
            retained.append((path, path.lstat()))
        return result
    monkeypatch.setattr(CheckpointStore, '_publish_held', changed)
    with pytest.raises((ArchiveError, SafetyViolation)):
        restore(raw, roots, target)
    assert observed == list(range(generation + 1)) and len(retained) == 1
    assert (target / 'work.json').read_bytes() == pointers[-1]
    assert json.loads(pointers[-1])['checkpoint_generation'] == generation
    path, stat = retained[0]
    assert path.lstat().st_ino == stat.st_ino and path.lstat().st_mode == stat.st_mode
    assert outside.read_bytes() == b'foreign bytes' and inventory(roots[0].root) == project
    if kind in ('root_file', 'object_file', 'result_file'): assert path.read_bytes() == b'foreign bytes'
    if kind == 'symlink': assert path.is_symlink() and path.readlink() == outside
    if kind == 'hardlink': assert path.stat().st_ino == outside.stat().st_ino and path.stat().st_nlink == 2
    assert not (target / 'work-lock.json').exists()


def test_replaced_destination_inode_does_not_redirect_remaining_publication(recorded, tmp_path, monkeypatch):
    _, roots, _, store = setup(tmp_path); resume_read_only_work(store)
    raw = packages.export_work_package(store); target = tmp_path / 'restored'; retained = tmp_path / 'retained'
    publish = CheckpointStore._publish_held; observed = []; project = inventory(roots[0].root)
    def changed(self, held, manifest, before):
        result = publish(self, held, manifest, before)
        observed.append(manifest.as_dict()['checkpoint_generation'])
        target.rename(retained); target.mkdir(mode=0o700)
        (target / 'foreign').write_bytes(b'replacement retained')
        return result
    monkeypatch.setattr(CheckpointStore, '_publish_held', changed)
    with pytest.raises(SafetyViolation):
        restore(raw, roots, target)
    assert observed == [0] and sorted(p.name for p in target.iterdir()) == ['foreign']
    assert (target / 'foreign').read_bytes() == b'replacement retained'
    assert json.loads((retained / 'work.json').read_bytes())['checkpoint_generation'] == 0
    assert (retained / 'work-lock.json').is_file() and inventory(roots[0].root) == project
