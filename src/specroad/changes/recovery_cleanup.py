"""Explicit terminal cleanup after the original writer has released its lock.

The recovery lock authorizes no new model write. Full live basis/target proof and
immutable receipts precede an atomic move of the closed work inventory into its
bound audit archive. No recovery bytes or unrelated blockers are deleted.
"""
import os

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..security import paths as guards
from ..storage.json_syntax import parse_json_object
from .execution_values import ChangeExecutionError
from .locking import HeldProjectLock
from .recovery_values import RecoveryAuthority, RecoveryError, RecoveryObservation
from ._journal_codec import _hash, _transaction, _text
from ._recovery_binding import check_run_lock as _completion_lock
from ._recovery_evidence import (EvidenceRecord, evidence_root, persist_evidence,
                                 read_evidence)
from ._recovery_receipts import existing_recovery_record, recheck_recovery_record
from ._recovery_barrier import barrier_path, barrier_record, persist_barrier, remove_barrier
from ._recovery_terminal import (terminal_marker_path as _marker_path,
    read_terminal_journal as _terminal, prove_terminal_result as _proof)
from ._recovery_work import read_terminal_work as _work, work_file_inventory


def _authorize(authority, journal):
    data = journal.data
    request = {'action': 'cleanup', 'transaction_id': data['transaction_id'],
        'project_id': data['project_id'], 'request_id': data['request_id'],
        'state': data['state'], 'journal_sha256': journal.sha256,
        'base_model_root_sha256': data['base_model_root_sha256'],
        'target_model_root_sha256': data['target_model_root_sha256']}
    raw = canonical_json_bytes(request)
    try:
        allowed = authority.check(request)
    except Exception as error:
        raise RecoveryError('recovery_authority_failed', exit_code=7) from error
    if canonical_json_bytes(request) != raw or type(allowed) is not bool or not allowed:
        raise RecoveryError('recovery_not_authorized', exit_code=7)


