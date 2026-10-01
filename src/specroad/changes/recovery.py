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
from ._journal_codec import _hash, _text, _transaction
from ._staging_files import _write_new, _image
from .recovery_values import (AUDIT_ROOT, RecoveryAuthority, RecoveryError,
                              RecoveryObservation, DiscardedJournal)
from ._recovery_inputs import _read_journal, _parse, _unchanged_base, _work
# Preserve the initial module import surface; the implementation is read-only.
from .recovery_read import inspect_recovery


def _held(held, journal):
    if type(held) is not HeldProjectLock:
        raise RecoveryError('native_recovery_lock_required', exit_code=7)
    held.check()
    lock, data = held.record.data, journal.data
    if (lock['kind'] != 'recovery' or lock['command'] != 'recover discard'
            or lock['transaction_id'] != data['transaction_id']
            or lock['project_id'] != data['project_id']
            or lock['request_id'] != data['request_id']):
        raise RecoveryError('recovery_lock_binding_mismatch', exit_code=6)


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
        raw, ident = _read_journal(files, transaction_id)
        journal = _parse(raw, transaction_id, files)
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
        work_files.extend({'path': path, 'size': token['size'], 'sha256': token['sha256']}
                          for path, token in sorted(work.items()) if type(token) is dict)
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
            terminal_work = {**work, 'journal.json': terminal.sha256}
            guard(terminal_raw=terminal.source_bytes, expected_work=terminal_work)
            _image(audit, 'journal.before.json', len(raw), journal.sha256)
            _image(audit, 'intent.json', len(intent), sha256(intent).hexdigest())
            with files.directory(('.specroad', 'transactions')) as parent:
                if guards._identity(os.stat(transaction_id, dir_fd=parent, follow_symlinks=False)) != ident:
                    raise RecoveryError('recovery_work_changed', exit_code=6)
                if 'work' in os.listdir(audit): raise RecoveryError('recovery_audit_collision', exit_code=6)
                os.rename(transaction_id, 'work', src_dir_fd=parent, dst_dir_fd=audit)
                os.fsync(parent); os.fsync(audit)
            if _work(files, journal, raw=terminal.source_bytes,
                     prefix=(*tuple(audit_path.split('/')), 'work'), preflight=preflight) != terminal_work:
                raise RecoveryError('recovery_archive_changed', exit_code=6)
            if _unchanged_base(preflight, journal, files) != base:
                raise RecoveryError('recovery_base_changed', exit_code=6)
            completed = {'format_version': 'recovery-audit-v1', 'event_id': event,
                'phase': 'completed', 'action': 'discard', 'state': 'rolled_back',
                'transaction_id': transaction_id, 'journal_before_sha256': journal.sha256,
                'journal_sha256': terminal.sha256, 'intent_sha256': sha256(intent).hexdigest(),
                'base_model_root_sha256': journal.data['base_model_root_sha256'],
                'archive_path': audit_path + '/work', 'normative_writes': 0}
            _write_new(audit, 'completed.json', canonical_json_bytes(completed))
            _image(audit, 'journal.before.json', len(raw), journal.sha256)
            _image(audit, 'intent.json', len(intent), sha256(intent).hexdigest())
            if _work(files, journal, raw=terminal.source_bytes,
                     prefix=(*tuple(audit_path.split('/')), 'work'), preflight=preflight) != terminal_work:
                raise RecoveryError('recovery_archive_changed', exit_code=6)
        _held(held_lock, journal)
        remaining = tuple(path for path in active if path != selected_path)
        if files.journal_entries() != remaining or _unchanged_base(preflight, journal, files) != base:
            raise RecoveryError('recovery_final_observation_changed', exit_code=6)
        return RecoveryObservation._create({**completed, 'discard_completed': True,
            'evidence_preserved': True, 'audit_path': audit_path, 'model_loaded': False,
            'remaining_active_paths': list(remaining),
            'write_authorized': False, 'atomic_snapshot': False})
    except (ChangeExecutionError, SafetyViolation, ModelError, OSError, ValueError) as error:
        raise RecoveryError(getattr(error, 'reason', 'recovery_discard_failed'),
            exit_code=getattr(error, 'exit_code', 5), mutation_possible=attempted) from error


def complete_published_transaction(transaction_id, *, held_lock, authority,
                                   expected_journal_sha256):
    """Finish or verify a complete interrupted transaction without target writes."""
    from ._recovery_completion import complete_published_transaction as complete
    return complete(
        transaction_id,
        held_lock=held_lock,
        authority=authority,
        expected_journal_sha256=expected_journal_sha256,
        write_new=_write_new,
        replace=os.replace,
    )
