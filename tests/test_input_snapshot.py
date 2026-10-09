"""Real guarded byte capture with explicit partial progress and immutable reuse."""

from hashlib import sha256
import json
import os
import pickle

import pytest

from specroad.security import ProjectBoundary, SafetyViolation
from specroad.work.snapshot import InputSnapshotTask, SnapshotCaptureError
from support.read_only import inventory, no_write_attempts
from test_work_manifest import create, read


def inputs(tmp_path, values=None):
    values = {'b.bin': b'abc' * 11, 'a.bin': b'first', 'empty': b''} if values is None else values
    root = tmp_path / 'source'; root.mkdir()
    for name, raw in values.items():
        path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    roots = {'source': ProjectBoundary(root)}
    entries = [{'root_id': 'source', 'path': name} for name in reversed(values)]
    return root, roots, entries, values


def finish(task, window=1):
    while not task.state['complete']:
        before = task.state['confirmed_units']
        state = task.advance(window)
        assert before < state['confirmed_units'] <= before + window
    return task.state


@pytest.mark.parametrize('window,block', [(1, 1), (3, 7), (10000, 65536)])
def test_every_declared_input_is_captured_with_monotone_bounded_progress(tmp_path, window, block):
    root, roots, entries, values = inputs(tmp_path)
    before = inventory(tmp_path)
    with no_write_attempts(), InputSnapshotTask(roots, entries, block_bytes=block) as task:
        state = finish(task, window)
        manifest = json.loads(task.manifest_bytes)
        assert [row['path'] for row in manifest['inputs']] == sorted(values)
        assert state['captured_bytes'] == sum(map(len, values.values()))
        assert state['completed_inputs'] == state['expected_inputs'] == len(values)
        assert state['input_manifest_sha256'] == sha256(task.manifest_bytes).hexdigest()
        assert state['model_root_sha256'] is None
        assert state['atomic_project_snapshot'] is False and state['durable_checkpoint'] is False
        for row in manifest['inputs']:
            raw = values[row['path']]
            assert row['size'] == len(raw) and row['sha256'] == sha256(raw).hexdigest()
            assert task.read_input('source', row['path']) == raw
        for digest, raw in task.objects.items():
            assert digest == sha256(raw).hexdigest() and len(raw) <= block
        assert str(root) not in json.dumps(state)
    assert inventory(tmp_path) == before


