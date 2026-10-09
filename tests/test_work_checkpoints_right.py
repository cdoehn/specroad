"""Hostile stored generations, changing read sets and publication fault windows."""

import errno
from hashlib import sha256
import json
import os
from pathlib import Path
import stat

import pytest

from specroad.model.canonical import canonical_json_bytes
from specroad.security import SafetyViolation
from specroad.work.checkpoints import CheckpointStorageError
from specroad.work.manifest import WorkManifestError
import specroad.work.checkpoints as storage
from support.read_only import inventory, no_write_attempts
from test_work_checkpoints import setup, successor
from test_work_manifest import create, sealed


def ref(raw):
    return {'sha256': sha256(raw).hexdigest(), 'size': len(raw)}


def put(root, folder, raw):
    reference = ref(raw)
    name = reference['sha256'] + ('.json' if folder == 'checkpoints' else '')
    path = root / folder / name
    path.write_bytes(raw); path.chmod(0o600)
    return reference


def documents(root):
    pointer = json.loads((root / 'work.json').read_bytes())
    record = json.loads((root / 'checkpoints' / (pointer['checkpoint']['sha256'] + '.json')).read_bytes())
    return pointer, record


def point_record(root, pointer, record):
    pointer = dict(pointer)
    pointer['checkpoint'] = put(root, 'checkpoints', canonical_json_bytes(record))
    (root / 'work.json').write_bytes(canonical_json_bytes(pointer))


def point_segment(root, pointer, record, segment, count, *, raw=None):
    encoded = canonical_json_bytes(segment) if raw is None else raw
    segment_ref = put(root, 'objects', encoded)
    record['objects'] = {'id': 'SEG-' + segment_ref['sha256'], **segment_ref, 'count': count}
    point_record(root, pointer, record)


def reject_read(store, root, *errors):
    before = inventory(root)
    with no_write_attempts(), pytest.raises(errors or (CheckpointStorageError, WorkManifestError, SafetyViolation)) as caught:
        store.read()
    assert inventory(root) == before
    return caught.value


@pytest.mark.parametrize('component', ['record', 'manifest', 'index'])
@pytest.mark.parametrize('change', ['missing', 'wrong_hash'])
def test_missing_or_changed_required_metadata_cannot_be_a_checkpoint(tmp_path, component, change):
    initial, _, location, store = setup(tmp_path);store.publish(initial)
    pointer, record = documents(location.path)
    folder = 'checkpoints' if component == 'record' else 'objects'
    reference = pointer['checkpoint'] if component == 'record' else record['manifest' if component == 'manifest' else 'objects']
    path = location.path / folder / (reference['sha256'] + ('.json' if folder == 'checkpoints' else ''))
    if change == 'missing':
        path.unlink()
    else:
        path.write_bytes(b'changed')
    error = reject_read(store, location.path, CheckpointStorageError)
    assert error.path == str(path.relative_to(location.path))
    assert error.reason == ('checkpoint_bytes_missing' if change == 'missing' else 'checkpoint_bytes_changed')


@pytest.mark.parametrize('update', [
    {'format_version': 'future'}, {'work_id': 'WORK-foreign'},
    {'checkpoint_generation': True}, {'checkpoint_generation': 9},
    {'checkpoint_sha256': '0' * 64}, {'unexpected': 'required'},
])
def test_rehashed_pointer_metadata_never_overrides_its_bound_generation(tmp_path, update):
    initial, _, location, store = setup(tmp_path);store.publish(initial)
    pointer, _ = documents(location.path);pointer.update(update)
    (location.path / 'work.json').write_bytes(canonical_json_bytes(pointer))
    reject_read(store, location.path)


