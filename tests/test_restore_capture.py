"""Capture observes bounded original bytes, never a qualification or write grant."""
from hashlib import sha256
import errno
import os

import pytest

from specroad.recovery import RestoreError
from specroad.security import ProjectBoundary, SafetyViolation
from specroad.work._restore_capture import (BLOCK, capture, chunk_bytes,
    enumerate_entries, units_for, assembled)
from support.read_only import inventory, no_write_attempts


def captured_file(tmp_path):
    root = tmp_path / 'source'; root.mkdir()
    path = root / 'source.bin'
    raw = b'a' * BLOCK + b'b' * BLOCK + b'last bytes'
    path.write_bytes(raw)
    rows = enumerate_entries(ProjectBoundary(root), ['source.bin'])
    tasks = units_for([], rows, [])
    return root, path, raw, tasks


def test_capture_uses_every_declared_byte_and_keeps_the_original_task_boundaries(tmp_path):
    root, path, raw, tasks = captured_file(tmp_path)
    before = inventory(tmp_path)
    with no_write_attempts():
        records = [capture({'--source-root': str(root)}, t) for t in tasks[:-2]]
        chunks = [chunk_bytes(t, r) for t, r in zip(tasks, records)]
        source, current, observed = assembled(tasks, [{'chunk': r} for r in records], [])
    assert [len(b) for b in chunks] == [BLOCK, BLOCK, 10]
    assert b''.join(chunks) == raw and source == {'source.bin': raw} and current == {}
    assert all(r['sha256'] == sha256(b).hexdigest() for r, b in zip(records, chunks))
    assert inventory(tmp_path) == before and observed['entries'] == []


@pytest.mark.parametrize('fault', ['rewrite', 'truncate', 'replace', 'hardlink', 'symlink'])
def test_capture_detects_a_changed_source_before_reporting_its_chunk(tmp_path, monkeypatch, fault):
    root, path, raw, tasks = captured_file(tmp_path)
    native = os.read
    reached = []
    def read(fd, size):
        result = native(fd, size)
        if not reached and os.fstat(fd).st_ino == path.stat().st_ino:
            reached.append(True)
            if fault == 'rewrite':
                path.write_bytes(b'c' * len(raw))
            elif fault == 'truncate':
                path.write_bytes(b'')
            elif fault == 'replace':
                replacement = root / 'replacement'
                replacement.write_bytes(raw)
                os.replace(replacement, path)
            elif fault == 'hardlink':
                os.link(path, root / 'alias')
            else:
                path.rename(root / 'moved')
                path.symlink_to('moved')
        return result
    monkeypatch.setattr(os, 'read', read)
    with pytest.raises((RestoreError, SafetyViolation)):
        capture({'--source-root': str(root)}, tasks[0])
    assert reached


@pytest.mark.parametrize('fault', ['short-read', 'io'])
def test_capture_cannot_report_missing_or_unreadable_bytes_as_progress(tmp_path, monkeypatch, fault):
    root, path, raw, tasks = captured_file(tmp_path)
    native = os.read
    inode = path.stat().st_ino
    def read(fd, size):
        if os.fstat(fd).st_ino == inode:
            if fault == 'short-read':
                return b''
            raise OSError(errno.EIO, 'Synthetic original read failure')
        return native(fd, size)
    monkeypatch.setattr(os, 'read', read)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError if fault == 'short-read' else OSError):
        capture({'--source-root': str(root)}, tasks[0])
    assert inventory(tmp_path) == before
