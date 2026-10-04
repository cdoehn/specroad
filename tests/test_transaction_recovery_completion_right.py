"""Robust complete-target recovery: mismatch refusal and exact retry semantics."""
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from specroad.changes import (CommittedJournal, CommittingJournal, RecoveryAuthority,
    RecoveryError, TransactionReceipt, RequestReceipt, project_lock,
    complete_published_transaction)
from specroad.changes.receipt_projection import prepare_recovery_receipts
from specroad.model.canonical import canonical_json_bytes
from support.publication import TRANSACTION, files
from test_transaction_recovery_completion import (RECOVER, crash_after_last_target,
    recover, recovery_options)


def promoted(journal):
    data = journal.data
    data['published_count'] = len(data['files'])
    for entry in data['files']:
        entry['published'] = True
    return CommittingJournal(canonical_json_bytes(data))


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in Path(root).rglob('*') if p.is_file() and p.name != 'project.json'}


def test_missing_changed_target_blocks_completion_before_receipts(tmp_path):
    model, plan, preflight, journal, target = crash_after_last_target(tmp_path)
    Path(tmp_path, journal.data['files'][0]['path']).unlink()
    before = snapshot(tmp_path)
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with pytest.raises(RecoveryError) as error:
            complete_published_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                expected_journal_sha256=journal.sha256)
        assert not error.value.mutation_possible
    assert snapshot(tmp_path) == before


def test_wrong_changed_target_hash_blocks_completion_before_receipts(tmp_path):
    model, plan, preflight, journal, target = crash_after_last_target(tmp_path)
    path = Path(tmp_path, journal.data['files'][0]['path'])
    raw = path.read_bytes(); path.write_bytes(b'X' + raw[1:])
    before = snapshot(tmp_path)
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with pytest.raises(RecoveryError):
            complete_published_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                expected_journal_sha256=journal.sha256)
    assert snapshot(tmp_path) == before


def test_unchanged_normative_resource_is_part_of_complete_target_proof(tmp_path):
    model, plan, preflight, journal, target = crash_after_last_target(tmp_path)
    path = Path(tmp_path, 'profiles/core.json')
    raw = path.read_bytes(); path.write_bytes(b' ' + raw)
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with pytest.raises(RecoveryError) as error:
            complete_published_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                expected_journal_sha256=journal.sha256)
        assert error.value.reason == 'recovery_target_mismatch'
    assert not Path(tmp_path, '.specroad/requests').exists()


def test_exact_existing_transaction_receipt_is_resumed_not_rewritten(tmp_path):
    model, plan, preflight, journal, target = crash_after_last_target(tmp_path)
    transaction, request, committed = prepare_recovery_receipts(promoted(journal))
    path = Path(tmp_path, transaction.path); path.parent.mkdir(parents=True)
    path.write_bytes(transaction.source_bytes)
    stat = path.stat()
    result = recover(tmp_path, journal)
    assert result.data['commit_completed']
    assert path.read_bytes() == transaction.source_bytes
    assert (path.stat().st_dev, path.stat().st_ino) == (stat.st_dev, stat.st_ino)
    assert Path(tmp_path, request.path).read_bytes() == request.source_bytes


def test_exact_existing_both_receipts_are_resumed_without_rewrite(tmp_path):
    model, plan, preflight, journal, target = crash_after_last_target(tmp_path)
    transaction, request, committed = prepare_recovery_receipts(promoted(journal))
    stats = {}
    for record in (transaction, request):
        path = Path(tmp_path, record.path); path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(record.source_bytes); stats[record.path] = path.stat().st_ino
    result = recover(tmp_path, journal)
    assert result.data['commit_completed']
    assert all(Path(tmp_path, path).stat().st_ino == inode for path, inode in stats.items())


