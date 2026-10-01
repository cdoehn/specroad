"""Interrupted rollback remains resumable and never guesses recovery bytes."""
import json
import os
from pathlib import Path
from unittest.mock import patch
import pytest

from specroad.changes import (CommittingJournal, RecoveryError, RolledBackJournal,
    RollingBackJournal, project_lock, rollback_interrupted_transaction)
from specroad.changes import _recovery_rollback as rollback_impl
from support.folds import goal, edit
from support.publication import TRANSACTION, files
from test_transaction_recovery_rollback import RECOVER, partial_commit, recovery_options


def journal_value(root, path):
    raw = Path(root, path).read_bytes()
    state = json.loads(raw)['state']
    cls = {'committing': CommittingJournal, 'rolling_back': RollingBackJournal,
           'rolled_back': RolledBackJournal}[state]
    return cls(raw)


def invoke(root, journal):
    with project_lock(root, **recovery_options(journal)) as held:
        return rollback_interrupted_transaction(TRANSACTION, held_lock=held,
            authority=RECOVER, expected_journal_sha256=journal.sha256)


def test_interrupted_successor_file_is_reused_exactly(tmp_path):
    model, plan, journal = partial_commit(tmp_path)
    original = os.replace
    def stop_before_replace(src, dst, **kwargs):
        if src == 'journal.rollback' and dst == 'journal.json':
            raise OSError(5, 'injected before journal replace')
        return original(src, dst, **kwargs)
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with patch.object(rollback_impl.os, 'replace', side_effect=stop_before_replace):
            with pytest.raises(RecoveryError):
                rollback_interrupted_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                    expected_journal_sha256=journal.sha256)
    pending = Path(tmp_path, journal.path).parent / 'journal.rollback'
    assert pending.is_file()
    result = invoke(tmp_path, journal)
    assert result.data['rollback_completed']
    assert files(tmp_path) == model.source_files
    assert not pending.exists()


def test_lost_journal_replace_result_resumes_from_observed_successor(tmp_path):
    model, plan, journal = partial_commit(tmp_path)
    native = os.replace
    fired = False
    def lost(src, dst, **kwargs):
        nonlocal fired
        result = native(src, dst, **kwargs)
        if src == 'journal.rollback' and dst == 'journal.json' and not fired:
            fired = True
            raise OSError(5, 'lost journal replace result')
        return result
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with patch.object(rollback_impl.os, 'replace', side_effect=lost):
            with pytest.raises(RecoveryError):
                rollback_interrupted_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                    expected_journal_sha256=journal.sha256)
    current = journal_value(tmp_path, journal.path)
    assert isinstance(current, RollingBackJournal)
    result = invoke(tmp_path, current)
    assert result.data['rollback_completed'] and files(tmp_path) == model.source_files


def test_lost_target_restore_result_is_recognized_as_already_based(tmp_path):
    a, b = goal(1), goal(2)
    model, plan, journal = partial_commit(tmp_path, artifacts=[a, b],
        operations=[edit(a, 'A'), edit(b, 'B')])
    native = os.replace
    fired = False
    target_name = Path(journal.data['files'][0]['path']).name
    def lost(src, dst, **kwargs):
        nonlocal fired
        result = native(src, dst, **kwargs)
        if dst == target_name and src.endswith('.bin') and not fired:
            fired = True
            raise OSError(5, 'lost target replace result')
        return result
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with patch.object(rollback_impl.os, 'replace', side_effect=lost):
            with pytest.raises(RecoveryError):
                rollback_interrupted_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                    expected_journal_sha256=journal.sha256)
    current = journal_value(tmp_path, journal.path)
    assert isinstance(current, RollingBackJournal)
    result = invoke(tmp_path, current)
    assert result.data['rollback_completed'] and files(tmp_path) == model.source_files


def test_wrong_before_image_blocks_instead_of_guessing_basis(tmp_path):
    model, plan, journal = partial_commit(tmp_path)
    entry = journal.data['files'][0]
    path = Path(tmp_path, entry['before_image_path'])
    raw = path.read_bytes(); path.write_bytes(b'X' + raw[1:])
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with pytest.raises(RecoveryError) as error:
            rollback_interrupted_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                expected_journal_sha256=journal.sha256)
    assert error.value.mutation_possible
    assert files(tmp_path) != model.source_files


def test_unknown_live_target_bytes_block_before_rolling_back(tmp_path):
    model, plan, journal = partial_commit(tmp_path)
    entry = journal.data['files'][0]
    path = Path(tmp_path, entry['path'])
    path.write_bytes(b'not-the-base-or-target')
    before = Path(tmp_path, journal.path).read_bytes()
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with pytest.raises(RecoveryError) as error:
            rollback_interrupted_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                expected_journal_sha256=journal.sha256)
        assert error.value.reason == 'recovery_target_mismatch'
        assert not error.value.mutation_possible
    assert Path(tmp_path, journal.path).read_bytes() == before


def test_conflicting_pending_successor_is_never_overwritten(tmp_path):
    model, plan, journal = partial_commit(tmp_path)
    pending = Path(tmp_path, journal.path).parent / 'journal.rollback'
    pending.write_bytes(b'conflict')
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with pytest.raises(RecoveryError) as error:
            rollback_interrupted_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                expected_journal_sha256=journal.sha256)
    assert error.value.reason == 'recovery_journal_successor_conflict'
    assert pending.read_bytes() == b'conflict'


def test_retry_after_rolled_back_performs_no_second_normative_write(tmp_path):
    model, plan, journal = partial_commit(tmp_path)
    first = invoke(tmp_path, journal)
    terminal = journal_value(tmp_path, journal.path)
    before = files(tmp_path)
    with project_lock(tmp_path, **recovery_options(terminal)) as held:
        with patch.object(rollback_impl.os, 'replace', side_effect=AssertionError('second replace')):
            second = rollback_interrupted_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                expected_journal_sha256=terminal.sha256)
    assert first.data['rollback_completed'] and second.data['rollback_completed']
    assert second.data['normative_writes'] == 0
    assert files(tmp_path) == before == model.source_files


def test_read_only_recovery_status_validates_rolling_back_journal(tmp_path):
    from specroad.changes import inspect_recovery
    model, plan, journal = partial_commit(tmp_path)
    native = os.replace
    def stop(src, dst, **kwargs):
        result = native(src, dst, **kwargs)
        if src == 'journal.rollback' and dst == 'journal.json':
            raise OSError(5, 'stop after rolling_back marker')
        return result
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with patch.object(rollback_impl.os, 'replace', side_effect=stop):
            with pytest.raises(RecoveryError):
                rollback_interrupted_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                    expected_journal_sha256=journal.sha256)
    current = journal_value(tmp_path, journal.path)
    status = inspect_recovery(tmp_path, transaction_id=TRANSACTION,
                              expected_project_id=current.data['project_id'])
    row = status.data['transactions'][0]
    assert row['state'] == 'rolling_back'
    assert row['journal_schema_validated']
    assert row['state_actions'] == ['recover']
