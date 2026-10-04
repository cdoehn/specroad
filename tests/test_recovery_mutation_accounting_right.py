"""Recovery mutation diagnostics follow real operational write boundaries."""
import os
from pathlib import Path

import pytest

from specroad.changes import RecoveryError, complete_published_transaction, project_lock
from specroad.changes import _recovery_completion as completion
from specroad.changes._recovery_evidence import evidence_root
from specroad.changes.receipt_projection import prepare_recovery_receipts
from support.publication import TRANSACTION, files
from support.recovery_writes import RecoveryWriteFault
from test_transaction_recovery_completion import RECOVER, crash_after_last_target, recover, recovery_options
from test_transaction_recovery_completion_right import promoted, snapshot


def seed(root, record):
    path = root / record.path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(record.source_bytes)


def fd_path(fd):
    return Path(os.readlink('/proc/self/fd/' + str(fd)))


def interrupt_file(fault, path, boundary):
    root = Path(*path.parts[:path.parts.index('.specroad')])
    site = 'completion_marker' if path.name == 'journal.complete' else 'completion_request'
    mode = {'created': 'empty', 'partial': 'prefix', 'synced': 'file_sync'}[boundary]
    interruption = RecoveryWriteFault(root, site, mode)
    for name, function in (('open', interruption.opening), ('write', interruption.writing),
                           ('fsync', interruption.syncing), ('link', interruption.linking)):
        fault.setattr(os, name, function)
    return interruption


def check_failure(error, mutation):
    diagnostic = error.diagnostic()
    assert diagnostic['mutation_possible'] is mutation
    assert diagnostic['recovery_required'] is True
    assert diagnostic['discard_completed'] is False
    assert diagnostic['normative_writes_by_recovery'] == 0


@pytest.mark.parametrize('which', ['transaction', 'request'])
@pytest.mark.parametrize('boundary', ['mkdir', 'parent_sync'])
def test_receipt_directory_failure_preserves_created_directory(tmp_path, monkeypatch, which, boundary):
    _, _, _, journal, target = crash_after_last_target(tmp_path)
    transaction, request, committed = prepare_recovery_receipts(promoted(journal))
    record = transaction if which == 'transaction' else request
    if which == 'request':
        seed(tmp_path, transaction)
    parts = Path(record.path).parts
    new_directory = next(tmp_path.joinpath(*parts[:i]) for i in range(1, len(parts))
                         if not tmp_path.joinpath(*parts[:i]).exists())
    before = snapshot(tmp_path)
    directories = {p.relative_to(tmp_path) for p in tmp_path.rglob('*') if p.is_dir()}
    native_mkdir, native_sync = os.mkdir, os.fsync
    created, fired = [], []

    def mkdir(name, *args, **kwargs):
        native_mkdir(name, *args, **kwargs)
        parent = fd_path(kwargs['dir_fd']) if kwargs.get('dir_fd') is not None else Path.cwd()
        if parent / name == new_directory:
            created.append(True)
            if boundary == 'mkdir':
                fired.append(True)
                raise OSError(5, 'injected directory creation response loss')

    def sync(fd):
        native_sync(fd)
        if created and fd_path(fd) == new_directory.parent:
            fired.append(True)
            raise OSError(5, 'injected parent synchronization response loss')

    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with monkeypatch.context() as fault:
            fault.setattr(os, 'mkdir', mkdir)
            if boundary == 'parent_sync':
                fault.setattr(os, 'fsync', sync)
            with pytest.raises(RecoveryError) as failure:
                complete_published_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                    expected_journal_sha256=journal.sha256)
    assert created and fired and new_directory.is_dir()
    check_failure(failure.value, True)
    assert {p.relative_to(tmp_path) for p in tmp_path.rglob('*') if p.is_dir()} == (
        directories | {new_directory.relative_to(tmp_path)})
    assert snapshot(tmp_path) == before and files(tmp_path) == target


