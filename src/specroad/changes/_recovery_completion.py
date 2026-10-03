"""Completion sequence for a journal whose full target is already published."""
import os
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..security import paths as guards
from .committing_values import CommittingJournal
from .execution_values import ChangeExecutionError
from .locking import HeldProjectLock
from ._recovery_binding import check_run_lock as _completion_lock
from .receipt_projection import prepare_recovery_receipts
from .receipt_values import CommittedJournal, TransactionCompletion
from .recovery_values import RecoveryAuthority, RecoveryError
from ._journal_codec import _hash, _transaction
from ._journal_io import _read
from ._recovery_inputs import _read_journal, _parse
from ._recovery_receipts import (
    ensure_recovery_record,
    existing_recovery_record,
    recheck_recovery_record,
)
from ._recovery_target import fully_published, prove_complete_target
from ._staging_files import _image
from ._recovery_evidence import EvidenceRecord, recovery_action, sync_evidence


def _authorize_completion(authority, journal):
    request = {
        'action': 'complete',
        'transaction_id': journal.data['transaction_id'],
        'project_id': journal.data['project_id'],
        'request_id': journal.data['request_id'],
        'journal_sha256': journal.sha256,
        'base_model_root_sha256': journal.data['base_model_root_sha256'],
        'target_model_root_sha256': journal.data['target_model_root_sha256'],
    }
    request_raw = canonical_json_bytes(request)
    try:
        allowed = authority.check(request)
    except Exception as error:
        raise RecoveryError('recovery_authority_failed', exit_code=7) from error
    if canonical_json_bytes(request) != request_raw or type(allowed) is not bool or not allowed:
        raise RecoveryError('recovery_not_authorized', exit_code=7)


def _verify_committed_recovery(files, journal, held_lock, authority, *, write_new):
    """Verify completion; preserve or finish its immutable recovery action record."""
    predecessor = journal.predecessor
    _completion_lock(held_lock, predecessor)
    observed_journal = _read_journal(files, journal.data['transaction_id'])
    target = prove_complete_target(files, predecessor)
    _authorize_completion(authority, predecessor)
    _completion_lock(held_lock, predecessor)
    if prove_complete_target(files, predecessor) != target:
        raise RecoveryError('recovery_target_changed', exit_code=6)
    transaction, request_receipt, expected = prepare_recovery_receipts(predecessor)
    if expected.source_bytes != journal.source_bytes:
        raise RecoveryError('recovery_committed_binding_mismatch', exit_code=6)
    tokens = []
    for record in (transaction, request_receipt):
        if record is None:
            continue
        token = existing_recovery_record(files, record)
        if token is None:
            raise RecoveryError('recovery_receipt_missing', path=record.path, exit_code=6)
        recheck_recovery_record(files, record, token)
        tokens.append((record, token))
    if prove_complete_target(files, predecessor) != target:
        raise RecoveryError('recovery_target_changed', exit_code=6)
    if _read_journal(files, journal.data['transaction_id']) != observed_journal:
        raise RecoveryError('recovery_journal_changed', exit_code=6)
    for record, token in tokens:
        sync_evidence(files, record, token)
    marker = EvidenceRecord(journal.path, journal.source_bytes)
    sync_evidence(files, marker, existing_recovery_record(files, marker))
    recovery_action(files, journal, 'complete', authority=authority, write_new=write_new)
    _completion_lock(held_lock, journal)
    if prove_complete_target(files, predecessor) != target:
        raise RecoveryError('recovery_target_changed', exit_code=6)
    if _read_journal(files, journal.data['transaction_id']) != observed_journal:
        raise RecoveryError('recovery_journal_changed', exit_code=6)
    for record, token in tokens:
        recheck_recovery_record(files, record, token)
    return TransactionCompletion._create(journal, live=True)