def cleanup_recovered_transaction(transaction_id, *, held_lock, authority, expected_journal_sha256):
    """Archive selected committed/rolled-back work under a bound recover-run lock.

    No original in-memory preflight is required. A repeated call checks the
    durable proof and archive; it never repeats a normative publication/rollback.
    Other active transactions remain blocking and are reported separately.
    """
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
        journal = _terminal(files, transaction_id)
        if journal.sha256 != expected_journal_sha256:
            raise RecoveryError('recovery_journal_changed', exit_code=6)
        _completion_lock(held_lock, journal)
        live, proof = _proof(files, journal)
        active = files.journal_entries()
        selected = journal.path.rsplit('/', 1)[0]
        prefix = tuple(selected.split('/'))
        audit_path = evidence_root(transaction_id) + '/cleanup-' + journal.sha256
        archive = tuple((audit_path + '/work').split('/'))
        work = _work(files, journal, prefix)
        archived = _work(files, journal, archive)
        if work is not None and archived is not None:
            raise RecoveryError('recovery_archive_collision', exit_code=6)
        expected_work = work if work is not None else archived
        if expected_work is None and barrier_path(transaction_id, 'cleanup') in active:
            raise RecoveryError('recovery_cleanup_work_missing', exit_code=6)
        _authorize(authority, journal)

        def guard(expected_active, work_prefix, inventory):
            _completion_lock(held_lock, journal)
            if files.journal_entries() != expected_active:
                raise RecoveryError('recovery_active_set_changed', exit_code=6)
            if _terminal(files, transaction_id).source_bytes != journal.source_bytes:
                raise RecoveryError('recovery_journal_changed', exit_code=6)
            if _work(files, journal, work_prefix) != inventory or _proof(files, journal)[0] != live:
                raise RecoveryError('recovery_work_or_result_changed', exit_code=6)
            for record, token in proof:
                recheck_recovery_record(files, record, token)

        guard(active, prefix if work is not None else archive, expected_work)
        marker = EvidenceRecord(_marker_path(transaction_id, journal), journal.source_bytes)
        # An already fully cleaned normal completion needs no new recovery write.
        if expected_work is not None:
            entries = work_file_inventory(expected_work)
            fields = {'format_version': 'terminal-cleanup-v1', 'action': 'cleanup',
                'transaction_id': transaction_id, 'journal_sha256': journal.sha256,
                'outcome': journal.data['state'], 'archive_path': audit_path + '/work',
                'work_files': entries, 'normative_writes': 0}
            record = read_evidence(files, audit_path + '/intent.json')
            if record is not None:
                data = parse_json_object(record.source_bytes)
                if (set(data) != set(fields) | {'authority_id', 'authority_version'}
                        or any(data.get(key) != value for key, value in fields.items())
                        or not _text(data.get('authority_id')) or not _text(data.get('authority_version'))):
                    raise RecoveryError('recovery_cleanup_audit_conflict', exit_code=6)
            elif work is None:
                raise RecoveryError('recovery_cleanup_audit_missing', exit_code=6)
            else:
                record = EvidenceRecord(audit_path + '/intent.json', canonical_json_bytes({**fields,
                    'authority_id': authority.authority_id, 'authority_version': authority.version}))
            completed = EvidenceRecord(audit_path + '/completed.json', canonical_json_bytes({
                **fields, 'phase': 'completed', 'intent_sha256': record.sha256}))
            barrier = barrier_record(journal, record, 'cleanup')
            done_token = existing_recovery_record(files, completed)
            pending_token = existing_recovery_record(files, barrier)
            if _work(files, journal, archive) != archived:
                raise RecoveryError('recovery_archive_changed', exit_code=6)
            mutated = True
            marker_token = persist_evidence(files, marker)
            audit_token = persist_evidence(files, record)
            guard(active, prefix if work is not None else archive, expected_work)
            recheck_recovery_record(files, marker, marker_token)
            recheck_recovery_record(files, record, audit_token)
            # A completed retry needs no new pending event. All other paths
            # stay visible to ordinary readers/writers until final proof.
            pending = work is not None or done_token is None or pending_token is not None
            if pending:
                pending_token, active = persist_barrier(files, barrier, active)
                guard(active, prefix if work is not None else archive, expected_work)
            if work is not None:
                with files.directory(tuple(audit_path.split('/'))) as audit:
                    with files.directory(('.specroad', 'transactions')) as parent:
                        if audit is None or parent is None:
                            raise RecoveryError('recovery_work_changed', exit_code=6)
                        if (guards._identity(os.stat(transaction_id, dir_fd=parent,
                                                    follow_symlinks=False)) != work['']
                                or 'work' in os.listdir(audit)):
                            raise RecoveryError('recovery_work_changed', exit_code=6)
                        os.rename(transaction_id, 'work', src_dir_fd=parent, dst_dir_fd=audit)
                        os.fsync(parent)
                        os.fsync(audit)
            else:
                # A rename may have completed before an unconfirmed fsync.
                for parts in (('.specroad', 'transactions'), tuple(audit_path.split('/'))):
                    with files.directory(parts) as directory:
                        if directory is None:
                            raise RecoveryError('recovery_work_changed', exit_code=6)
                        os.fsync(directory)
            remaining = tuple(path for path in active if path != selected)
            guard(remaining, archive, expected_work)
            completed_token = persist_evidence(files, completed)
            guard(remaining, archive, expected_work)
            for item, token in ((marker, marker_token), (record, audit_token), (completed, completed_token)):
                recheck_recovery_record(files, item, token)
            if pending:
                remove_barrier(files, barrier, pending_token)
                remaining = tuple(path for path in remaining if path != barrier.path)
                guard(remaining, archive, expected_work)
        else:
            if existing_recovery_record(files, marker) is None:
                raise RecoveryError('recovery_terminal_proof_missing', exit_code=6)
            remaining = active
        return RecoveryObservation._create({'format_version': 'terminal-cleanup-result-v1',
            'transaction_id': transaction_id, 'state': journal.data['state'],
            'journal_sha256': journal.sha256, 'cleanup_completed': True, 'cleanup_required': False,
            'completion_verified': True, 'current_result_verified': True, 'normative_writes': 0,
            'archive_path': None if expected_work is None else audit_path + '/work',
            'evidence_preserved': True, 'remaining_active_paths': list(remaining),
            'recovery_required': bool(remaining), 'model_loaded': False, 'normal_operation_started': False})
    except RecoveryError as error:
        error.mutation_possible |= mutated
        raise
    except (OSError, SafetyViolation, ModelError, ChangeExecutionError) as error:
        raise RecoveryError(getattr(error, 'reason', 'recovery_cleanup_failed'),
            path=getattr(error, 'path', None), exit_code=getattr(error, 'exit_code', 5),
            mutation_possible=mutated) from error