def test_constructor_and_deterministic_enumeration_do_not_read_source_content(tmp_path, monkeypatch):
    _, roots, entries, _ = inputs(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError('content read during declaration enumeration')
    monkeypatch.setattr('specroad.work.snapshot.os.read', forbidden)
    with no_write_attempts(), InputSnapshotTask(roots, entries) as task:
        assert task.state['enumerated_inputs'] == 0
        for number in range(1, len(entries) + 1):
            state = task.advance(1)
            assert state['enumerated_inputs'] == number
            assert state['captured_bytes'] == 0 and not state['complete']
        assert [row['path'] for row in state['inputs']] == sorted(row['path'] for row in entries)


def test_first_complete_input_is_usable_before_the_whole_set_is_finished(tmp_path):
    _, roots, entries, values = inputs(tmp_path)
    with InputSnapshotTask(roots, entries, block_bytes=2) as task:
        while task.state['completed_inputs'] == 0:
            task.advance(1)
        state = task.state
        assert not state['complete'] and state['input_manifest_sha256'] is None
        assert task.read_input('source', 'a.bin') == values['a.bin']
        with pytest.raises(SnapshotCaptureError) as error:
            task.manifest_bytes
        assert error.value.reason == 'input_set_incomplete'
        with pytest.raises(SnapshotCaptureError) as error:
            task.read_input('source', 'b.bin')
        assert error.value.as_dict()['path'] == 'b.bin'
        assert task.read_input('source', 'a.bin') == values['a.bin']


def test_pausing_does_not_reread_already_captured_blocks(tmp_path, monkeypatch):
    raw = b'0123456789' * 14000
    _, roots, entries, _ = inputs(tmp_path, {'large': raw})
    native = os.read; observed = []
    def read_once(fd, count):
        offset = os.lseek(fd, 0, os.SEEK_CUR)
        data = native(fd, count)
        observed.append((offset, count, len(data)))
        return data
    monkeypatch.setattr('specroad.work.snapshot.os.read', read_once)
    with InputSnapshotTask(roots, entries, block_bytes=10**9) as task:
        finish(task)
        assert task.read_input('source', 'large') == raw
    assert [row[0] for row in observed] == [0, 65536, 131072, len(raw)]
    assert max(row[1] for row in observed) <= 65536
    assert sum(row[2] for row in observed) == len(raw)


def test_partial_blocks_survive_close_without_becoming_a_complete_input(tmp_path):
    _, roots, entries, _ = inputs(tmp_path, {'file': b'abcdefgh'})
    task = InputSnapshotTask(roots, entries, block_bytes=3)
    task.advance(3)  # declaration, opening, one captured block
    state = task.state
    ref, = state['inputs'][0]['chunks']
    task.close()
    assert task.read_block(ref['sha256']) == b'abc'
    assert task.state['closed'] and not task.state['complete']
    with pytest.raises(SnapshotCaptureError):
        task.advance(1)
    with pytest.raises(SnapshotCaptureError):
        task.read_input('source', 'file')


def test_sealed_capture_survives_source_relocation_and_later_content_changes(tmp_path):
    root, roots, entries, values = inputs(tmp_path)
    with InputSnapshotTask(roots, entries) as task:
        finish(task)
    manifest = task.manifest_bytes
    root.rename(tmp_path / 'moved')
    root.mkdir()
    (root / 'a.bin').write_bytes(b'later unrelated project bytes')
    assert task.manifest_bytes == manifest
    assert {row['path']: row['raw'] for row in task.work_inputs()} == values
    # The actual captured bytes can feed the existing inert work-v1 codec.
    work = create(data=task.work_inputs())
    assert read(work.raw, work.objects).raw == work.raw


def test_input_order_root_location_and_block_size_do_not_change_manifest_binding(tmp_path):
    bindings = []
    for index, block in enumerate((1, 8, 65536)):
        folder = tmp_path / str(index); folder.mkdir()
        _, roots, entries, _ = inputs(folder)
        with InputSnapshotTask(roots, list(reversed(entries)) if index else entries,
                               block_bytes=block) as task:
            finish(task, 1000); bindings.append(task.manifest_bytes)
    assert len(set(bindings)) == 1


def test_detached_progress_and_store_cannot_change_captured_data(tmp_path):
    _, roots, entries, values = inputs(tmp_path)
    with InputSnapshotTask(roots, entries) as task:
        finish(task)
        state = task.state; state['inputs'].clear(); state['complete'] = False
        with pytest.raises(TypeError):
            task.objects['foreign'] = b'altered'
        assert task.state['complete']
        assert {row['path']: row['raw'] for row in task.work_inputs()} == values
        before = task.state
        assert task.advance(7) == before


@pytest.mark.parametrize('window', [0, -1, True, 1.5])
def test_invalid_work_window_preserves_the_previous_state(tmp_path, window):
    _, roots, entries, _ = inputs(tmp_path)
    with InputSnapshotTask(roots, entries) as task:
        before = task.state
        with pytest.raises(ValueError):
            task.advance(window)
        assert task.state == before


@pytest.mark.parametrize('block', [0, -1, True, 1.5])
def test_invalid_block_size_is_rejected_before_input_access(tmp_path, block):
    _, roots, entries, _ = inputs(tmp_path)
    with no_write_attempts(), pytest.raises(ValueError):
        InputSnapshotTask(roots, entries, block_bytes=block)


@pytest.mark.parametrize('path', ['../outside', '/absolute', 'a//b', 'a/./b', 'a\\b'])
def test_unsafe_declared_input_paths_are_rejected(tmp_path, path):
    _, roots, _, _ = inputs(tmp_path)
    with no_write_attempts(), pytest.raises(SafetyViolation):
        InputSnapshotTask(roots, [{'root_id': 'source', 'path': path}])


def test_missing_input_is_named_and_previously_captured_bytes_are_retained(tmp_path):
    _, roots, entries, _ = inputs(tmp_path, {'a': b'already captured'})
    entries.append({'root_id': 'source', 'path': 'missing'})
    with InputSnapshotTask(roots, entries) as task:
        with pytest.raises(SnapshotCaptureError) as error:
            finish(task)
        assert error.value.as_dict() == {'reason': 'source_missing', 'root_id': 'source',
                                         'path': 'missing', 'object_sha256': None}
        assert task.read_input('source', 'a') == b'already captured'
        before = task.state
        assert before['phase'] == 'failed' and not before['complete']
        with pytest.raises(SnapshotCaptureError):
            task.advance(1)
        assert task.state == before


def test_missing_captured_object_is_not_reconstructed_from_its_hash(tmp_path):
    _, roots, entries, _ = inputs(tmp_path)
    with InputSnapshotTask(roots, entries) as task:
        with pytest.raises(SnapshotCaptureError) as error:
            task.read_block('0' * 64)
        assert error.value.reason == 'captured_bytes_missing'
        assert error.value.object_sha256 == '0' * 64
        assert task.objects == {}


@pytest.mark.parametrize('change', ['rewrite', 'grow', 'truncate', 'replace'])
def test_changed_open_source_never_becomes_a_complete_input(tmp_path, change):
    root, roots, entries, _ = inputs(tmp_path, {'file': b'abcdefgh'})
    with InputSnapshotTask(roots, entries, block_bytes=2) as task:
        task.advance(3)
        path = root / 'file'
        if change == 'replace':
            path.rename(root / 'original'); path.write_bytes(b'abcdefgh')
        else:
            path.write_bytes({'rewrite': b'XXXXXXXX', 'grow': b'abcdefghMORE',
                              'truncate': b'a'}[change])
        with pytest.raises(SnapshotCaptureError):
            finish(task)
        assert not task.state['complete'] and task.state['completed_inputs'] == 0
        assert task.state['input_manifest_sha256'] is None


def test_empty_declared_set_has_a_complete_empty_manifest(tmp_path):
    _, roots, _, _ = inputs(tmp_path)
    with InputSnapshotTask(roots, []) as task:
        finish(task)
        assert json.loads(task.manifest_bytes)['inputs'] == []
        assert task.state['captured_bytes'] == 0 and task.work_inputs() == []


def test_duplicate_input_cannot_be_counted_twice(tmp_path):
    _, roots, entries, _ = inputs(tmp_path)
    with pytest.raises(ValueError):
        InputSnapshotTask(roots, entries + [entries[0]])


def test_multiple_roots_have_distinct_logical_identities(tmp_path):
    a = tmp_path / 'first'; a.mkdir()
    b = tmp_path / 'second'; b.mkdir()
    (a / 'same').write_bytes(b'first'); (b / 'same').write_bytes(b'second')
    roots = {'a': ProjectBoundary(a), 'b': ProjectBoundary(b)}
    with InputSnapshotTask(roots, [{'root_id': 'b', 'path': 'same'},
                                  {'root_id': 'a', 'path': 'same'}]) as task:
        finish(task)
        assert task.read_input('a', 'same') == b'first'
        assert task.read_input('b', 'same') == b'second'


def test_live_capture_is_not_a_serializable_checkpoint(tmp_path):
    _, roots, entries, _ = inputs(tmp_path)
    with InputSnapshotTask(roots, entries) as task:
        with pytest.raises(TypeError):
            pickle.dumps(task)
        assert task.state['durable_checkpoint'] is False
