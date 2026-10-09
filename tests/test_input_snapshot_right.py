"""Actual source closure, native writer exclusion and retained partial bytes."""

import copy
import errno
import json
import os
import stat
import subprocess

import pytest

from specroad.changes import project_lock
from specroad.changes._lock_files import LockFiles
from specroad.changes.lock_values import ProjectLockError
from specroad.security import ProjectBoundary
from specroad.work.snapshot import InputSnapshotTask, SnapshotCaptureError
from support.project_locks import attempt, child_program, options, orphan
from support.read_only import inventory, make_project, no_write_attempts
from test_input_snapshot import finish, inputs


def captured(task):
    while task.state['completed_inputs'] < task.state['expected_inputs']:
        task.advance(1)
    assert not task.state['complete']
    assert task.state['input_manifest_sha256'] is None


def project(tmp_path):
    root = tmp_path / 'project'; root.mkdir()
    make_project(root)
    (root / 'input.bin').write_bytes(b'abcdefgh')
    return root, {'project': ProjectBoundary(root)}, [{'root_id': 'project', 'path': 'input.bin'}]


def failure(task, reason=None, path=None):
    with pytest.raises(SnapshotCaptureError) as error:
        finish(task)
    state = task.state
    assert not state['complete'] and state['phase'] == 'failed'
    assert state['model_root_sha256'] is None and state['input_manifest_sha256'] is None
    assert not state['atomic_project_snapshot'] and not state['durable_checkpoint']
    if reason is not None:
        assert error.value.reason == reason
    if path is not None:
        assert error.value.path == path
    return error.value


@pytest.mark.parametrize('change', ['rewrite', 'grow', 'truncate', 'replace'])
def test_previously_captured_changed_file_cannot_seal_the_set(tmp_path, change):
    root, roots, entries, values = inputs(tmp_path, {'a': b'abcdefgh', 'b': b'last'})
    with InputSnapshotTask(roots, entries, block_bytes=2) as task:
        captured(task)
        if change == 'replace':
            (root / 'a').rename(root / 'old')
        (root / 'a').write_bytes({'rewrite': b'XXXXXXXX', 'grow': b'abcdefgh-more',
                                 'truncate': b'a', 'replace': b'new bytes'}[change])
        failure(task, 'source_content_changed', 'a')
        assert task.read_input('source', 'a') == values['a']
        assert task.read_input('source', 'b') == values['b']
        assert task.state['validation_bytes'] > 0
        before = task.state
        with pytest.raises(SnapshotCaptureError):
            task.advance(100)
        assert task.state == before


def test_same_size_and_restored_mtime_are_not_a_content_proof(tmp_path):
    root, roots, entries, _ = inputs(tmp_path, {'file': b'abcdefgh'})
    with InputSnapshotTask(roots, entries, block_bytes=3) as task:
        captured(task)
        path = root / 'file'; before = path.stat()
        path.write_bytes(b'ABCDEFGH')
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        assert path.stat().st_size == before.st_size
        assert path.stat().st_mtime_ns == before.st_mtime_ns
        failure(task, 'source_content_changed', 'file')
        assert task.state['validation_bytes'] == 8


@pytest.mark.parametrize('change', ['timestamp', 'same_bytes', 'replacement'])
def test_changed_source_is_reread_once_and_only_hash_identical_bytes_are_accepted(tmp_path, monkeypatch, change):
    root, roots, entries, _ = inputs(tmp_path, {'file': b'abcdefgh'})
    reads = []; native = os.read
    def observe(fd, count):
        offset = os.lseek(fd, 0, os.SEEK_CUR)
        data = native(fd, count)
        reads.append((offset, len(data)))
        return data
    with InputSnapshotTask(roots, entries, block_bytes=3) as task:
        captured(task)
        path = root / 'file'
        if change == 'timestamp':
            info = path.stat()
            os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns + 1000000))
        elif change == 'replacement':
            path.rename(root / 'old'); path.write_bytes(b'abcdefgh')
        else:
            path.write_bytes(b'abcdefgh')
        monkeypatch.setattr('specroad.work.snapshot.os.read', observe)
        state = finish(task)
        assert state['validated_inputs'] == state['revalidated_inputs'] == 1
        assert state['validation_bytes'] == 8
        assert reads == [(0, 3), (3, 3), (6, 2), (8, 0)]
        assert task.read_input('source', 'file') == b'abcdefgh'


