"""Shared immutable bytes retain fresh read-set and publication guarantees."""

import json
import os

import pytest

from specroad.model.canonical import canonical_json_bytes
from specroad.security import SafetyViolation
from specroad.work.checkpoints import CheckpointStorageError
import specroad.work.checkpoints as storage
from support.read_only import inventory, no_write_attempts
from test_work_checkpoints import setup, successor
from test_work_checkpoints_right import documents, point_record, put
from test_work_manifest import create


def published_pair(tmp_path, *, data=None):
    initial, _, location, store = setup(tmp_path, initial=create(data=data))
    following = successor(initial)
    store.publish(initial)
    store.publish(following)
    shared = location.path / 'objects' / initial.entries('inputs')[0]['sha256']
    return location, store, following, shared


def observed_reads(monkeypatch, path):
    identity = path.stat().st_dev, path.stat().st_ino
    native = os.read
    payloads = []

    def read(fd, count):
        info = os.fstat(fd)
        raw = native(fd, count)
        if (info.st_dev, info.st_ino) == identity and raw:
            payloads.append(raw)
        return raw

    monkeypatch.setattr(storage.os, 'read', read)
    return payloads


def test_shared_bytes_are_read_once_per_chain_but_fresh_on_the_next_call(tmp_path, monkeypatch):
    location, store, expected, shared = published_pair(tmp_path)
    original = shared.read_bytes()
    before = inventory(location.path)
    payloads = observed_reads(monkeypatch, shared)
    for _ in range(2):
        payloads.clear()
        with no_write_attempts():
            actual = store.read()
        assert actual.raw == expected.raw and dict(actual.objects) == dict(expected.objects)
        assert b''.join(payloads) == original
        assert inventory(location.path) == before
    shared.write_bytes(b'x' * len(original))
    with pytest.raises(CheckpointStorageError):
        store.read()
    assert shared.read_bytes() == b'x' * len(original)
    shared.write_bytes(original)
    assert store.read().raw == expected.raw


def mutate(path, outside, change):
    before, raw = path.stat(), path.read_bytes()
    if change == 'same_size':
        path.write_bytes(b'x' * len(raw))
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    elif change == 'same_bytes_new_inode':
        path.rename(path.with_name('retained-original'))
        path.write_bytes(raw)
        path.chmod(0o600)
    elif change == 'public':
        path.chmod(0o644)
    else:
        path.unlink()
        if change == 'symlink':
            path.symlink_to(outside)
        elif change == 'hardlink':
            os.link(outside, path)


@pytest.mark.parametrize('change', [
    'same_size', 'same_bytes_new_inode', 'missing', 'public', 'symlink', 'hardlink',
])
def test_reused_bytes_do_not_hide_changes_before_chain_acceptance(tmp_path, monkeypatch, change):
    location, store, expected, shared = published_pair(tmp_path)
    pointer = (location.path / 'work.json').read_bytes()
    outside = tmp_path / 'outside'
    original = shared.read_bytes()
    outside.write_bytes(original)
    outside.chmod(0o600)
    native = storage.read_work_manifest
    changed = []

    def after_latest_manifest(*args, **kwargs):
        manifest = native(*args, **kwargs)
        if not changed:
            assert manifest.raw == expected.raw
            mutate(shared, outside, change)
            changed.append(True)
        return manifest

    monkeypatch.setattr(storage, 'read_work_manifest', after_latest_manifest)
    with pytest.raises((CheckpointStorageError, SafetyViolation)):
        store.read()
    assert changed == [True]
    assert (location.path / 'work.json').read_bytes() == pointer
    assert outside.read_bytes() == original
    assert not (location.path / 'work-lock.json').exists()


def rewrite_predecessor(root, update):
    pointer, latest = documents(root)
    parent = latest['parent']
    previous = json.loads((root / 'checkpoints' / (parent['sha256'] + '.json')).read_bytes())
    update(previous)
    latest['parent'] = put(root, 'checkpoints', canonical_json_bytes(previous))
    point_record(root, pointer, latest)


def test_a_later_reference_cannot_change_the_size_of_reused_bytes(tmp_path):
    location, store, _, shared = published_pair(tmp_path)

    def wrong_size(previous):
        segment = json.loads((location.path / 'objects' / previous['objects']['sha256']).read_bytes())
        row = next(row for row in segment['entries'] if row['sha256'] == shared.name)
        row['size'] += 1
        reference = put(location.path, 'objects', canonical_json_bytes(segment))
        previous['objects'] = {**previous['objects'], **reference, 'id': 'SEG-' + reference['sha256']}

    rewrite_predecessor(location.path, wrong_size)
    before = inventory(location.path)
    with no_write_attempts(), pytest.raises(CheckpointStorageError) as error:
        store.read()
    assert error.value.reason == 'checkpoint_bytes_changed'
    assert error.value.path == 'objects/' + shared.name
    assert inventory(location.path) == before


def test_reusing_a_payload_as_metadata_still_enforces_the_metadata_bound(tmp_path):
    data = [{'root_id': 'input', 'path': 'large.bin', 'raw': b'x' * 65537}]
    location, store, _, shared = published_pair(tmp_path, data=data)

    def oversized_index(previous):
        previous['objects'] = {'id': 'SEG-' + shared.name, 'sha256': shared.name,
                               'size': shared.stat().st_size, 'count': 1}

    rewrite_predecessor(location.path, oversized_index)
    before = inventory(location.path)
    with no_write_attempts(), pytest.raises(CheckpointStorageError) as error:
        store.read()
    assert error.value.reason == 'checkpoint_metadata_too_large'
    assert error.value.path == 'objects/' + shared.name
    assert inventory(location.path) == before


@pytest.mark.parametrize('limit', ['_MAX_REUSED_OBJECT_BYTES', '_MAX_REUSED_OBJECTS'])
def test_exhausted_reuse_budget_keeps_exact_results_and_current_file_checks(tmp_path, monkeypatch, limit):
    location, store, expected, shared = published_pair(tmp_path)
    original = shared.read_bytes()
    before = inventory(location.path)
    monkeypatch.setattr(storage, limit, 0)
    payloads = observed_reads(monkeypatch, shared)
    with no_write_attempts():
        actual = store.read()
    assert actual.raw == expected.raw and dict(actual.objects) == dict(expected.objects)
    assert b''.join(payloads) == original * 2
    assert inventory(location.path) == before
    shared.unlink()
    with pytest.raises(CheckpointStorageError):
        store.read()


def test_shared_bytes_are_rechecked_at_the_pointer_publication_barrier(tmp_path, monkeypatch):
    initial, _, location, store = setup(tmp_path)
    store.publish(initial)
    following = successor(initial)
    shared = location.path / 'objects' / initial.entries('inputs')[0]['sha256']
    original = shared.read_bytes()
    pointer = (location.path / 'work.json').read_bytes()
    native = storage._write_new
    changed = []

    def after_pointer_temp(parent, name, raw):
        result = native(parent, name, raw)
        if name.startswith('.current-'):
            shared.write_bytes(b'x' * len(original))
            changed.append(True)
        return result

    monkeypatch.setattr(storage, '_write_new', after_pointer_temp)
    with pytest.raises(CheckpointStorageError):
        store.publish(following)
    assert changed == [True]
    assert (location.path / 'work.json').read_bytes() == pointer
    assert shared.read_bytes() == b'x' * len(original)
    assert not (location.path / 'work-lock.json').exists()
