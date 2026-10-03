"""Durability loss and interrupted archival retain evidence and active blockers."""
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from specroad.changes import (RecoveryError, RolledBackJournal, CommittedJournal,
    ProjectLockError, project_lock, rollback_interrupted_transaction,
    complete_published_transaction, transaction_receipt_path)
from support.publication import TRANSACTION, files
from support.recovery import pending, discard, recovery_options as discard_options, tree
from test_terminal_recovery import terminal, cleanup, writer, RECOVER
from test_transaction_recovery_completion import crash_after_last_target, recovery_options
from test_transaction_recovery_rollback import partial_commit


def fd_path(fd):
    return Path(os.readlink('/proc/self/fd/' + str(fd)))


def fail_sync(monkeypatch, predicate):
    native = os.fsync
    fired = []
    def sync(fd):
        native(fd)
        if not fired and predicate(fd_path(fd)):
            fired.append(True)
            raise OSError(5, 'injected unconfirmed synchronization')
    monkeypatch.setattr(os, 'fsync', sync)
    return fired


@pytest.mark.parametrize('name', ['rollback.json', 'transaction.json', 'complete.json'])
def test_terminal_evidence_fsync_loss_resumes_without_normative_rewrite(tmp_path, monkeypatch, name):
    if name == 'complete.json':
        model, plan, preflight, journal, expected = crash_after_last_target(tmp_path)
        action, cls = complete_published_transaction, CommittedJournal
    else:
        model, plan, journal = partial_commit(tmp_path)
        expected, action, cls = model.source_files, rollback_interrupted_transaction, RolledBackJournal
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with monkeypatch.context() as faults:
            fired = fail_sync(faults, lambda path: path.name == name)
            with pytest.raises(RecoveryError) as failure:
                action(TRANSACTION, held_lock=held, authority=RECOVER, expected_journal_sha256=journal.sha256)
        assert fired and failure.value.mutation_possible
    terminal_journal = cls(Path(tmp_path, journal.path).read_bytes())
    assert files(tmp_path) == expected
    with project_lock(tmp_path, **recovery_options(terminal_journal)) as held:
        with patch('os.replace', side_effect=AssertionError('second normative replace')):
            again = action(TRANSACTION, held_lock=held, authority=RECOVER,
                           expected_journal_sha256=terminal_journal.sha256)
    assert again.data['normative_writes'] == 0 and files(tmp_path) == expected
    assert cleanup(tmp_path, terminal_journal).data['cleanup_completed']


@pytest.mark.parametrize('outcome', ['rollback', 'complete'])
@pytest.mark.parametrize('boundary', ['marker', 'intent', 'barrier', 'rename_before', 'rename_after',
                                     'parent_sync', 'completed', 'unlink_before', 'unlink_after'])
def test_cleanup_durable_boundaries_resume_with_preserved_bytes(tmp_path, monkeypatch, outcome, boundary):
    journal, expected, result = terminal(tmp_path, outcome)
    work = Path(tmp_path, journal.path).parent
    before = {p.relative_to(work).as_posix(): p.read_bytes() for p in work.rglob('*') if p.is_file()}
    fired = []
    with monkeypatch.context() as faults:
        if boundary.startswith('rename') or boundary.startswith('unlink'):
            native = os.rename if boundary.startswith('rename') else os.unlink
            def interrupt(name, *args, **kwargs):
                selected = (name == TRANSACTION if boundary.startswith('rename')
                            else str(name).startswith('pending-cleanup-'))
                if selected and not fired:
                    fired.append(True)
                    if boundary.endswith('after'):
                        native(name, *args, **kwargs)
                    raise OSError(5, 'injected operation response loss')
                return native(name, *args, **kwargs)
            faults.setattr(os, 'rename' if boundary.startswith('rename') else 'unlink', interrupt)
        else:
            def selected(path):
                if boundary == 'marker': return path.name in ('committed.json', 'rolled_back.json')
                if boundary == 'intent': return path.name == 'intent.json'
                if boundary == 'barrier': return path.name.startswith('pending-cleanup-')
                if boundary == 'completed': return path.name == 'completed.json'
                return path == tmp_path / '.specroad/transactions' and not work.exists()
            fired = fail_sync(faults, selected)
        with pytest.raises(RecoveryError) as failure:
            cleanup(tmp_path, journal)
    assert fired and failure.value.mutation_possible
    assert failure.value.diagnostic()['recovery_required']
    assert files(tmp_path) == expected
    if boundary != 'unlink_after':
        with pytest.raises(ProjectLockError):
            with writer(tmp_path):
                pass
    cleaned = cleanup(tmp_path, journal).data
    assert cleaned['cleanup_completed'] and not cleaned['recovery_required']
    archive = Path(tmp_path, cleaned['archive_path'])
    assert {p.relative_to(archive).as_posix(): p.read_bytes() for p in archive.rglob('*') if p.is_file()} == before
    assert files(tmp_path) == expected
    with writer(tmp_path):
        pass