def test_source_lost_after_capture_names_the_resource_and_preserves_its_bytes(tmp_path):
    root, roots, entries, _ = inputs(tmp_path, {'file': b'captured'})
    with InputSnapshotTask(roots, entries) as task:
        captured(task)
        (root / 'file').unlink()
        error = failure(task, 'source_missing', 'file')
        assert error.root_id == 'source'
        assert task.read_input('source', 'file') == b'captured'


@pytest.mark.parametrize('replacement', ['symlink', 'directory', 'fifo', 'socket'])
def test_unsafe_replacement_after_capture_is_never_followed_or_opened_as_data(tmp_path, replacement):
    root, roots, entries, _ = inputs(tmp_path, {'file': b'captured'})
    outside = tmp_path / 'outside'; outside.write_bytes(b'foreign')
    with InputSnapshotTask(roots, entries) as task:
        captured(task)
        path = root / 'file'; path.unlink()
        if replacement == 'symlink':
            path.symlink_to(outside)
        elif replacement == 'directory':
            path.mkdir()
        elif replacement == 'fifo':
            os.mkfifo(path)
        else:
            os.mknod(path, stat.S_IFSOCK | 0o600)
        failure(task, 'unsafe_or_changed_source', 'file')
        assert task.read_input('source', 'file') == b'captured'
        assert outside.read_bytes() == b'foreign'


def test_final_closure_catches_a_change_after_an_earlier_validation_unit(tmp_path):
    root, roots, entries, _ = inputs(tmp_path, {'a': b'first', 'b': b'last'})
    with InputSnapshotTask(roots, entries) as task:
        captured(task)
        while task.state['validated_inputs'] < 1:
            task.advance(1)
        (root / 'a').write_bytes(b'later')
        failure(task, 'source_changed_during_closure', 'a')
        assert task.read_input('source', 'a') == b'first'


@pytest.mark.parametrize('kind', ['writer', 'recovery', 'operational'])
def test_existing_native_project_guard_blocks_capture_before_source_bytes(tmp_path, kind):
    root, roots, entries = project(tmp_path)
    with project_lock(root, **options(kind)) as held:
        before = inventory(root)
        with no_write_attempts(), InputSnapshotTask(roots, entries) as task:
            error = failure(task, 'source_writer_busy')
            assert error.root_id == 'project'
            assert task.state['captured_bytes'] == 0
            assert task.objects == {}
        assert held.check() and inventory(root) == before


def test_native_mutex_blocks_even_without_a_lock_record(tmp_path):
    root, roots, entries = project(tmp_path)
    before = inventory(root)
    with LockFiles(root) as held:
        held.acquire()
        with no_write_attempts(), InputSnapshotTask(roots, entries) as task:
            failure(task, 'source_writer_busy')
    assert inventory(root) == before


@pytest.mark.parametrize('kind', ['writer', 'recovery', 'operational'])
def test_live_capture_excludes_real_child_writers_and_releases_at_seal(tmp_path, kind):
    root, roots, entries = project(tmp_path)
    before = inventory(root)
    with InputSnapshotTask(roots, entries, block_bytes=2) as task:
        with no_write_attempts():
            task.advance(3)
        assert attempt(root, kind) == {'acquired': False, 'reason': 'project_lock_busy'}
        assert inventory(root) == before
        with no_write_attempts():
            finish(task)
        assert inventory(root) == before
        manifest = task.manifest_bytes
        assert attempt(root, kind)['acquired']
        assert task.manifest_bytes == manifest


