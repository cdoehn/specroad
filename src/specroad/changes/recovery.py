"""Explicit audited discard under an already-held native recovery lock.

No ordinary model load, new plan or target write occurs. Original journals,
images and receipts are retained. Diagnosis has a separate read-only entrypoint.
"""
from datetime import datetime, timezone
from hashlib import sha256
import os
from uuid import uuid4
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..security import paths as guards
from ..storage.json_syntax import parse_json_object
from .authoring import normalize_authoring_actor
from .execution_values import ChangeExecutionError
from .locking import HeldProjectLock
from ._recovery_binding import check_discard_lock as _held
from ._journal_codec import _hash, _text, _transaction
from ._staging_files import _write_new, _image
from .recovery_values import (AUDIT_ROOT, RecoveryAuthority, RecoveryError,
                              RecoveryObservation, DiscardedJournal)
from ._recovery_inputs import _read_journal, _parse, _unchanged_base, _work
from ._discard_completion import archived_discard, finish_discard
from ._recovery_work import work_file_inventory
# Preserve the initial module import surface; the implementation is read-only.
from .recovery_read import inspect_recovery


def discard_unpublished_transaction(preflight, transaction_id, *, held_lock,
                                   authority, actor, reason, expected_journal_sha256):
    """Discard ONLY proven unpublished preparations; retain all work in an audit.

    The original journal and an immutable intent are durable before the terminal
    marker. An atomic directory rename moves *all* known work to the audit. No
    normative target, request receipt, before image or prior audit is removed.
    Late failure keeps partial audit/terminal state for explicit diagnosis.
    """
    _transaction(transaction_id)
    if not _hash(expected_journal_sha256) or not _text(reason):
        raise RecoveryError('explicit_recovery_identity_and_reason_required', exit_code=2)
    actor = normalize_authoring_actor(actor)
    if type(authority) is not RecoveryAuthority:
        raise RecoveryError('recovery_authority_required', exit_code=2)
    if type(held_lock) is not HeldProjectLock:
        raise RecoveryError('native_recovery_lock_required', exit_code=7)
    attempted = False
    try:
        files = held_lock._files
        try:
            raw, ident = _read_journal(files, transaction_id)
        except RecoveryError as error:
            if error.reason != 'recovery_journal_missing':
                raise
            journal = archived_discard(files, transaction_id)
        else:
            journal = _parse(raw, transaction_id, files)
        if type(journal) is DiscardedJournal:
            return finish_discard(preflight, journal, held_lock=held_lock,
                authority=authority, actor=actor, reason=reason,
                expected_journal_sha256=expected_journal_sha256)
        _held(held_lock, journal)
        if journal.sha256 != expected_journal_sha256:
            raise RecoveryError('recovery_journal_changed', exit_code=6)
        base = _unchanged_base(preflight, journal, files)
        active = files.journal_entries()
        selected_path = '.specroad/transactions/' + transaction_id
        if selected_path not in active:
            raise RecoveryError('recovery_active_set_unproven', exit_code=6)
        work = _work(files, journal, preflight=preflight)

        def guard(*, terminal_raw=None, expected_work=work):
            _held(held_lock, journal)
            if files.journal_entries() != active:
                raise RecoveryError('recovery_active_set_changed', exit_code=6)
            if _work(files, journal, raw=terminal_raw, preflight=preflight) != expected_work:
                raise RecoveryError('recovery_work_changed', exit_code=6)
            if _unchanged_base(preflight, journal, files) != base:
                raise RecoveryError('recovery_base_changed', exit_code=6)

        request = {'action': 'discard', 'transaction_id': transaction_id,
                   'project_id': journal.data['project_id'], 'actor': actor.as_fields(),
                   'reason': reason, 'journal_sha256': journal.sha256,
                   'base_model_root_sha256': journal.data['base_model_root_sha256'],
                   'target_model_root_sha256': journal.data['target_model_root_sha256']}
        request_raw = canonical_json_bytes(request)
        try:
            allowed = authority.check(request)
        except Exception as error:
            raise RecoveryError('recovery_authority_failed', exit_code=7) from error
        if canonical_json_bytes(request) != request_raw or type(allowed) is not bool or not allowed:
            raise RecoveryError('recovery_not_authorized', exit_code=7)
        guard()
        event = str(uuid4()); audit_path = AUDIT_ROOT + '/' + event
        work_files = [{'path': 'journal.json', 'size': len(raw), 'sha256': journal.sha256}]
        work_files.extend(work_file_inventory(work))
        intent = canonical_json_bytes({'format_version': 'recovery-audit-v1',
            'event_id': event, 'phase': 'intent', **parse_json_object(request_raw),
            'previous_state': journal.data['state'], 'normative_writes': 0,
            'work_files': sorted(work_files, key=lambda item: item['path']),
            'authority_id': authority.authority_id, 'authority_version': authority.version,
            'created_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')})
        value = journal.data
        value.update(state='rolled_back', discard={'event_id': event,
            'previous_state': journal.data['state'], 'journal_before_sha256': journal.sha256,
            'intent_sha256': sha256(intent).hexdigest(), 'audit_path': audit_path})
        terminal = DiscardedJournal(canonical_json_bytes(value))
        attempted = True
        with files.directory(tuple(AUDIT_ROOT.split('/')), create=True) as audit_root:
            os.mkdir(event, mode=0o700, dir_fd=audit_root)
            os.fsync(audit_root)
        with files.directory(tuple(audit_path.split('/'))) as audit:
            if os.listdir(audit): raise RecoveryError('recovery_audit_collision', exit_code=6)
            _write_new(audit, 'journal.before.json', raw)
            _write_new(audit, 'intent.json', intent)
            guard()
            prefix = tuple(journal.path.split('/')[:-1])
            with files.directory(prefix) as directory:
                if guards._identity(os.fstat(directory)) != ident:
                    raise RecoveryError('recovery_work_changed', exit_code=6)
                _write_new(directory, 'journal.discard', terminal.source_bytes)
                # Recheck all original bytes without trusting the temporary marker.
                _image(directory, 'journal.json', len(raw), journal.sha256)
                _held(held_lock, journal)
                if _unchanged_base(preflight, journal, files) != base:
                    raise RecoveryError('recovery_base_changed', exit_code=6)
                os.replace('journal.discard', 'journal.json', src_dir_fd=directory, dst_dir_fd=directory)
                os.fsync(directory)
        return finish_discard(preflight, terminal, held_lock=held_lock,
            authority=authority, actor=actor, reason=reason,
            expected_journal_sha256=terminal.sha256, authorized=True)
    except (ChangeExecutionError, SafetyViolation, ModelError, OSError, ValueError) as error:
        raise RecoveryError(getattr(error, 'reason', 'recovery_discard_failed'),
            exit_code=getattr(error, 'exit_code', 5),
            mutation_possible=attempted or getattr(error, 'mutation_possible', False)) from error


def complete_published_transaction(transaction_id, *, held_lock, authority,
                                   expected_journal_sha256):
    """Finish or verify a complete interrupted transaction without target writes."""
    from ._recovery_completion import complete_published_transaction as complete
    from ._recovery_initial import write_recovery_file
    return complete(
        transaction_id,
        held_lock=held_lock,
        authority=authority,
        expected_journal_sha256=expected_journal_sha256,
        write_new=write_recovery_file,
        replace=os.replace,
    )


def rollback_interrupted_transaction(transaction_id, *, held_lock, authority,
                                     expected_journal_sha256):
    """Restore an interrupted commit to its complete journal-bound basis."""
    from ._recovery_rollback import rollback_interrupted_transaction as rollback
    return rollback(transaction_id, held_lock=held_lock, authority=authority,
                    expected_journal_sha256=expected_journal_sha256)
