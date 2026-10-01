"""Deterministic basis rollback for interrupted committing transactions."""
import os
from pathlib import Path
from unittest.mock import patch
import pytest

from specroad.changes import (CommitPublicationError, CommittingJournal, RecoveryAuthority,
    RecoveryError, RolledBackJournal, project_lock, rollback_interrupted_transaction)
from support.committing import staged, publish
from support.folds import goal, edit, create
from support.publication import TRANSACTION, files
from support.targets import ACTOR, TIME

RECOVER = RecoveryAuthority('rollback-test-authorizer', '1', lambda request: True)


def recovery_options(journal):
    data = journal.data
    return dict(kind='recovery', command='recover run', project_id=data['project_id'],
                request_id=data['request_id'], transaction_id=data['transaction_id'])


def partial_commit(root, *, operations=None, artifacts=None):
    if operations is None and artifacts is None:
        a, b = goal(1), goal(2)
        artifacts = [a, b]
        operations = [edit(a, 'A'), edit(b, 'B')]
    with staged(root, operations=operations, artifacts=artifacts) as (model, plan, preflight, held, prepared):
        original_replace = os.replace
        targets = []
        def replace(src, dst, **kwargs):
            if dst != 'journal.json' and targets:
                raise OSError(5, 'stop before second target')
            result = original_replace(src, dst, **kwargs)
            if dst != 'journal.json':
                targets.append(dst)
            return result
        with patch.object(os, 'replace', side_effect=replace):
            with pytest.raises(CommitPublicationError):
                publish(preflight, prepared, held)
        journal = CommittingJournal(Path(root, prepared.path).read_bytes())
    return model, plan, journal


def recover(root, journal, *, authority=RECOVER, expected=None):
    with project_lock(root, **recovery_options(journal)) as held:
        return rollback_interrupted_transaction(TRANSACTION, held_lock=held,
            authority=authority, expected_journal_sha256=expected or journal.sha256)


def test_partial_committing_restores_exact_basis_bytes(tmp_path):
    a, b = goal(1), goal(2)
    model, plan, journal = partial_commit(tmp_path, artifacts=[a, b],
        operations=[edit(a, 'A'), edit(b, 'B')])
    assert files(tmp_path) != model.source_files
    result = recover(tmp_path, journal)
    assert files(tmp_path) == model.source_files
    assert result.data['state'] == 'rolled_back'
    assert result.data['base_model_root_sha256'] == journal.data['base_model_root_sha256']
    assert result.data['rollback_completed']
    terminal = RolledBackJournal(Path(tmp_path, journal.path).read_bytes())
    assert terminal.data['published_count'] == 0
    assert all(not entry['published'] for entry in terminal.data['files'])


def test_created_target_is_removed_from_basis_and_preserved_as_operational_evidence(tmp_path):
    base = goal(1)
    created = goal(0, revision=1, created_at=TIME, updated_at=TIME,
                   created_by=ACTOR, updated_by=ACTOR)
    model, plan, journal = partial_commit(tmp_path, operations=[create(created), edit(base, 'X')],
                                          artifacts=[base])
    created_entry = next(entry for entry in journal.data['files'] if not entry['existed_before'])
    assert Path(tmp_path, created_entry['path']).is_file()
    recover(tmp_path, journal)
    assert files(tmp_path) == model.source_files
    assert not Path(tmp_path, created_entry['path']).exists()
    rollback_dir = Path(tmp_path, journal.path).parent / 'rollback'
    removed = list(rollback_dir.glob('*.removed'))
    assert len(removed) == 1
    from hashlib import sha256
    assert removed[0].stat().st_size == created_entry['after_size']
    assert sha256(removed[0].read_bytes()).hexdigest() == created_entry['after_sha256']


def test_full_target_is_never_rolled_back(tmp_path):
    with staged(tmp_path) as (model, plan, preflight, held, prepared):
        publish(preflight, prepared, held)
        journal = CommittingJournal(Path(tmp_path, prepared.path).read_bytes())
    before = files(tmp_path)
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with pytest.raises(RecoveryError) as error:
            rollback_interrupted_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                expected_journal_sha256=journal.sha256)
    assert error.value.reason == 'recovery_full_target_requires_completion'
    assert files(tmp_path) == before


def test_wrong_expected_hash_refuses_before_mutation(tmp_path):
    model, plan, journal = partial_commit(tmp_path)
    before = {p.relative_to(tmp_path).as_posix(): p.read_bytes()
              for p in Path(tmp_path).rglob('*') if p.is_file() and p.name != 'project.json'}
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with pytest.raises(RecoveryError) as error:
            rollback_interrupted_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                expected_journal_sha256='0' * 64)
        assert error.value.exit_code == 6 and not error.value.mutation_possible
    after = {p.relative_to(tmp_path).as_posix(): p.read_bytes()
             for p in Path(tmp_path).rglob('*') if p.is_file() and p.name != 'project.json'}
    assert after == before


def test_denied_authority_does_not_enter_rolling_back(tmp_path):
    model, plan, journal = partial_commit(tmp_path)
    denied = RecoveryAuthority('deny', '1', lambda request: False)
    before = Path(tmp_path, journal.path).read_bytes()
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with pytest.raises(RecoveryError) as error:
            rollback_interrupted_transaction(TRANSACTION, held_lock=held, authority=denied,
                expected_journal_sha256=journal.sha256)
        assert error.value.exit_code == 7 and not error.value.mutation_possible
    assert Path(tmp_path, journal.path).read_bytes() == before