@pytest.mark.parametrize('which', ['transaction', 'request'])
def test_conflicting_existing_receipt_is_never_overwritten(tmp_path, which):
    model, plan, preflight, journal, target = crash_after_last_target(tmp_path)
    transaction, request, committed = prepare_recovery_receipts(promoted(journal))
    record = transaction if which == 'transaction' else request
    path = Path(tmp_path, record.path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'{"foreign":true}')
    before = snapshot(tmp_path)
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with pytest.raises(RecoveryError) as error:
            complete_published_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                expected_journal_sha256=journal.sha256)
        assert error.value.reason == 'recovery_receipt_conflict'
    assert path.read_bytes() == b'{"foreign":true}'
    # A transaction receipt may have been created before a conflicting request
    # receipt is discovered; the conflict itself is never overwritten.
    assert Path(tmp_path, journal.path).read_bytes() == journal.source_bytes


def test_exact_interrupted_completion_marker_is_resumed(tmp_path):
    model, plan, preflight, journal, target = crash_after_last_target(tmp_path)
    transaction, request, committed = prepare_recovery_receipts(promoted(journal))
    for record in (transaction, request):
        path = Path(tmp_path, record.path); path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(record.source_bytes)
    pending = Path(tmp_path, journal.path).with_name('journal.complete')
    pending.write_bytes(committed.source_bytes)
    result = recover(tmp_path, journal)
    assert result.data['commit_completed']
    assert not pending.exists()
    assert Path(tmp_path, journal.path).read_bytes() == committed.source_bytes


def test_conflicting_interrupted_completion_marker_is_preserved_and_blocks(tmp_path):
    model, plan, preflight, journal, target = crash_after_last_target(tmp_path)
    pending = Path(tmp_path, journal.path).with_name('journal.complete')
    pending.write_bytes(b'foreign marker')
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with pytest.raises(RecoveryError) as error:
            complete_published_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                expected_journal_sha256=journal.sha256)
        assert error.value.reason == 'recovery_completion_marker_conflict'
    assert pending.read_bytes() == b'foreign marker'
    assert Path(tmp_path, journal.path).read_bytes() == journal.source_bytes


def test_retry_after_completed_recovery_performs_no_second_write(tmp_path):
    model, plan, preflight, journal, target = crash_after_last_target(tmp_path)
    first = recover(tmp_path, journal)
    committed = CommittedJournal(Path(tmp_path, journal.path).read_bytes())
    with project_lock(tmp_path, **recovery_options(committed.predecessor)) as held:
        with patch('os.write', side_effect=AssertionError('no write')), \
             patch('specroad.changes.recovery.os.replace', side_effect=AssertionError('no replace')):
            second = complete_published_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                expected_journal_sha256=committed.sha256)
    assert second.data['receipts'] == first.data['receipts']
    assert second.data['normative_writes'] == 0
    assert files(tmp_path) == target


def test_authority_mutating_target_after_initial_proof_is_detected(tmp_path):
    model, plan, preflight, journal, target = crash_after_last_target(tmp_path)
    path = Path(tmp_path, journal.data['files'][0]['path'])
    def mutate(request):
        raw = path.read_bytes(); path.write_bytes(b'X' + raw[1:]); return True
    authority = RecoveryAuthority('mutating-host', '1', mutate)
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with pytest.raises(RecoveryError) as error:
            complete_published_transaction(TRANSACTION, held_lock=held, authority=authority,
                expected_journal_sha256=journal.sha256)
        assert not error.value.mutation_possible
    assert Path(tmp_path, journal.path).read_bytes() == journal.source_bytes


@pytest.mark.parametrize('field', ['authoring_sha256', 'authoring_binding'])
def test_forged_recovery_binding_is_not_a_valid_journal(tmp_path, field):
    model, plan, preflight, journal, target = crash_after_last_target(tmp_path)
    data = journal.data
    if field == 'authoring_sha256': data[field] = '0' * 64
    else: data[field]['operations'] = []
    with pytest.raises(Exception):
        CommittingJournal(canonical_json_bytes(data))


def test_target_inventory_cannot_omit_a_changed_after_image(tmp_path):
    model, plan, preflight, journal, target = crash_after_last_target(tmp_path)
    data = journal.data
    changed = data['files'][0]['path']
    data['target_inventory'] = [item for item in data['target_inventory'] if item['path'] != changed]
    with pytest.raises(Exception):
        CommittingJournal(canonical_json_bytes(data))
