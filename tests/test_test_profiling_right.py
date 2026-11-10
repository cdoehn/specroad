"""Raw import races, corrupt streams and inconsistent process outcomes stay visible."""
import os
import zlib

import pytest

from dev.profiling import artifacts
from dev.profiling.artifacts import capture, export
from dev.profiling.store import reader
from test_test_profiling import prepared_store


@pytest.mark.parametrize('kind', ['symlink', 'hardlink'])
def test_linked_raw_artifacts_are_rejected_before_admission(tmp_path, kind):
    store, directory = prepared_store(tmp_path)
    original = directory / 'original'
    original.write_bytes(b'kept source bytes')
    linked = directory / 'linked'
    if kind == 'symlink':
        linked.symlink_to(original)
    else:
        os.link(original, linked)
    with store, pytest.raises(ValueError):
        capture(store, 'run', directory, linked, kind='metadata')
    assert original.read_bytes() == b'kept source bytes'
    with reader(store.path) as db:
        assert db.execute('SELECT COUNT(*) FROM artifacts').fetchone()[0] == 0


@pytest.mark.parametrize('mutation', ['same_size', 'replace_inode'])
def test_changed_artifacts_keep_an_incomplete_import_and_cannot_be_exported(tmp_path, monkeypatch, mutation):
    store, directory = prepared_store(tmp_path)
    path = directory / 'raw.trace'
    original = b'raw syscall data'
    path.write_bytes(original)
    before = path.stat()
    native, changed = zlib.compress, []

    def interrupted(raw):
        packed = native(raw)
        if not changed:
            if mutation == 'replace_inode':
                path.rename(directory / 'retained')
                path.write_bytes(original)
            else:
                path.write_bytes(b'x' * len(original))
                os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
            changed.append(True)
        return packed

    monkeypatch.setattr(artifacts.zlib, 'compress', interrupted)
    with store:
        with pytest.raises(ValueError):
            capture(store, 'run', directory, path, kind='strace')
        identifier, state = store.db.execute('SELECT id,state FROM artifacts').fetchone()
        assert state == 'writing' and changed == [True]
        with pytest.raises(ValueError):
            capture(store, 'run', directory, path, kind='strace')
    output = directory / 'exported'
    with reader(store.path) as db, pytest.raises(ValueError):
        export(db, identifier, output)
    assert not output.exists()


def test_reimport_does_not_silently_associate_new_bytes_with_old_evidence(tmp_path):
    store, directory = prepared_store(tmp_path)
    path = directory / 'raw.trace'
    path.write_bytes(b'original')
    with store:
        identifier = capture(store, 'run', directory, path, kind='strace')
        path.write_bytes(b'modified')
        with pytest.raises(ValueError):
            capture(store, 'run', directory, path, kind='strace')
    output = directory / 'exported'
    with reader(store.path) as db:
        export(db, identifier, output)
    assert output.read_bytes() == b'original' and path.read_bytes() == b'modified'


@pytest.mark.parametrize('damage', ['gap', 'trailing', 'truncated', 'oversized'])
def test_corrupt_chunk_streams_never_publish_an_export(tmp_path, damage):
    store, directory = prepared_store(tmp_path)
    path = directory / 'profile.pstats'
    path.write_bytes(b'native raw profile')
    with store:
        identifier = capture(store, 'run', directory, path, kind='cprofile')
        raw_size, data = store.db.execute('SELECT raw_size,data FROM artifact_chunks').fetchone()
        with store.db:
            if damage == 'gap':
                store.db.execute('UPDATE artifact_chunks SET ordinal=1')
            else:
                altered = data + b'trailing' if damage == 'trailing' else data[:-1] if damage == 'truncated' else zlib.compress(b'x' * (raw_size + 1))
                store.db.execute('UPDATE artifact_chunks SET data=?', (altered,))
    output = directory / 'exported'
    with reader(store.path) as db, pytest.raises(ValueError):
        export(db, identifier, output)
    assert not output.exists() and not list(directory.glob('.profile-export-*'))


@pytest.mark.parametrize('exit_code', [1, None, False])
def test_complete_phases_do_not_hide_a_failed_or_unknown_process_exit(tmp_path, exit_code):
    store, _ = prepared_store(tmp_path)
    node = 'tests/test_one.py::test_one'
    before = dict(pid=123, tid=124, time_ns=100, monotonic_ns=10)
    after = dict(pid=123, tid=124, time_ns=200, monotonic_ns=110)
    with store:
        store.begin_test('run', node, 'gw0', 123, 124, 0, 100)
        for name in ('setup', 'call', 'teardown'):
            store.phase('run', node, name, before, after, {}, tmp_path)
            store.phase_outcome('run', node, name, 'passed')
        store.end_test('run', node, 200)
        assert store.finish('run', 'passed', exit_code, outcomes={'test_one': 'passed'}) == 'failed'
    with reader(store.path) as db:
        assert tuple(db.execute('SELECT status,error IS NOT NULL FROM runs').fetchone()) == ('failed', 1)
