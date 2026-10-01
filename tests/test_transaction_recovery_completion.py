"""Complete-target recovery reconstructs durable receipts without a new plan."""
from pathlib import Path
import pytest
from specroad.changes import (CommittingJournal, RecoveryAuthority, RecoveryError,
    TransactionReceipt, RequestReceipt, CommittedJournal, project_lock,
    complete_published_transaction)
from specroad.model.canonical import canonical_json_bytes
from support.receipts import published
from support.publication import TRANSACTION, files

RECOVER = RecoveryAuthority('test-recovery-authorizer', '1', lambda request: True)


def crash_after_last_target(root):
    with published(root) as (model, plan, preflight, held, journal):
        data = journal.data
        assert data['published_count'] == len(data['files']) == 1
        data['published_count'] = 0
        data['files'][0]['published'] = False
        crashed = CommittingJournal(canonical_json_bytes(data))
        Path(root, journal.path).write_bytes(crashed.source_bytes)
        target = {item['path']: Path(root, item['path']).read_bytes()
                  for item in data['target_inventory']}
    return model, plan, preflight, crashed, target


def recovery_options(journal, *, command='recover run'):
    data = journal.data
    return dict(kind='recovery', command=command, project_id=data['project_id'],
                request_id=data['request_id'], transaction_id=data['transaction_id'])


def recover(root, journal, **kwargs):
    with project_lock(root, **recovery_options(journal)) as held:
        return complete_published_transaction(TRANSACTION, held_lock=held,
            authority=kwargs.pop('authority', RECOVER),
            expected_journal_sha256=kwargs.pop('expected_journal_sha256', journal.sha256),
            **kwargs)


def test_last_target_crash_is_committed_without_republishing_target(tmp_path):
    model, plan, preflight, journal, target = crash_after_last_target(tmp_path)
    result = recover(tmp_path, journal)
    assert result.data['commit_completed'] and result.data['current_target_verified']
    assert result.data['normative_writes'] == 0
    assert files(tmp_path) == target
    committed = CommittedJournal(Path(tmp_path, journal.path).read_bytes())
    assert committed.data['state'] == 'committed'
    assert committed.data['published_count'] == len(committed.data['files'])
    assert all(entry['published'] for entry in committed.data['files'])


def test_recovery_reconstructs_normal_transaction_and_request_receipts_from_journal(tmp_path):
    model, plan, preflight, journal, target = crash_after_last_target(tmp_path)
    result = recover(tmp_path, journal)
    refs = result.data['receipts']
    transaction = TransactionReceipt(Path(tmp_path, refs['transaction']['path']).read_bytes())
    request = RequestReceipt(Path(tmp_path, refs['request']['path']).read_bytes())
    assert transaction.sha256 == refs['transaction']['sha256']
    assert request.sha256 == refs['request']['sha256']
    assert transaction.data['operations'] == plan.data['operations']
    assert transaction.data['operations_sha256'] == journal.data['authoring_binding']['operation_sequence_sha256']
    assert request.data['result_object'] == transaction.data['result_object']


def test_journal_binds_recovery_authoring_and_complete_target_inventory(tmp_path):
    model, plan, preflight, journal, target = crash_after_last_target(tmp_path)
    data = journal.data
    assert data['authoring_binding'] == preflight.request.data['authoring_binding']
    assert data['authoring_sha256'] == preflight.request.data['authoring_sha256']
    expected = sorted(model.source_files)
    assert [item['path'] for item in data['target_inventory']] == expected
    assert {item['path'] for item in data['target_inventory']} >= {entry['path'] for entry in data['files']}


def test_completion_requires_exact_recovery_lock_binding(tmp_path):
    model, plan, preflight, journal, target = crash_after_last_target(tmp_path)
    with project_lock(tmp_path, **recovery_options(journal, command='recover discard')) as held:
        with pytest.raises(RecoveryError) as error:
            complete_published_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                expected_journal_sha256=journal.sha256)
    assert error.value.exit_code == 6
    assert Path(tmp_path, journal.path).read_bytes() == journal.source_bytes
    assert files(tmp_path) == target


def test_completion_requires_exact_expected_journal_hash(tmp_path):
    model, plan, preflight, journal, target = crash_after_last_target(tmp_path)
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with pytest.raises(RecoveryError) as error:
            complete_published_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                expected_journal_sha256='0' * 64)
    assert error.value.exit_code == 6 and not error.value.mutation_possible
    assert Path(tmp_path, journal.path).read_bytes() == journal.source_bytes


def test_denied_recovery_authority_writes_no_receipt_or_marker(tmp_path):
    model, plan, preflight, journal, target = crash_after_last_target(tmp_path)
    denied = RecoveryAuthority('deny', '1', lambda request: False)
    before = {p.relative_to(tmp_path).as_posix(): p.read_bytes()
              for p in Path(tmp_path).rglob('*') if p.is_file()}
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with pytest.raises(RecoveryError) as error:
            complete_published_transaction(TRANSACTION, held_lock=held, authority=denied,
                expected_journal_sha256=journal.sha256)
        assert error.value.exit_code == 7 and not error.value.mutation_possible
    after = {p.relative_to(tmp_path).as_posix(): p.read_bytes()
             for p in Path(tmp_path).rglob('*') if p.is_file()}
    # The recovery lock itself is gone after leaving the context; no other bytes changed.
    before.pop('.specroad/locks/project.json', None)
    assert after == before
