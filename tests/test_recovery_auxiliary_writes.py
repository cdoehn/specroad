"""Repeated interruptions of recovery derivatives preserve sources and progress."""
import json
import os
from unittest.mock import patch

import pytest

from specroad.changes import RecoveryError, RecoveryAuthority, LockRecord, ProjectLockError
from support.publication import files, TRANSACTION
from support.recovery_writes import (AUTHORITY, SITES, RecoveryWriteFault, fd_path,
    invoke, journal_at, scenario, snapshot)
from test_terminal_recovery import cleanup, writer
from test_transaction_recovery_lock import child, takeover


@pytest.mark.parametrize('site', SITES)
@pytest.mark.parametrize('mode', ['empty', 'prefix', 'file_sync', 'link_before', 'link_after', 'parent_sync'])
def test_auxiliary_interruption_resumes_without_repeated_normative_effect(tmp_path, site, mode):
    journal, expected, expected_root = scenario(tmp_path, site)
    original = {p: raw for p, raw in snapshot(tmp_path).items() if '/before/' in p or '/staging/' in p}
    native, replaced = os.replace, []
    def replace(src, dst, **kwargs):
        target = fd_path(kwargs['dst_dir_fd']) / dst
        result = native(src, dst, **kwargs)
        if target.relative_to(tmp_path).as_posix() in expected:
            replaced.append(target)
        return result
    with patch.object(os, 'replace', side_effect=replace):
        for _ in range(2 if mode in ('empty', 'prefix', 'file_sync', 'link_before') else 1):
            with RecoveryWriteFault(tmp_path, site, mode) as fault:
                with pytest.raises(RecoveryError) as failure:
                    invoke(tmp_path, journal.path, site)
            assert fault.fired and failure.value.mutation_possible
            if mode in ('link_after', 'parent_sync'):
                assert fault.path.read_bytes() == fault.expected and fault.path.stat().st_nlink == 1
            else:
                assert not fault.path.exists()
        result = invoke(tmp_path, journal.path, site)
        assert files(tmp_path) == expected
        root_key = 'base_model_root_sha256' if site.startswith('rollback_') else 'target_model_root_sha256'
        assert result.data[root_key] == expected_root
        assert len(replaced) == len(set(replaced)) == (1 if site.startswith('rollback_') else 0)
        before = snapshot(tmp_path)
        assert invoke(tmp_path, journal.path, site).data['normative_writes'] == 0
        assert snapshot(tmp_path) == before
    assert all(snapshot(tmp_path)[path] == raw for path, raw in original.items())
    current = journal_at(tmp_path, journal.path)
    assert cleanup(tmp_path, current).data['cleanup_completed']
    with writer(tmp_path):
        pass
    assert files(tmp_path) == expected


@pytest.mark.parametrize('site', SITES)
@pytest.mark.parametrize('kind', ['empty', 'prefix', 'conflict', 'extended', 'symlink', 'hardlink', 'directory', 'fifo'])
def test_foreign_auxiliary_file_remains_a_blocker(tmp_path, site, kind):
    root = tmp_path / 'project'
    journal, _, _ = scenario(root, site)
    with RecoveryWriteFault(root, site, 'empty') as fault:
        with pytest.raises(RecoveryError):
            invoke(root, journal.path, site)
    assert fault.fired and not fault.path.exists()
    path, expected = fault.path, fault.expected
    raw = {'empty': b'', 'prefix': expected[:17], 'conflict': b'foreign',
           'extended': expected + b'foreign'}.get(kind, expected)
    outside = tmp_path / 'foreign'
    if kind in ('symlink', 'hardlink'):
        outside.write_bytes(raw)
        if kind == 'symlink': path.symlink_to(outside)
        else: os.link(outside, path)
    elif kind == 'directory': path.mkdir()
    elif kind == 'fifo': os.mkfifo(path)
    else: path.write_bytes(raw)
    before, identity = snapshot(root), path.lstat().st_ino
    for _ in range(2):
        with pytest.raises(RecoveryError):
            invoke(root, journal.path, site)
        assert snapshot(root) == before and path.lstat().st_ino == identity
    if kind in ('symlink', 'hardlink'):
        assert outside.read_bytes() == raw


