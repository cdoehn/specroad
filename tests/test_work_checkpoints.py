"""Durable data publication, real process restart and immutable generation history."""

import base64
import errno
from hashlib import sha256
import json
import os
import stat
import subprocess

import pytest

from specroad.security import ProjectBoundary, SafetyViolation
from specroad.work.checkpoints import CheckpointStore, CheckpointStorageError
from specroad.work.manifest import WorkManifestError, partition_work_manifest
from specroad.work.root import WorkDirectory
from support.project_locks import child_program
from support.read_only import inventory, no_write_attempts
from test_work_manifest import BUILD, create, evidence
from test_work_root import protected


def setup(tmp_path, *, initial=None):
    initial = create() if initial is None else initial
    roots = protected(tmp_path)
    location = WorkDirectory(initial, protected_roots=roots, directory=tmp_path / 'work')
    return initial, roots, location, CheckpointStore(location, initial)


def successor(manifest):
    task = manifest.entries('remaining')[0]
    return partition_work_manifest(manifest, {task['unit_id']: evidence(task)})


def trusted_packet(tmp_path, initial, following):
    # Independent fixture trust input, not reconstructed from the stored work root.
    def encode(value):
        return {'raw': base64.b64encode(value.raw).decode(),
                'objects': {k: base64.b64encode(v).decode() for k, v in value.objects.items()}}
    path = tmp_path / 'trusted-initial-fixture.json'
    path.write_text(json.dumps({'initial': encode(initial), 'following': encode(following),
                               'build': BUILD}))
    return path


CHILD = '''
import base64, json, os
from pathlib import Path
from specroad.cli.commands import builtin_registry
from specroad.security import ProjectBoundary
from specroad.work.manifest import read_work_manifest
from specroad.work.root import WorkDirectory
from specroad.work.checkpoints import CheckpointStore
import specroad.work.checkpoints as storage
packet = json.loads(Path(sys.argv[1]).read_text())
def decode(data):
    return read_work_manifest(base64.b64decode(data['raw']),
        {k: base64.b64decode(v) for k, v in data['objects'].items()},
        registry=builtin_registry(), expected_tool_build=packet['build'])
initial, following = decode(packet['initial']), decode(packet['following'])
location = WorkDirectory(initial, protected_roots=(ProjectBoundary(sys.argv[3]),),
                         directory=Path(sys.argv[2]))
store = CheckpointStore(location, initial)
stage = sys.argv[4]
if stage == 'partial_objects':
    native = storage._ensure_file
    def stop_after_object(*args, **kwargs):
        native(*args, **kwargs)
        os._exit(21)
    storage._ensure_file = stop_after_object
elif stage in ('before_pointer', 'after_pointer'):
    native = storage.replace_bound_image
    def stop_at_pointer(*args, **kwargs):
        if stage == 'after_pointer':
            native(*args, **kwargs)
        os._exit(22 if stage == 'before_pointer' else 23)
    storage.replace_bound_image = stop_at_pointer
if stage != 'read':
    store.publish(following)
loaded = store.read()
print(json.dumps({'raw': base64.b64encode(loaded.raw).decode(),
    'objects': {k: base64.b64encode(v).decode() for k, v in loaded.objects.items()},
    'generation': loaded.as_dict()['checkpoint_generation']}))
'''


def run_child(packet, work, project, stage):
    return subprocess.run(child_program(CHILD, packet, work, project, stage),
                          capture_output=True, text=True)


def test_storage_declaration_and_absent_inspection_do_not_create_files(tmp_path):
    initial, _, location, store = setup(tmp_path)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(FileNotFoundError):
        store.read()
    assert inventory(tmp_path) == before and location.path is None


def test_bound_but_unpublished_root_has_no_current_generation(tmp_path):
    _, _, location, store = setup(tmp_path)
    with location.for_checkpoint():
        pass
    before = inventory(location.path)
    with no_write_attempts():
        assert store.read() is None
    assert inventory(location.path) == before