def _commit_recovered_journal(files, journal, committed, directory_identity, *,
                              write_new, replace):
    prefix = tuple(journal.path.split('/')[:-1])
    with files.directory(prefix) as directory:
        if directory is None or guards._identity(os.fstat(directory)) != directory_identity:
            raise RecoveryError('recovery_work_changed', exit_code=6)
        if _read(directory, 'journal.json') != journal.source_bytes:
            raise RecoveryError('recovery_journal_changed', exit_code=6)
        pending = 'journal.complete'
        try:
            info = os.stat(pending, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            identity = write_new(directory, pending, committed.source_bytes)
        else:
            guards._regular(info)
            identity = guards._identity(info)
            try:
                existing = _read(directory, pending, expected_identity=identity)
            except ChangeExecutionError as error:
                raise RecoveryError('recovery_completion_marker_conflict', exit_code=6) from error
            if existing != committed.source_bytes:
                raise RecoveryError('recovery_completion_marker_conflict', exit_code=6)
        _image(directory, pending, len(committed.source_bytes), committed.sha256, identity=identity)
        replace(pending, 'journal.json', src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)


def complete_published_transaction(transaction_id, *, held_lock, authority,
                                   expected_journal_sha256, write_new, replace):
    """Finish or verify a complete interrupted transaction without target writes."""
    _transaction(transaction_id)
    if not _hash(expected_journal_sha256):
        raise RecoveryError('expected_recovery_journal_sha256_required', exit_code=2)
    if type(authority) is not RecoveryAuthority:
        raise RecoveryError('recovery_authority_required', exit_code=2)
    if type(held_lock) is not HeldProjectLock:
        raise RecoveryError('native_recovery_lock_required', exit_code=7)
    mutated = False
    try:
        files = held_lock._files
        raw, directory_identity = _read_journal(files, transaction_id)
        journal = _parse(raw, transaction_id, files)
        if journal.sha256 != expected_journal_sha256:
            raise RecoveryError('recovery_journal_changed', exit_code=6)
        if type(journal) is CommittedJournal:
            return _verify_committed_recovery(files, journal, held_lock, authority,
                                               write_new=write_new)
        if type(journal) is not CommittingJournal:
            raise RecoveryError('recovery_full_target_requires_committing', exit_code=6)
        _completion_lock(held_lock, journal)
        active = files.journal_entries()
        if '.specroad/transactions/' + transaction_id not in active:
            raise RecoveryError('recovery_active_set_unproven', exit_code=6)
        target = prove_complete_target(files, journal)
        _authorize_completion(authority, journal)
        _completion_lock(held_lock, journal)
        if files.journal_entries() != active or _read_journal(files, transaction_id) != (raw, directory_identity):
            raise RecoveryError('recovery_journal_changed', exit_code=6)
        if prove_complete_target(files, journal) != target:
            raise RecoveryError('recovery_target_changed', exit_code=6)
        recovered = fully_published(journal)
        transaction, request_receipt, committed = prepare_recovery_receipts(recovered)
        tokens = {}

        def receipt_creation_started():
            nonlocal mutated
            mutated = True

        for record in (transaction, request_receipt):
            if record is None:
                continue
            token, wrote = ensure_recovery_record(files, record, write_new=write_new,
                                                  before_create=receipt_creation_started)
            mutated |= wrote
            tokens[record.path] = (record, token)
        _completion_lock(held_lock, journal)
        if files.journal_entries() != active or _read_journal(files, transaction_id) != (raw, directory_identity):
            raise RecoveryError('recovery_journal_changed', exit_code=6)
        if prove_complete_target(files, journal) != target:
            raise RecoveryError('recovery_target_changed', exit_code=6)
        for record, token in tokens.values():
            recheck_recovery_record(files, record, token)
        mutated = True
        _commit_recovered_journal(files, journal, committed, directory_identity,
                                  write_new=write_new, replace=replace)
        current_raw, current_identity = _read_journal(files, transaction_id)
        if current_identity != directory_identity or current_raw != committed.source_bytes:
            raise RecoveryError('recovery_committed_marker_changed', exit_code=6)
        current = CommittedJournal(current_raw)
        _completion_lock(held_lock, current.predecessor)
        if prove_complete_target(files, current.predecessor) != target:
            raise RecoveryError('recovery_target_changed', exit_code=6)
        for record, token in tokens.values():
            recheck_recovery_record(files, record, token)
        recovery_action(files, current, 'complete', authority=authority, write_new=write_new)
        _completion_lock(held_lock, current)
        if prove_complete_target(files, current.predecessor) != target:
            raise RecoveryError('recovery_target_changed', exit_code=6)
        if _read_journal(files, transaction_id) != (current_raw, current_identity):
            raise RecoveryError('recovery_journal_changed', exit_code=6)
        for record, token in tokens.values():
            recheck_recovery_record(files, record, token)
        return TransactionCompletion._create(current, live=True)
    except RecoveryError as error:
        error.mutation_possible |= mutated
        raise
    except (OSError, SafetyViolation, ModelError, ChangeExecutionError) as error:
        raise RecoveryError(
            getattr(error, 'reason', 'recovery_completion_failed'),
            path=getattr(error, 'path', None),
            exit_code=getattr(error, 'exit_code', 5),
            mutation_possible=mutated,
        ) from error
