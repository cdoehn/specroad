"""Explicit transaction-bound ownership transfer while holding the native mutex.

This is recovery access, never permission to bypass a journal or start another
operation. The ordinary lock-recover API retains its unconditional journal veto.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import os
from uuid import uuid4

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..storage.json_syntax import parse_json_object
from .authoring import normalize_authoring_actor
from .locking import HeldProjectLock, _bound, _request
from .lock_values import LOCK_VERSION, LockRecord, ProjectLockError, text
from .recovery_values import RecoveryAuthority, RecoveryError, DiscardedJournal
from .receipt_values import transaction_receipt_path
from ._journal_codec import _hash, _transaction, journal_path
from ._lock_files import LockFiles, identity
from ._lock_process import LinuxOwnerProbe
from ._lock_owner_policy import _recovery_permitted
from ._recovery_inputs import _parse
from ._recovery_evidence import (EvidenceRecord, evidence_root, read_evidence,
                                 persist_evidence, rollback_receipt)
from ._recovery_receipts import existing_recovery_record, recheck_recovery_record
from ._staging_files import _image


def _selected_journal(files, transaction_id, project_id):
    record = read_evidence(files, journal_path(transaction_id))
    if record is None:
        # Terminal cleanup may already have moved the active journal. Select
        # only this transaction's canonical evidence, never scan audit history.
        from .recovery_cleanup import _terminal, _marker_path
        try:
            journal = _terminal(files, transaction_id)
            record = read_evidence(files, _marker_path(transaction_id, journal))
        except RecoveryError as error:
            if error.reason != 'recovery_terminal_proof_missing':
                raise
            record = read_evidence(files, transaction_receipt_path(transaction_id))
            if record is None:
                raise error
            value = parse_json_object(record.source_bytes)
            if value.get('format_version') != 'recovery-transaction-receipt-v1' or value.get('action') != 'discard':
                raise error
            journal = DiscardedJournal(canonical_json_bytes(value.get('journal')))
            intent = read_evidence(files, journal.data['discard']['audit_path'] + '/intent.json')
            if intent is None or rollback_receipt(journal, intent, action='discard').source_bytes != record.source_bytes:
                raise RecoveryError('recovery_receipt_conflict', exit_code=6)
        journal = _parse(journal.source_bytes, transaction_id, files, project_id)
    else:
        journal = _parse(record.source_bytes, transaction_id, files, project_id)
    return journal, record, existing_recovery_record(files, record)


def _takeover(files, transaction_id, *, project_id, request_id, command,
              expected_lock_sha256, expected_journal_sha256, authority, actor,
              reason, accept_remote_risk, probe):
    old, old_inode = files.read_record()
    if old is None:
        raise RecoveryError('lock_record_missing', exit_code=6)
    _bound(old, files, project_id)
    if old.sha256 != expected_lock_sha256:
        raise RecoveryError('lock_owner_changed', exit_code=6)
    value = old.data
    if (value['kind'] not in ('writer', 'recovery') or value['transaction_id'] != transaction_id
            or value['request_id'] != request_id):
        raise RecoveryError('recovery_lock_binding_mismatch', exit_code=6)
    journal, selected_record, selected_token = _selected_journal(files, transaction_id, project_id)
    if journal.sha256 != expected_journal_sha256 or journal.data['request_id'] != request_id:
        raise RecoveryError('recovery_journal_binding_mismatch', exit_code=6)
    active = files.journal_entries()
    state = _recovery_permitted(old, probe, accept_remote_risk)
    request = {'action': 'takeover', 'command': command, 'project_id': project_id,
        'transaction_id': transaction_id, 'request_id': request_id, 'actor': actor.as_fields(),
        'reason': reason, 'force': True, 'accept_remote_risk': accept_remote_risk,
        'lock_sha256': old.sha256, 'journal_sha256': journal.sha256,
        'observed_owner_state': state}
    raw = canonical_json_bytes(request)
    try:
        allowed = authority.check(request)
    except Exception as error:
        raise RecoveryError('recovery_authority_failed', exit_code=7) from error
    if type(allowed) is not bool or not allowed or canonical_json_bytes(request) != raw:
        raise RecoveryError('recovery_not_authorized', exit_code=7)

    def unchanged():
        files.require_held()
        current, inode = files.read_record()
        if current is None or current.source_bytes != old.source_bytes or inode != old_inode:
            raise RecoveryError('lock_owner_changed', exit_code=6)
        _bound(current, files, project_id)
        if _recovery_permitted(current, probe, accept_remote_risk) != state:
            raise RecoveryError('recovery_owner_observation_changed', exit_code=6)
        if files.journal_entries() != active:
            raise RecoveryError('recovery_active_set_changed', exit_code=6)
        now, record, token = _selected_journal(files, transaction_id, project_id)
        if now.source_bytes != journal.source_bytes or record != selected_record or token != selected_token:
            raise RecoveryError('recovery_journal_changed', exit_code=6)

    unchanged()
    next_record = LockRecord(canonical_json_bytes({'format_version': LOCK_VERSION,
        'kind': 'recovery', 'lock_id': str(uuid4()), 'project_id': project_id,
        'root_identity': identity(os.fstat(files.root_fd)), **LinuxOwnerProbe().current().as_dict(),
        'created_at': datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z'),
        'command': command, 'request_id': request_id, 'transaction_id': transaction_id}))
    audit_path = evidence_root(transaction_id) + '/takeover-' + next_record.data['lock_id']
    journal_copy = EvidenceRecord(audit_path + '/journal.before.json', journal.source_bytes)
    intent = EvidenceRecord(audit_path + '/intent.json', canonical_json_bytes({
        'format_version': 'transaction-lock-takeover-v1', 'phase': 'intent', **request,
        'old_record': old.data, 'new_record': next_record.data,
        'new_record_sha256': next_record.sha256, 'journal_copy': journal_copy.reference,
        'authority_id': authority.authority_id, 'authority_version': authority.version}))
    staged_owner = EvidenceRecord(audit_path + '/owner.pending.json', next_record.source_bytes)
    attempted = False
    try:
        attempted = True
        journal_token = persist_evidence(files, journal_copy)
        intent_token = persist_evidence(files, intent)
        owner_token = persist_evidence(files, staged_owner)
        unchanged()
        recheck_recovery_record(files, intent, intent_token)
        recheck_recovery_record(files, journal_copy, journal_token)
        with files.directory(tuple(audit_path.split('/'))) as staged:
            with files.directory(('.specroad', 'locks')) as locks:
                if staged is None or locks is None:
                    raise RecoveryError('recovery_takeover_directory_changed', exit_code=6)
                _image(staged, 'owner.pending.json', len(next_record.source_bytes),
                       next_record.sha256, identity=owner_token[1])
                unchanged()
                # No unlink/create gap or partial new owner at the live path.
                os.replace('owner.pending.json', 'project.json', src_dir_fd=staged, dst_dir_fd=locks)
                os.fsync(locks)
                os.fsync(staged)
        current, inode = files.read_record()
        if current is None or current.source_bytes != next_record.source_bytes or inode != owner_token[1]:
            raise RecoveryError('lock_owner_changed', exit_code=6)
        held = HeldProjectLock(files, current, inode)
        held.check()
        if files.journal_entries() != active:
            raise RecoveryError('recovery_active_set_changed', exit_code=6)
        now, record, token = _selected_journal(files, transaction_id, project_id)
        if now.source_bytes != journal.source_bytes or record != selected_record or token != selected_token:
            raise RecoveryError('recovery_journal_changed', exit_code=6)
        completed = EvidenceRecord(audit_path + '/completed.json', canonical_json_bytes({
            'format_version': 'transaction-lock-takeover-v1', 'phase': 'completed',
            'action': 'takeover', 'transaction_id': transaction_id,
            'intent': intent.reference, 'new_record_sha256': current.sha256,
            'journal_sha256': journal.sha256, 'normative_writes': 0}))
        persist_evidence(files, completed)
        recheck_recovery_record(files, intent, intent_token)
        recheck_recovery_record(files, journal_copy, journal_token)
        held.check()
        now, record, token = _selected_journal(files, transaction_id, project_id)
        if (files.journal_entries() != active or now.source_bytes != journal.source_bytes
                or record != selected_record or token != selected_token):
            raise RecoveryError('recovery_journal_changed', exit_code=6)
        return held
    except (OSError, SafetyViolation, ModelError) as error:
        if isinstance(error, RecoveryError):
            error.mutation_possible |= attempted
            raise
        raise RecoveryError(getattr(error, 'reason', 'recovery_takeover_failed'),
            exit_code=getattr(error, 'exit_code', 5), mutation_possible=attempted) from error


@contextmanager
def transaction_recovery_lock(root, transaction_id, *, project_id, request_id,
        expected_lock_sha256, expected_journal_sha256, authority, actor, reason,
        force=False, accept_remote_risk=False, command='recover run', owner_probe=None):
    """Explicitly transfer a stopped owner's bound transaction to recovery.

    The host authenticates and authorizes the caller. Foreign/unverifiable/PID-
    reused owners retain the existing explicit risk-consent gate; a live owner
    or occupied native mutex is never overridden. No journal is removed here.
    """
    _transaction(transaction_id)
    _request('recovery', command, project_id, request_id, transaction_id)
    text(reason)
    actor = normalize_authoring_actor(actor)
    if (command not in ('recover run', 'recover discard') or type(force) is not bool or not force
            or type(accept_remote_risk) is not bool):
        raise RecoveryError('explicit_transaction_recovery_required', exit_code=2)
    if not _hash(expected_lock_sha256) or not _hash(expected_journal_sha256):
        raise RecoveryError('expected_recovery_bindings_required', exit_code=2)
    if type(authority) is not RecoveryAuthority:
        raise RecoveryError('recovery_authority_required', exit_code=2)
    probe = LinuxOwnerProbe() if owner_probe is None else owner_probe
    with LockFiles(root) as files:
        files.acquire()
        try:
            held = _takeover(files, transaction_id, project_id=project_id, request_id=request_id,
                command=command, expected_lock_sha256=expected_lock_sha256,
                expected_journal_sha256=expected_journal_sha256, authority=authority,
                actor=actor, reason=reason, accept_remote_risk=accept_remote_risk, probe=probe)
        except (ProjectLockError, RecoveryError):
            raise
        except (OSError, SafetyViolation, ModelError) as error:
            raise RecoveryError(getattr(error, 'reason', 'recovery_takeover_failed'),
                                exit_code=getattr(error, 'exit_code', 5)) from error
        try:
            yield held
        finally:
            if os.getpid() == held._pid:
                try:
                    held.check()
                    files.remove_record(held.record, held._inode)
                finally:
                    held._active = False