def test_complete_generations_preserve_every_declared_byte_and_previous_file(tmp_path):
    initial, roots, location, store = setup(tmp_path)
    protected_before = inventory(roots[0].root)
    current = initial
    old_files = {}
    for generation in range(4):
        assert store.publish(current).raw == current.raw
        assert location.path == tmp_path / 'work'
        pointer = json.loads((location.path / 'work.json').read_bytes())
        assert pointer['checkpoint_generation'] == generation
        assert pointer['checkpoint_sha256'] == current.as_dict()['checkpoint_sha256']
        with no_write_attempts():
            loaded = store.read()
        assert loaded.raw == current.raw and dict(loaded.objects) == dict(current.objects)
        assert inventory(roots[0].root) == protected_before
        assert not (location.path / 'work-lock.json').exists()
        for path, raw in old_files.items():
            assert path.read_bytes() == raw
        old_files.update({p: p.read_bytes() for folder in ('objects', 'checkpoints')
                          for p in (location.path / folder).iterdir()})
        for path in location.path.rglob('*'):
            assert stat.S_IMODE(path.stat().st_mode) & 0o077 == 0
        current = successor(current)


def test_an_independent_runtime_reads_exactly_the_last_published_generation(tmp_path):
    initial, roots, location, store = setup(tmp_path)
    following = successor(initial)
    packet = trusted_packet(tmp_path, initial, following)
    store.publish(initial); store.publish(following)
    before = inventory(location.path)
    done = run_child(packet, location.path, roots[0].root, 'read')
    assert done.returncode == 0, done.stderr
    result = json.loads(done.stdout)
    assert result['generation'] == 1
    assert base64.b64decode(result['raw']) == following.raw
    assert {k: base64.b64decode(v) for k, v in result['objects'].items()} == dict(following.objects)
    assert inventory(location.path) == before


@pytest.mark.parametrize('stage,exit_code,generation', [
    ('partial_objects', 21, 0), ('before_pointer', 22, 0), ('after_pointer', 23, 1),
])
def test_real_abrupt_exit_never_publishes_a_partial_generation_or_steals_the_owner(tmp_path, stage, exit_code, generation):
    initial, roots, location, store = setup(tmp_path)
    following = successor(initial)
    packet = trusted_packet(tmp_path, initial, following)
    store.publish(initial)
    old_pointer = (location.path / 'work.json').read_bytes()
    done = run_child(packet, location.path, roots[0].root, stage)
    assert done.returncode == exit_code, done.stderr
    owner = location.path / 'work-lock.json'
    assert owner.exists()
    before = inventory(location.path)
    with no_write_attempts():
        actual = store.read()
    expected = initial if generation == 0 else following
    assert actual.raw == expected.raw and dict(actual.objects) == dict(expected.objects)
    assert inventory(location.path) == before
    if generation == 0:
        assert (location.path / 'work.json').read_bytes() == old_pointer
    with pytest.raises(SafetyViolation):
        store.publish(successor(actual))
    assert inventory(location.path) == before


def test_segmented_object_inventory_and_binary_inputs_survive_reopening(tmp_path):
    initial = create(data=[{'root_id': 'input', 'path': f'{n:04}.bin',
                           'raw': n.to_bytes(2, 'big') + bytes(range(256))} for n in range(150)])
    initial, roots, location, store = setup(tmp_path, initial=initial)
    store.publish(initial)
    pointer = json.loads((location.path / 'work.json').read_bytes())
    record_path = location.path / 'checkpoints' / (pointer['checkpoint']['sha256'] + '.json')
    record = json.loads(record_path.read_bytes())
    index = json.loads((location.path / 'objects' / record['objects']['sha256']).read_bytes())
    assert index['kind'] == 'checkpoint-objects' and 1 < len(index['children']) <= 64
    assert record['objects']['count'] == len(initial.objects)
    reopened = WorkDirectory(initial, protected_roots=roots, directory=location.path)
    with no_write_attempts():
        loaded = CheckpointStore(reopened, initial).read()
    assert dict(loaded.objects) == dict(initial.objects)
    assert loaded.entries('inputs') == initial.entries('inputs')