@pytest.mark.parametrize('site', SITES)
def test_foreign_prefix_at_publication_is_not_replaced(tmp_path, site):
    journal, _, _ = scenario(tmp_path, site)
    def foreign(fault):
        fault.path.write_bytes(fault.expected[:17])
    with RecoveryWriteFault(tmp_path, site, 'observe', on_link=foreign) as fault:
        with pytest.raises(RecoveryError):
            invoke(tmp_path, journal.path, site)
    assert fault.staged and fault.path.read_bytes() == fault.expected[:17]
    before = snapshot(tmp_path)
    with pytest.raises(RecoveryError): invoke(tmp_path, journal.path, site)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('site', SITES)
@pytest.mark.parametrize('changed', ['journal', 'target'])
def test_auxiliary_publication_rechecks_live_sources(tmp_path, site, changed):
    journal, _, _ = scenario(tmp_path, site)
    path = tmp_path / (journal.path if changed == 'journal' else journal.data['files'][0]['path'])
    recorded = []
    def mutate(fd, fault):
        path.write_bytes(b'foreign source')
        recorded.append(snapshot(tmp_path))
    with RecoveryWriteFault(tmp_path, site, 'observe', on_stage=mutate) as fault:
        with pytest.raises(RecoveryError):
            invoke(tmp_path, journal.path, site)
    assert recorded and fault.staged and not fault.path.exists()
    assert snapshot(tmp_path) == recorded[0] and path.read_bytes() == b'foreign source'


@pytest.mark.parametrize('site', ['rollback_audit', 'completion_audit', 'rollback_receipt'])
def test_complete_evidence_keeps_original_authority_after_retry(tmp_path, site):
    journal, expected, _ = scenario(tmp_path, site)
    with RecoveryWriteFault(tmp_path, site, 'link_after') as fault:
        with pytest.raises(RecoveryError): invoke(tmp_path, journal.path, site)
    assert fault.fired
    records = {p: raw for p, raw in snapshot(tmp_path).items()
               if p.startswith(('.specroad/recovery/transaction-audit/', '.specroad/transactions/receipts/'))}
    identities = {p: (tmp_path / p).stat().st_ino for p in records}
    other = RecoveryAuthority('later-recovery-authority', '2', lambda request: True)
    invoke(tmp_path, journal.path, site, authority=other)
    assert all(snapshot(tmp_path)[p] == raw for p, raw in records.items())
    assert all((tmp_path / p).stat().st_ino == inode for p, inode in identities.items())
    action = next(json.loads(raw) for p, raw in records.items() if p.endswith(('/complete.json', '/rollback.json')))
    assert action['authority_id'] == AUTHORITY.authority_id
    assert files(tmp_path) == expected


@pytest.mark.parametrize('site', SITES)
@pytest.mark.parametrize('mode', ['empty', 'prefix'])
def test_real_auxiliary_process_stop_resumes_through_native_lock_takeover(tmp_path, site, mode):
    journal, expected, _ = scenario(tmp_path, site)
    original = {p: raw for p, raw in snapshot(tmp_path).items() if '/before/' in p or '/staging/' in p}
    child(tmp_path, '''
from support.recovery_writes import RecoveryWriteFault, invoke
with RecoveryWriteFault(root, sys.argv[4], sys.argv[5], process_stop=True):
    invoke(root, sys.argv[3], sys.argv[4])
raise AssertionError('process stop not reached')
''', journal.path, site, mode, exit_code=23)
    current = journal_at(tmp_path, journal.path)
    lock = LockRecord((tmp_path / '.specroad/locks/project.json').read_bytes())
    from specroad.changes import complete_published_transaction, rollback_interrupted_transaction
    operation = rollback_interrupted_transaction if site.startswith('rollback_') else complete_published_transaction
    with takeover(tmp_path, lock, current) as held:
        result = operation(TRANSACTION, held_lock=held, authority=AUTHORITY,
                           expected_journal_sha256=current.sha256)
        assert result.data['normative_writes'] <= 1 and files(tmp_path) == expected
    assert all(snapshot(tmp_path)[path] == raw for path, raw in original.items())
    assert invoke(tmp_path, journal.path, site).data['normative_writes'] == 0
    assert cleanup(tmp_path, journal_at(tmp_path, journal.path)).data['cleanup_completed']
    with writer(tmp_path): pass