@pytest.mark.parametrize('update', [
    {'format_version': 'future'}, {'work_id': 'WORK-foreign'},
    {'checkpoint_generation': True}, {'checkpoint_generation': 9},
    {'checkpoint_sha256': '0' * 64}, {'parent': None}, {'unexpected': 'required'},
])
def test_self_consistent_record_hashes_do_not_validate_false_generation_metadata(tmp_path, update):
    initial, _, location, store = setup(tmp_path)
    store.publish(initial);store.publish(successor(initial))
    pointer, record = documents(location.path);record.update(update)
    point_record(location.path, pointer, record)
    reject_read(store, location.path)


@pytest.mark.parametrize('change', ['duplicate', 'missing_entry', 'reverse', 'bool_size', 'kind', 'branch_duplicate'])
def test_rehashed_inventory_still_requires_a_complete_unique_ordered_object_set(tmp_path, change):
    initial, _, location, store = setup(tmp_path);store.publish(initial)
    pointer, record = documents(location.path)
    segment = json.loads((location.path / 'objects' / record['objects']['sha256']).read_bytes())
    rows = segment['entries'];count = len(rows)
    if change == 'duplicate':
        rows.append(dict(rows[0]));count += 1
    elif change == 'missing_entry':
        required = initial.entries('inputs')[0]['sha256']
        rows[:] = [row for row in rows if row['sha256'] != required];count -= 1
    elif change == 'reverse':
        rows.reverse()
    elif change == 'bool_size':
        rows[0]['size'] = True
    elif change == 'kind':
        segment['kind'] = 'different'
    else:
        segment = {'format_version': 'work-manifest-segment-v1', 'kind': 'checkpoint-objects',
                   'children': [dict(record['objects']), dict(record['objects'])]}
        count *= 2
    point_segment(location.path, pointer, record, segment, count)
    reject_read(store, location.path)


def test_noncanonical_inventory_cannot_be_smuggled_under_a_fresh_hash(tmp_path):
    initial, _, location, store = setup(tmp_path);store.publish(initial)
    pointer, record = documents(location.path)
    segment = json.loads((location.path / 'objects' / record['objects']['sha256']).read_bytes())
    raw = json.dumps(segment, indent=4).encode()
    assert raw != canonical_json_bytes(segment)
    point_segment(location.path, pointer, record, segment, record['objects']['count'], raw=raw)
    error = reject_read(store, location.path, CheckpointStorageError)
    assert error.reason == 'noncanonical_checkpoint_segment'


def test_a_fully_rehashed_foreign_initial_model_does_not_replace_the_trust_anchor(tmp_path):
    initial, _, location, store = setup(tmp_path);store.publish(initial)
    foreign = create(sources={'project_id': None, 'scope': ['foreign'], 'model_root_sha256': None})
    value = foreign.as_dict();value['work_id'] = initial.as_dict()['work_id']
    raw = sealed(value)
    pointer, record = documents(location.path)
    for payload in foreign.objects.values():
        put(location.path, 'objects', payload)
    record['manifest'] = put(location.path, 'objects', raw)
    record['checkpoint_sha256'] = json.loads(raw)['checkpoint_sha256']
    pointer['checkpoint_sha256'] = record['checkpoint_sha256']
    segment = {'format_version': 'work-manifest-segment-v1', 'kind': 'checkpoint-objects',
               'entries': [{'sha256': key, 'size': len(payload)} for key, payload in sorted(foreign.objects.items())]}
    point_segment(location.path, pointer, record, segment, len(foreign.objects))
    error = reject_read(store, location.path, CheckpointStorageError)
    assert error.reason == 'checkpoint_binding_changed'