def test_all_payload_files_are_synced_before_the_current_pointer_can_change(tmp_path, monkeypatch):
    initial, _, location, store = setup(tmp_path)
    synced = set(); native_sync = os.fsync
    native_replace = __import__('specroad.work.checkpoints', fromlist=['replace_bound_image']).replace_bound_image
    checked = []
    def sync(fd):
        native_sync(fd)
        info = os.fstat(fd); synced.add((info.st_dev, info.st_ino))
    def replacing(*args, **kwargs):
        assert not (location.path / 'work.json').exists()
        for folder in ('objects', 'checkpoints'):
            directory = location.path / folder
            for path in (directory, *directory.iterdir()):
                info = path.stat()
                assert (info.st_dev, info.st_ino) in synced
        for digest, raw in initial.objects.items():
            assert (location.path / 'objects' / digest).read_bytes() == raw
        checked.append(True)
        return native_replace(*args, **kwargs)
    monkeypatch.setattr('specroad.work.checkpoints.os.fsync', sync)
    monkeypatch.setattr('specroad.work.checkpoints.replace_bound_image', replacing)
    store.publish(initial)
    assert checked == [True] and store.read().raw == initial.raw


def test_failed_new_object_write_keeps_the_previous_checkpoint_readable(tmp_path, monkeypatch):
    initial, _, location, store = setup(tmp_path)
    store.publish(initial)
    old_pointer = (location.path / 'work.json').read_bytes()
    following = successor(initial)
    fresh = set(following.objects) - set(initial.objects)
    native = __import__('specroad.work.checkpoints', fromlist=['_write_new'])._write_new
    def failing(parent, name, raw):
        if name in fresh:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=parent)
            try:
                os.write(fd, raw[:1]); os.fsync(fd)
            finally:
                os.close(fd)
            raise OSError(errno.ENOSPC, 'injected full work volume')
        return native(parent, name, raw)
    with monkeypatch.context() as scoped:
        scoped.setattr('specroad.work.checkpoints._write_new', failing)
        with pytest.raises(OSError) as error:
            store.publish(following)
        assert error.value.errno == errno.ENOSPC
    assert (location.path / 'work.json').read_bytes() == old_pointer
    with no_write_attempts():
        assert store.read().raw == initial.raw
    assert not (location.path / 'work-lock.json').exists()
    assert any((location.path / 'objects' / name).exists() for name in fresh)


@pytest.mark.parametrize('candidate', ['same', 'skip', 'different'])
def test_only_an_immediate_successor_of_the_current_binding_can_publish(tmp_path, candidate):
    initial, _, location, store = setup(tmp_path)
    store.publish(initial)
    following = {'same': initial, 'skip': successor(successor(initial)), 'different': create()}[candidate]
    before = inventory(location.path)
    with pytest.raises((CheckpointStorageError, WorkManifestError)):
        store.publish(following)
    assert inventory(location.path) == before
    assert store.read().raw == initial.raw


@pytest.mark.parametrize('change', ['missing', 'different'])
def test_unavailable_required_payload_is_named_instead_of_reconstructed(tmp_path, change):
    initial, _, location, store = setup(tmp_path)
    store.publish(initial)
    digest = initial.entries('inputs')[0]['sha256']
    path = location.path / 'objects' / digest
    if change == 'missing':
        path.unlink()
    else:
        path.write_bytes(b'changed')
    before = inventory(location.path)
    with no_write_attempts(), pytest.raises(CheckpointStorageError) as error:
        store.read()
    assert error.value.path == 'objects/' + digest
    assert error.value.reason == ('checkpoint_bytes_missing' if change == 'missing' else 'checkpoint_bytes_changed')
    assert inventory(location.path) == before


def test_active_publisher_mutex_blocks_an_independent_reader(tmp_path):
    initial, roots, location, store = setup(tmp_path)
    following = successor(initial);packet = trusted_packet(tmp_path, initial, following)
    store.publish(initial)
    with location.for_checkpoint():
        before = inventory(location.path)
        done = run_child(packet, location.path, roots[0].root, 'read')
        assert done.returncode != 0
        assert inventory(location.path) == before
    assert store.read().raw == initial.raw


def test_wrong_initial_binding_is_rejected_without_storage_effects(tmp_path):
    initial, _, location, _ = setup(tmp_path)
    before = inventory(tmp_path)
    for candidate in (create(), successor(initial), object()):
        with no_write_attempts(), pytest.raises(CheckpointStorageError):
            CheckpointStore(location, candidate)
    assert inventory(tmp_path) == before