@pytest.mark.parametrize('site', SITES)
def test_changed_native_owner_blocks_auxiliary_publication(tmp_path, site):
    journal, _, _ = scenario(tmp_path, site)
    lock = tmp_path / '.specroad/locks/project.json'
    recorded = []
    def mutate(fd, fault):
        lock.write_bytes(b'foreign lock owner')
        recorded.append(snapshot(tmp_path))
    with RecoveryWriteFault(tmp_path, site, 'observe', on_stage=mutate) as fault:
        with pytest.raises((RecoveryError, ProjectLockError)):
            invoke(tmp_path, journal.path, site)
    assert recorded and not fault.path.exists()
    assert snapshot(tmp_path) == recorded[0] and lock.read_bytes() == b'foreign lock owner'


@pytest.mark.parametrize('site', ['rollback_copy', 'completion_request', 'rollback_receipt'])
def test_changed_before_image_or_prior_evidence_blocks_publication(tmp_path, site):
    journal, _, _ = scenario(tmp_path, site)
    recorded, changed = [], []
    def mutate(fd, fault):
        if site == 'rollback_copy':
            path = tmp_path / journal.data['files'][0]['before_image_path']
        elif site == 'completion_request':
            path, = (tmp_path / '.specroad/transactions/receipts').glob('*/transaction.json')
        else:
            path, = (tmp_path / '.specroad/recovery/transaction-audit').glob('*/rollback.json')
        path.write_bytes(b'foreign bound source')
        changed.append(path)
        recorded.append(snapshot(tmp_path))
    with RecoveryWriteFault(tmp_path, site, 'observe', on_stage=mutate) as fault:
        with pytest.raises(RecoveryError): invoke(tmp_path, journal.path, site)
    assert recorded and not fault.path.exists() and snapshot(tmp_path) == recorded[0]
    assert changed[0].read_bytes() == b'foreign bound source'


@pytest.mark.parametrize('site', ['rollback_copy', 'completion_transaction', 'completion_marker', 'completion_audit'])
@pytest.mark.parametrize('damage', ['truncated', 'changed'])
def test_incomplete_or_changed_staging_is_not_published(tmp_path, site, damage):
    journal, expected, _ = scenario(tmp_path, site)
    def corrupt(fd, fault):
        if damage == 'truncated':
            os.ftruncate(fd, 17)
        else:
            os.lseek(fd, 0, os.SEEK_SET)
            os.write(fd, b'X')
    with RecoveryWriteFault(tmp_path, site, 'observe', on_stage=corrupt) as fault:
        with pytest.raises(RecoveryError) as failure: invoke(tmp_path, journal.path, site)
    assert fault.staged and failure.value.reason == 'recovery_stage_changed'
    assert not fault.path.exists()
    invoke(tmp_path, journal.path, site)
    assert files(tmp_path) == expected


@pytest.mark.parametrize('site', ['rollback_copy', 'completion_transaction'])
@pytest.mark.parametrize('count', [0, -1, True, '17', 999999])
def test_invalid_native_write_count_leaves_sources_retryable(tmp_path, site, count):
    journal, expected, _ = scenario(tmp_path, site)
    fault = RecoveryWriteFault(tmp_path, site, 'observe')
    native_write = fault.write
    def write(fd, raw):
        if fd == fault.fd:
            return count
        return native_write(fd, raw)
    fault.write = write
    with fault:
        with pytest.raises(RecoveryError) as failure: invoke(tmp_path, journal.path, site)
    assert fault.path is not None and failure.value.reason == 'recovery_stage_short_write'
    assert not fault.path.exists()
    invoke(tmp_path, journal.path, site)
    assert files(tmp_path) == expected


def test_existing_completion_marker_is_synced_before_journal_replacement(tmp_path, monkeypatch):
    site = 'completion_marker'
    journal, expected, _ = scenario(tmp_path, site)
    with RecoveryWriteFault(tmp_path, site, 'link_after') as fault:
        with pytest.raises(RecoveryError): invoke(tmp_path, journal.path, site)
    assert fault.fired
    before, inode = snapshot(tmp_path), fault.path.stat().st_ino
    native, fired = os.fsync, []
    def unavailable(fd):
        if fd_path(fd) == fault.path:
            fired.append(True)
            raise OSError(5, 'pending marker synchronization unavailable')
        return native(fd)
    with monkeypatch.context() as patching:
        patching.setattr(os, 'fsync', unavailable)
        with pytest.raises(RecoveryError): invoke(tmp_path, journal.path, site)
    assert fired and snapshot(tmp_path) == before and fault.path.stat().st_ino == inode
    assert (tmp_path / journal.path).read_bytes() == journal.source_bytes
    assert invoke(tmp_path, journal.path, site).data['commit_completed']
    assert files(tmp_path) == expected