@pytest.mark.parametrize('component', ['pointer', 'input'])
@pytest.mark.parametrize('kind', ['symlink', 'hardlink', 'public', 'fifo'])
def test_unsafe_storage_is_not_followed_repaired_or_replaced(tmp_path, component, kind):
    initial, _, location, store = setup(tmp_path);store.publish(initial)
    path = location.path / ('work.json' if component == 'pointer' else
                            'objects/' + initial.entries('inputs')[0]['sha256'])
    outside = tmp_path / 'outside';outside.write_bytes(path.read_bytes());outside.chmod(0o600)
    if kind == 'public':
        path.chmod(0o644)
    else:
        path.unlink()
        if kind == 'symlink':
            path.symlink_to(outside)
        elif kind == 'hardlink':
            os.link(outside, path)
        else:
            os.mkfifo(path, 0o600)
    before = outside.read_bytes()
    reject_read(store, location.path, SafetyViolation)
    assert outside.read_bytes() == before


@pytest.mark.parametrize('component', ['index', 'record'])
def test_structurally_bounded_metadata_is_rejected_before_its_bytes_are_read(tmp_path, monkeypatch, component):
    initial, _, location, store = setup(tmp_path);store.publish(initial)
    pointer, record = documents(location.path)
    raw = b' ' * 65537
    if component == 'index':
        point_segment(location.path, pointer, record, {}, record['objects']['count'], raw=raw)
        path = location.path / 'objects' / sha256(raw).hexdigest()
    else:
        pointer['checkpoint'] = put(location.path, 'checkpoints', raw)
        (location.path / 'work.json').write_bytes(canonical_json_bytes(pointer))
        path = location.path / 'checkpoints' / (sha256(raw).hexdigest() + '.json')
    identity = (path.stat().st_dev, path.stat().st_ino);native = os.read
    def no_payload_read(fd, count):
        info = os.fstat(fd)
        assert (info.st_dev, info.st_ino) != identity
        return native(fd, count)
    monkeypatch.setattr('specroad.work.checkpoints.os.read', no_payload_read)
    error = reject_read(store, location.path, CheckpointStorageError)
    assert error.reason == 'checkpoint_metadata_too_large'


def test_wrong_object_size_is_detected_before_reading_the_object(tmp_path, monkeypatch):
    initial, _, location, store = setup(tmp_path);store.publish(initial)
    path = location.path / 'objects' / initial.entries('inputs')[0]['sha256']
    path.write_bytes(b'x' * 1000000)
    identity = (path.stat().st_dev, path.stat().st_ino);native = os.read
    def no_payload_read(fd, count):
        info = os.fstat(fd)
        assert (info.st_dev, info.st_ino) != identity
        return native(fd, count)
    monkeypatch.setattr('specroad.work.checkpoints.os.read', no_payload_read)
    error = reject_read(store, location.path, CheckpointStorageError)
    assert error.reason == 'checkpoint_bytes_changed'


@pytest.mark.parametrize('change', ['missing', 'changed'])
def test_damage_after_initial_readback_but_before_pointer_replace_preserves_old_current(tmp_path, monkeypatch, change):
    initial, _, location, store = setup(tmp_path);store.publish(initial)
    following = successor(initial);old_pointer = (location.path / 'work.json').read_bytes()
    fresh = sorted(set(following.objects) - set(initial.objects))[0]
    path = location.path / 'objects' / fresh
    native = storage._write_new;calls = []
    def after_pointer_temp(parent, name, raw):
        result = native(parent, name, raw)
        if name.startswith('.current-'):
            if change == 'missing':
                path.unlink()
            else:
                path.write_bytes(b'damaged new generation')
            calls.append(True)
        return result
    with monkeypatch.context() as scoped:
        scoped.setattr(storage, '_write_new', after_pointer_temp)
        with pytest.raises(CheckpointStorageError):
            store.publish(following)
    assert calls == [True] and (location.path / 'work.json').read_bytes() == old_pointer
    assert store.read().raw == initial.raw
    assert not (location.path / 'work-lock.json').exists()