@pytest.mark.parametrize('existing_transaction', [False, True])
@pytest.mark.parametrize('boundary', ['created', 'partial', 'synced'])
def test_request_failure_preserves_receipts_and_original_journal(tmp_path, monkeypatch,
                                                                 existing_transaction, boundary):
    _, _, _, journal, target = crash_after_last_target(tmp_path)
    transaction, request, committed = prepare_recovery_receipts(promoted(journal))
    if existing_transaction:
        seed(tmp_path, transaction)
        inode = (tmp_path / transaction.path).stat().st_ino
    before = snapshot(tmp_path)
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with monkeypatch.context() as fault:
            fired = interrupt_file(fault, tmp_path / request.path, boundary)
            with pytest.raises(RecoveryError) as failure:
                complete_published_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                    expected_journal_sha256=journal.sha256)
    assert fired.fired
    check_failure(failure.value, True)
    assert not (tmp_path / request.path).exists()
    assert snapshot(tmp_path) == {**before, transaction.path: transaction.source_bytes}
    assert files(tmp_path) == target
    if existing_transaction:
        assert (tmp_path / transaction.path).stat().st_ino == inode


@pytest.mark.parametrize('existing_transaction', [False, True])
def test_request_conflict_reports_only_this_calls_writes(tmp_path, existing_transaction):
    _, _, _, journal, target = crash_after_last_target(tmp_path)
    transaction, request, committed = prepare_recovery_receipts(promoted(journal))
    if existing_transaction:
        seed(tmp_path, transaction)
    path = tmp_path / request.path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'foreign request receipt')
    before = snapshot(tmp_path)
    with pytest.raises(RecoveryError) as failure:
        recover(tmp_path, journal)
    assert failure.value.reason == 'recovery_receipt_conflict'
    check_failure(failure.value, not existing_transaction)
    assert snapshot(tmp_path) == {**before, transaction.path: transaction.source_bytes}
    assert files(tmp_path) == target


@pytest.mark.parametrize('existing_receipts', [False, True])
def test_marker_conflict_distinguishes_prior_receipt_writes(tmp_path, existing_receipts):
    _, _, _, journal, target = crash_after_last_target(tmp_path)
    transaction, request, committed = prepare_recovery_receipts(promoted(journal))
    if existing_receipts:
        for record in (transaction, request):
            seed(tmp_path, record)
    pending = (tmp_path / journal.path).with_name('journal.complete')
    pending.write_bytes(b'foreign marker')
    before = snapshot(tmp_path)
    with pytest.raises(RecoveryError) as failure:
        recover(tmp_path, journal)
    assert failure.value.reason == 'recovery_completion_marker_conflict'
    check_failure(failure.value, not existing_receipts)
    assert snapshot(tmp_path) == {**before, transaction.path: transaction.source_bytes,
                                 request.path: request.source_bytes}
    assert files(tmp_path) == target


@pytest.mark.parametrize('boundary', ['created', 'partial', 'synced', 'replace_before',
                                     'replace_after', 'parent_sync'])
def test_marker_failure_reports_retained_operational_state(tmp_path, monkeypatch, boundary):
    _, _, _, journal, target = crash_after_last_target(tmp_path)
    transaction, request, committed = prepare_recovery_receipts(promoted(journal))
    for record in (transaction, request):
        seed(tmp_path, record)
    pending = (tmp_path / journal.path).with_name('journal.complete')
    if boundary.startswith('replace'):
        pending.write_bytes(committed.source_bytes)
    before = snapshot(tmp_path)
    fired, replaced = [], []
    native_replace, native_sync = os.replace, os.fsync

    def replace(source, target, **kwargs):
        selected = source == 'journal.complete'
        if selected and boundary == 'replace_before':
            fired.append(True)
            raise OSError(5, 'injected replacement failure')
        result = native_replace(source, target, **kwargs)
        if selected:
            replaced.append(True)
            if boundary == 'replace_after':
                fired.append(True)
                raise OSError(5, 'injected replacement response loss')
        return result

    def sync(fd):
        native_sync(fd)
        if replaced and fd_path(fd) == pending.parent:
            fired.append(True)
            raise OSError(5, 'injected journal directory sync failure')

    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with monkeypatch.context() as fault:
            if boundary in ('created', 'partial', 'synced'):
                fired = interrupt_file(fault, pending, boundary)
            else:
                fault.setattr(os, 'replace', replace)
                if boundary == 'parent_sync':
                    fault.setattr(os, 'fsync', sync)
            with pytest.raises(RecoveryError) as failure:
                complete_published_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                    expected_journal_sha256=journal.sha256)
    assert fired.fired if isinstance(fired, RecoveryWriteFault) else fired
    check_failure(failure.value, True)
    expected = dict(before)
    if replaced:
        expected[journal.path] = committed.source_bytes
        expected.pop(pending.relative_to(tmp_path).as_posix(), None)
    elif boundary == 'replace_before':
        expected[pending.relative_to(tmp_path).as_posix()] = committed.source_bytes
    else:
        assert not pending.exists()
    assert snapshot(tmp_path) == expected and files(tmp_path) == target