@pytest.mark.parametrize('state', ['building', 'prepared'])
@pytest.mark.parametrize('boundary', ['terminal', 'receipt', 'rename', 'completed'])
def test_discard_reuses_original_event_after_lost_completion(tmp_path, monkeypatch, state, boundary):
    model, plan, preflight, journal = pending(tmp_path, state=state)
    fired = []
    with project_lock(tmp_path, **discard_options(preflight)) as held:
        with monkeypatch.context() as faults:
            if boundary in ('terminal', 'rename'):
                native = os.replace if boundary == 'terminal' else os.rename
                def lost(name, *args, **kwargs):
                    result = native(name, *args, **kwargs)
                    if not fired and name == ('journal.discard' if boundary == 'terminal' else TRANSACTION):
                        fired.append(True)
                        raise OSError(5, 'lost discard boundary')
                    return result
                faults.setattr(os, 'replace' if boundary == 'terminal' else 'rename', lost)
            else:
                fired = fail_sync(faults, lambda path: path.name == (
                    'transaction.json' if boundary == 'receipt' else 'completed.json'))
            with pytest.raises(RecoveryError) as failure:
                discard(preflight, journal, held)
        assert fired and failure.value.mutation_possible
    with pytest.raises(ProjectLockError):
        with writer(tmp_path):
            pass
    intent_path, = Path(tmp_path, '.specroad/recovery/transaction-audit').glob('*/intent.json')
    intent_raw, inode = intent_path.read_bytes(), intent_path.stat().st_ino
    with project_lock(tmp_path, **discard_options(preflight)) as held:
        result = discard(preflight, journal, held).data
    assert result['discard_completed'] and result['remaining_active_paths'] == []
    assert result['audit_path'] == intent_path.parent.relative_to(tmp_path).as_posix()
    assert intent_path.read_bytes() == intent_raw and intent_path.stat().st_ino == inode
    assert files(tmp_path) == model.source_files
    before = tree(tmp_path)
    with project_lock(tmp_path, **discard_options(preflight)) as held:
        with patch('os.write', side_effect=AssertionError('repeat write')):
            assert discard(preflight, journal, held).data == result
    assert tree(tmp_path) == before


@pytest.mark.parametrize('name', ['rollback.json', 'transaction.json'])
def test_short_terminal_evidence_stays_blocked_and_is_not_overwritten(tmp_path, monkeypatch, name):
    model, plan, journal = partial_commit(tmp_path)
    native = os.write
    partial = []
    def short(fd, data):
        if fd_path(fd).name == name:
            if partial:
                raise OSError(28, 'no space for evidence')
            partial.append(fd_path(fd))
            return native(fd, data[:17])
        return native(fd, data)
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with monkeypatch.context() as faults:
            faults.setattr(os, 'write', short)
            with pytest.raises(RecoveryError) as failure:
                rollback_interrupted_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                                                  expected_journal_sha256=journal.sha256)
    assert failure.value.mutation_possible and len(partial[0].read_bytes()) == 17
    current = RolledBackJournal(Path(tmp_path, journal.path).read_bytes())
    before = tree(tmp_path)
    with project_lock(tmp_path, **recovery_options(current)) as held:
        with pytest.raises(RecoveryError):
            rollback_interrupted_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                                              expected_journal_sha256=current.sha256)
    assert tree(tmp_path) == before and files(tmp_path) == model.source_files


def test_lost_archive_then_tampered_evidence_keeps_pending_and_foreign_blockers(tmp_path, monkeypatch):
    journal, expected, result = terminal(tmp_path)
    foreign = tmp_path / '.specroad/recovery/foreign.json'
    foreign.parent.mkdir(exist_ok=True)
    foreign.write_bytes(b'foreign recovery')
    native = os.rename
    def lost(*args, **kwargs):
        native(*args, **kwargs)
        raise OSError(5, 'lost archive response')
    with monkeypatch.context() as faults:
        faults.setattr(os, 'rename', lost)
        with pytest.raises(RecoveryError): cleanup(tmp_path, journal)
    barrier, = (tmp_path / '.specroad/recovery').glob('pending-cleanup-*.json')
    receipt = tmp_path / transaction_receipt_path(TRANSACTION)
    receipt.write_bytes(b'foreign receipt')
    before = tree(tmp_path)
    with pytest.raises(RecoveryError): cleanup(tmp_path, journal)
    assert tree(tmp_path) == before and barrier.exists() and foreign.read_bytes() == b'foreign recovery'
    assert files(tmp_path) == expected


def test_changed_receipt_during_cleanup_completion_never_clears_pending(tmp_path, monkeypatch):
    journal, expected, result = terminal(tmp_path)
    native = os.fsync
    fired = []
    def sync(fd):
        native(fd)
        if not fired and fd_path(fd).name == 'completed.json':
            fired.append(True)
            (tmp_path / transaction_receipt_path(TRANSACTION)).write_bytes(b'changed receipt')
    with monkeypatch.context() as faults:
        faults.setattr(os, 'fsync', sync)
        with pytest.raises(RecoveryError): cleanup(tmp_path, journal)
    assert fired and list((tmp_path / '.specroad/recovery').glob('pending-cleanup-*.json'))
    assert files(tmp_path) == expected