@pytest.mark.parametrize('change', ['same_size', 'same_bytes_new_inode', 'missing'])
def test_a_previously_read_object_must_stay_bound_until_the_reader_returns(tmp_path, monkeypatch, change):
    initial, _, location, store = setup(tmp_path);store.publish(initial)
    path = location.path / 'objects' / initial.entries('inputs')[0]['sha256']
    native = storage.read_work_manifest;calls = []
    def changed_after_validation(*args, **kwargs):
        result = native(*args, **kwargs)
        before, raw = path.stat(), path.read_bytes()
        if change == 'missing':
            path.unlink()
        elif change == 'same_bytes_new_inode':
            path.rename(location.path / 'objects' / 'retained-original')
            path.write_bytes(raw);path.chmod(0o600)
        else:
            path.write_bytes(b'x' * len(raw));os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        calls.append(True)
        return result
    monkeypatch.setattr(storage, 'read_work_manifest', changed_after_validation)
    with pytest.raises(CheckpointStorageError) as error:
        store.read()
    assert calls == [True]
    assert error.value.path == str(path.relative_to(location.path))
    assert not (location.path / 'work-lock.json').exists()


def test_pointer_replacement_by_another_writer_is_not_silently_overwritten(tmp_path, monkeypatch):
    initial, _, location, store = setup(tmp_path);store.publish(initial)
    following = successor(initial)
    native = storage._write_new;foreign = b'{"foreign":"retained"}'
    def replace_pointer(parent, name, raw):
        result = native(parent, name, raw)
        if name.startswith('.current-'):
            (location.path / 'work.json').write_bytes(foreign)
        return result
    monkeypatch.setattr(storage, '_write_new', replace_pointer)
    with pytest.raises(CheckpointStorageError) as error:
        store.publish(following)
    assert error.value.reason == 'checkpoint_pointer_changed'
    assert (location.path / 'work.json').read_bytes() == foreign


@pytest.mark.parametrize('phase', ['new_object', 'pointer_file', 'target_directory', 'source_directory'])
def test_fsync_failure_keeps_the_actual_complete_pointer_and_retains_predecessors(tmp_path, monkeypatch, phase):
    initial, _, location, store = setup(tmp_path);store.publish(initial)
    following = successor(initial);old_pointer = (location.path / 'work.json').read_bytes()
    old_files = {p:p.read_bytes() for folder in ('objects', 'checkpoints') for p in (location.path / folder).iterdir()}
    fresh = set(following.objects) - set(initial.objects)
    native = os.fsync;injected = []
    def fail_once(fd):
        path = Path(os.readlink('/proc/self/fd/' + str(fd)))
        switched = (location.path / 'work.json').read_bytes() != old_pointer
        match = ((phase == 'new_object' and path.name in fresh)
                 or (phase == 'pointer_file' and path.name.startswith('.current-'))
                 or (phase == 'target_directory' and switched and path == location.path)
                 or (phase == 'source_directory' and switched and path == location.path / 'checkpoints'))
        if match and not injected:
            injected.append(True)
            raise OSError(errno.EIO, 'injected durability failure')
        return native(fd)
    with monkeypatch.context() as scoped:
        scoped.setattr('specroad.work.checkpoints.os.fsync', fail_once)
        with pytest.raises(OSError) as error:
            store.publish(following)
        assert error.value.errno == errno.EIO
    assert injected == [True]
    for path, raw in old_files.items():
        assert path.read_bytes() == raw
    expected = following if phase in ('target_directory', 'source_directory') else initial
    with no_write_attempts():
        assert store.read().raw == expected.raw
    assert not (location.path / 'work-lock.json').exists()


def test_unreferenced_private_script_bytes_remain_inert_and_are_not_cleaned(tmp_path):
    initial, _, location, store = setup(tmp_path);store.publish(initial)
    path = location.path / 'objects' / 'retained-script.py'
    marker = tmp_path / 'must-not-exist'
    path.write_text('from pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\n');path.chmod(0o600)
    before = inventory(location.path)
    with no_write_attempts():
        assert store.read().raw == initial.raw
    assert inventory(location.path) == before and not marker.exists()