def test_close_releases_the_mutex_without_removing_partial_bytes(tmp_path):
    root, roots, entries = project(tmp_path)
    task = InputSnapshotTask(roots, entries, block_bytes=2)
    task.advance(3)
    digest = task.state['inputs'][0]['chunks'][0]['sha256']
    task.close()
    assert attempt(root)['acquired']
    assert task.read_block(digest) == b'ab' and not task.state['complete']


def test_orphan_record_is_preserved_and_never_treated_as_permission(tmp_path):
    root, roots, entries = project(tmp_path)
    orphan(root)
    before = inventory(root)
    with no_write_attempts(), InputSnapshotTask(roots, entries) as task:
        failure(task, 'source_operational_state_unknown', '.specroad/locks/project.json')
        assert task.state['captured_bytes'] == 0
    assert inventory(root) == before


@pytest.mark.parametrize('path,reason', [
    ('.specroad/transactions/pending.json', 'source_recovery_required'),
    ('.specroad/recovery/pending.json', 'source_recovery_required'),
    ('.specroad/unknown.json', 'source_operational_state_unknown'),
])
def test_unresolved_operational_data_blocks_capture_without_repair(tmp_path, path, reason):
    root, roots, entries = project(tmp_path)
    file = root / path; file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(b'untouched unresolved bytes')
    before = inventory(root)
    with no_write_attempts(), InputSnapshotTask(roots, entries) as task:
        failure(task, reason, path)
        assert task.state['captured_bytes'] == 0
    assert inventory(root) == before


def test_transaction_appearing_during_capture_prevents_final_confirmation(tmp_path):
    root, roots, entries = project(tmp_path)
    with InputSnapshotTask(roots, entries) as task:
        captured(task)
        pending = root / '.specroad/transactions/pending.json'
        pending.parent.mkdir(parents=True); pending.write_bytes(b'unresolved')
        before = inventory(root)
        with no_write_attempts():
            failure(task, 'source_recovery_required', '.specroad/transactions/pending.json')
        assert inventory(root) == before
        assert task.read_input('project', 'input.bin') == b'abcdefgh'


def test_later_root_lock_failure_releases_the_earlier_root(tmp_path):
    first = tmp_path / 'first'; first.mkdir()
    second = tmp_path / 'second'; second.mkdir()
    make_project(first); make_project(second)
    (first / 'file').write_bytes(b'a'); (second / 'file').write_bytes(b'b')
    roots = {'a': ProjectBoundary(first), 'b': ProjectBoundary(second)}
    entries = [{'root_id': name, 'path': 'file'} for name in roots]
    with project_lock(second, **options()):
        with InputSnapshotTask(roots, entries) as task:
            error = failure(task, 'source_writer_busy')
            assert error.root_id == 'b' and task.state['captured_bytes'] == 0
        assert attempt(first)['acquired']


def test_distinct_logical_roots_can_share_one_native_source_mutex(tmp_path):
    root, roots, _, _ = inputs(tmp_path, {'file': b'same bytes'})
    roots['alias'] = ProjectBoundary(root)
    entries = [{'root_id': name, 'path': 'file'} for name in roots]
    with no_write_attempts(), InputSnapshotTask(roots, entries) as task:
        finish(task)
        assert task.read_input('source', 'file') == task.read_input('alias', 'file') == b'same bytes'


def test_replaced_root_prevents_sealing_and_keeps_captured_data(tmp_path):
    root, roots, entries, _ = inputs(tmp_path, {'file': b'original'})
    with InputSnapshotTask(roots, entries) as task:
        captured(task)
        root.rename(tmp_path / 'original'); root.mkdir()
        (root / 'file').write_bytes(b'original')
        failure(task, 'source_guard_changed')
        assert task.read_input('source', 'file') == b'original'