@pytest.mark.parametrize('existing_audit', [False, True])
def test_terminal_retry_retains_audit_creation_in_later_error(tmp_path, monkeypatch, existing_audit):
    _, _, _, journal, target = crash_after_last_target(tmp_path)
    transaction, request, committed = prepare_recovery_receipts(promoted(journal))
    for record in (transaction, request, committed):
        seed(tmp_path, record)
    action_path = evidence_root(TRANSACTION) + '/complete.json'
    if existing_audit:
        recover(tmp_path, committed)
    before = snapshot(tmp_path)
    synced = []
    native_sync, native_lock = os.fsync, completion._completion_lock

    def sync(fd):
        native_sync(fd)
        if fd_path(fd) == tmp_path / action_path:
            synced.append(True)

    def late_lock(*args):
        native_lock(*args)
        if synced:
            raise RecoveryError('injected_post_audit_lock_failure', exit_code=6)

    with project_lock(tmp_path, **recovery_options(committed)) as held:
        with monkeypatch.context() as fault:
            fault.setattr(os, 'fsync', sync)
            fault.setattr(completion, '_completion_lock', late_lock)
            with pytest.raises(RecoveryError) as failure:
                complete_published_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                    expected_journal_sha256=committed.sha256)
    assert synced and failure.value.reason == 'injected_post_audit_lock_failure'
    check_failure(failure.value, not existing_audit)
    raw = (tmp_path / action_path).read_bytes()
    assert snapshot(tmp_path) == {**before, action_path: raw}
    assert files(tmp_path) == target
    # A later explicit retry reuses the exact audit and never writes a target.
    inode = (tmp_path / action_path).stat().st_ino
    result = recover(tmp_path, committed)
    assert result.data['commit_completed'] and result.data['normative_writes'] == 0
    assert (tmp_path / action_path).stat().st_ino == inode
    assert snapshot(tmp_path) == {**before, action_path: raw} and files(tmp_path) == target


def test_terminal_retry_rejects_foreign_audit_without_mutation(tmp_path):
    _, _, _, journal, target = crash_after_last_target(tmp_path)
    transaction, request, committed = prepare_recovery_receipts(promoted(journal))
    for record in (transaction, request, committed):
        seed(tmp_path, record)
    path = tmp_path / evidence_root(TRANSACTION) / 'complete.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'{"foreign":true}')
    before = snapshot(tmp_path)
    with pytest.raises(RecoveryError) as failure:
        recover(tmp_path, committed)
    assert failure.value.reason == 'recovery_action_conflict'
    check_failure(failure.value, False)
    assert snapshot(tmp_path) == before and files(tmp_path) == target


def test_foreign_audit_appearing_before_creation_is_not_our_mutation(tmp_path, monkeypatch):
    _, _, _, journal, target = crash_after_last_target(tmp_path)
    transaction, request, committed = prepare_recovery_receipts(promoted(journal))
    for record in (transaction, request, committed):
        seed(tmp_path, record)
    path = tmp_path / evidence_root(TRANSACTION) / 'complete.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    before = snapshot(tmp_path)
    native_stat = os.stat
    probes, inserted = [], []

    def stat(name, *args, **kwargs):
        parent = fd_path(kwargs['dir_fd']) if kwargs.get('dir_fd') is not None else Path.cwd()
        if parent / name == path:
            probes.append(True)
            # Another writer appears after the missing-record checks, before
            # our exclusive creation branch is entered.
            if len(probes) == 3:
                path.write_bytes(b'{"foreign":true}')
                inserted.append(True)
        return native_stat(name, *args, **kwargs)

    with project_lock(tmp_path, **recovery_options(committed)) as held:
        with monkeypatch.context() as fault:
            fault.setattr(os, 'stat', stat)
            with pytest.raises(RecoveryError) as failure:
                complete_published_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                    expected_journal_sha256=committed.sha256)
    assert inserted and failure.value.reason == 'recovery_receipt_conflict'
    check_failure(failure.value, False)
    assert snapshot(tmp_path) == {**before, path.relative_to(tmp_path).as_posix(): b'{"foreign":true}'}
    assert files(tmp_path) == target
