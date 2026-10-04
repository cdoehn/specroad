"""First receipt failures retain original evidence and report possible mutation."""

import pytest

from specroad.changes import RecoveryError, complete_published_transaction, project_lock
from specroad.changes.receipt_projection import prepare_recovery_receipts
from support.publication import TRANSACTION, files
from support.recovery_writes import RecoveryWriteFault
from test_transaction_recovery_completion import RECOVER, crash_after_last_target, recovery_options
from test_transaction_recovery_completion_right import promoted, snapshot


@pytest.mark.parametrize('boundary', ['created', 'partial', 'synced'])
def test_first_receipt_failure_retains_bytes_and_reports_mutation(tmp_path, monkeypatch, boundary):
    model, plan, preflight, journal, target = crash_after_last_target(tmp_path)
    transaction, request, committed = prepare_recovery_receipts(promoted(journal))
    receipt_path = tmp_path / transaction.path
    before = snapshot(tmp_path)
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        mode = {'created': 'empty', 'partial': 'prefix', 'synced': 'file_sync'}[boundary]
        with RecoveryWriteFault(tmp_path, 'completion_transaction', mode) as fault:
            with pytest.raises(RecoveryError) as failure:
                complete_published_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                                                expected_journal_sha256=journal.sha256)
    assert fault.fired and fault.path == receipt_path and not receipt_path.exists()
    assert snapshot(tmp_path) == before
    assert files(tmp_path) == target
    diagnostic = failure.value.diagnostic()
    assert diagnostic['mutation_possible'] is True
    assert diagnostic['recovery_required'] is True
    assert diagnostic['normative_writes_by_recovery'] == 0
    assert not (tmp_path / request.path).exists()
    assert (tmp_path / journal.path).read_bytes() == journal.source_bytes


def test_first_receipt_conflict_remains_a_write_free_rejection(tmp_path):
    model, plan, preflight, journal, target = crash_after_last_target(tmp_path)
    transaction, request, committed = prepare_recovery_receipts(promoted(journal))
    receipt_path = tmp_path / transaction.path
    receipt_path.parent.mkdir(parents=True)
    receipt_path.write_bytes(b'foreign receipt')
    before = snapshot(tmp_path)
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with pytest.raises(RecoveryError) as failure:
            complete_published_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                                            expected_journal_sha256=journal.sha256)
    assert failure.value.reason == 'recovery_receipt_conflict'
    assert failure.value.mutation_possible is False
    assert snapshot(tmp_path) == before and files(tmp_path) == target