def test_repeated_source_failures_do_not_leak_descriptors_or_mutexes(tmp_path):
    root, roots, _ = project(tmp_path)
    baseline = len(os.listdir('/proc/self/fd'))
    for _ in range(20):
        with InputSnapshotTask(roots, [{'root_id': 'project', 'path': 'missing'}]) as task:
            failure(task, 'source_missing', 'missing')
    assert len(os.listdir('/proc/self/fd')) == baseline
    assert attempt(root)['acquired']


@pytest.mark.parametrize('operation', [copy.copy, copy.deepcopy])
def test_live_capture_cannot_be_copied(tmp_path, operation):
    _, roots, entries, _ = inputs(tmp_path)
    with InputSnapshotTask(roots, entries) as task:
        with pytest.raises(TypeError):
            operation(task)
        finish(task)


def test_forked_child_cannot_advance_or_unlock_the_parent_capture(tmp_path):
    root, _, _ = project(tmp_path)
    # Fork in a standalone single-threaded interpreter, not in an xdist worker.
    program = '''
import json, os
from specroad.security import ProjectBoundary
from specroad.work.snapshot import InputSnapshotTask, SnapshotCaptureError
from specroad.changes._lock_files import LockFiles
from specroad.changes.lock_values import ProjectLockError
root = sys.argv[1]
with InputSnapshotTask({'project': ProjectBoundary(root)},
        [{'root_id': 'project', 'path': 'input.bin'}]) as task:
    task.advance(3)
    before = task.state
    reader, writer = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(reader)
        try:
            task.advance(1)
            result = 'unexpected success'
        except SnapshotCaptureError as error:
            result = error.reason
        task.close()
        os.write(writer, json.dumps(result).encode())
        os.close(writer)
        os._exit(0)
    os.close(writer)
    try:
        result = os.read(reader, 4096)
    finally:
        os.close(reader)
    _, status = os.waitpid(pid, 0)
    blocked = False
    try:
        with LockFiles(root) as other:
            other.acquire()
    except ProjectLockError as error:
        blocked = error.reason == 'project_lock_busy'
    unchanged = task.state == before
    while not task.state['complete']:
        task.advance(1)
    sealed = task.state['complete']
with LockFiles(root) as other:
    other.acquire()
    other.require_held()
print(json.dumps({'child_exit': os.waitstatus_to_exitcode(status),
    'child_reason': json.loads(result), 'unchanged': unchanged,
    'parent_mutex_retained': blocked, 'sealed': sealed, 'released': True}))
'''
    done = subprocess.run(child_program(program, root), check=True, capture_output=True, text=True)
    assert json.loads(done.stdout) == {'child_exit': 0, 'child_reason': 'capture_not_owned',
        'unchanged': True, 'parent_mutex_retained': True, 'sealed': True, 'released': True}


def test_native_guard_unavailability_cannot_be_downgraded_to_an_unlocked_capture(tmp_path, monkeypatch):
    _, roots, entries, _ = inputs(tmp_path)
    def unavailable(self):
        raise ProjectLockError('native_lock_unavailable')
    monkeypatch.setattr(LockFiles, '__enter__', unavailable)
    with no_write_attempts(), InputSnapshotTask(roots, entries) as task:
        failure(task, 'source_guard_unavailable')
        assert task.state['captured_bytes'] == 0


def test_reread_io_failure_keeps_original_bytes_and_releases_native_guard(tmp_path, monkeypatch):
    root, roots, entries = project(tmp_path)
    with InputSnapshotTask(roots, entries) as task:
        captured(task)
        (root / 'input.bin').write_bytes(b'abcdefgh')
        with monkeypatch.context() as scoped:
            def failed_read(fd, count):
                raise OSError(errno.EIO, 'injected source device failure')
            scoped.setattr('specroad.work.snapshot.os.read', failed_read)
            failure(task, 'source_io_failure', 'input.bin')
        assert task.read_input('project', 'input.bin') == b'abcdefgh'
        assert attempt(root)['acquired']
