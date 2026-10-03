"""Immutable terminal recovery evidence, separate from successful write receipts.

These records establish local byte consistency, not a signature or permission.
Only a caller holding the native lock and proving the live result may create one.
"""
from dataclasses import dataclass
from hashlib import sha256
import os

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from ..security import SafetyViolation
from ..security import paths as guards
from .execution_values import ChangeExecutionError
from ._journal_codec import _text
from ._journal_io import _read
from ._recovery_receipts import ensure_recovery_record, existing_recovery_record, recheck_recovery_record
from ._staging_files import _write_new
from .receipt_values import transaction_receipt_path
from .recovery_values import AUDIT_ROOT, RecoveryError


@dataclass(frozen=True)
class EvidenceRecord:
    path: str
    source_bytes: bytes

    @property
    def sha256(self):
        return sha256(self.source_bytes).hexdigest()

    @property
    def reference(self):
        return {'path': self.path, 'sha256': self.sha256}


def evidence_root(transaction_id):
    return AUDIT_ROOT + '/' + sha256(transaction_id.encode('utf-8')).hexdigest()


def read_evidence(files, path):
    """Read only the selected, descriptor-bound regular record; never scan history."""
    parts = tuple(path.split('/'))
    with files.directory(parts[:-1]) as directory:
        if directory is None:
            return None
        try:
            info = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            return None
        return EvidenceRecord(path, _read(directory, parts[-1],
                              expected_identity=guards._identity(info)))


def sync_evidence(files, record, token):
    """Retry an unconfirmed fsync without replacing any already exact bytes."""
    files.require_held()
    parts = tuple(record.path.split('/'))
    recheck_recovery_record(files, record, token)
    with files.directory(parts[:-1]) as directory:
        if directory is None:
            raise RecoveryError('recovery_receipt_changed', path=record.path, exit_code=6)
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0),
                     dir_fd=directory)
        try:
            if guards._identity(os.fstat(fd)) != token[1]:
                raise RecoveryError('recovery_receipt_changed', path=record.path, exit_code=6)
            os.fsync(fd)
        finally:
            os.close(fd)
    for count in range(len(parts) - 1, -1, -1):
        with files.directory(parts[:count]) as directory:
            if directory is None:
                raise RecoveryError('recovery_receipt_changed', path=record.path, exit_code=6)
            os.fsync(directory)
    recheck_recovery_record(files, record, token)
    return token


def persist_evidence(files, record, *, write_new=_write_new, before_create=None):
    # Refuse a conflicting pre-existing record before entering the write path.
    token = existing_recovery_record(files, record)
    creating = token is None
    mutated = False

    def creation_started():
        nonlocal mutated
        mutated = True
        if before_create is not None:
            before_create()

    try:
        if creating:
            token = ensure_recovery_record(files, record, write_new=write_new,
                                            before_create=creation_started)[0]
        return sync_evidence(files, record, token)
    except (OSError, SafetyViolation, ModelError, ChangeExecutionError) as error:
        raise RecoveryError(getattr(error, 'reason', 'recovery_evidence_write_failed'),
            path=record.path, exit_code=getattr(error, 'exit_code', 5),
            mutation_possible=mutated or getattr(error, 'mutation_possible', False)) from error


def _action_fields(journal, action):
    data = journal.data
    return {'format_version': 'terminal-recovery-audit-v1', 'action': action,
            'outcome': data['state'], 'transaction_id': data['transaction_id'],
            'project_id': data['project_id'], 'request_id': data['request_id'],
            'root_identity': data['root_identity'], 'journal_sha256': journal.sha256,
            'base_model_root_sha256': data['base_model_root_sha256'],
            'target_model_root_sha256': data['target_model_root_sha256'],
            'result_model_root_sha256': data[
                'target_model_root_sha256' if action == 'complete' else 'base_model_root_sha256']}


def recovery_action(files, journal, action, *, authority=None, write_new=_write_new,
                    before_create=None):
    """Verify an existing action or, when authorized, persist its terminal result.

    A repeat caller does not replace the original authority attribution. This
    record attests the completed result; it is not an in-progress write counter.
    """
    fields = _action_fields(journal, action)
    path = evidence_root(journal.data['transaction_id']) + '/' + action + '.json'
    record = read_evidence(files, path)
    if record is not None:
        data = parse_json_object(record.source_bytes)
        if (set(data) != set(fields) | {'authority_id', 'authority_version'}
                or any(data.get(key) != value for key, value in fields.items())
                or not _text(data.get('authority_id')) or not _text(data.get('authority_version'))):
            raise RecoveryError('recovery_action_conflict', path=path, exit_code=6)
        if authority is not None:
            persist_evidence(files, record, write_new=write_new, before_create=before_create)
        return record
    if authority is None:
        raise RecoveryError('recovery_action_missing', path=path, exit_code=6)
    record = EvidenceRecord(path, canonical_json_bytes({**fields,
        'authority_id': authority.authority_id, 'authority_version': authority.version}))
    persist_evidence(files, record, write_new=write_new, before_create=before_create)
    return record


def rollback_receipt(journal, action_record, *, action='rollback'):
    """A rolled-back/discarded result never impersonates a committed request."""
    return EvidenceRecord(transaction_receipt_path(journal.data['transaction_id']),
        canonical_json_bytes({'format_version': 'recovery-transaction-receipt-v1',
            'outcome': 'rolled_back', 'action': action, 'journal': journal.data,
            'journal_sha256': journal.sha256, 'recovery_audit': action_record.reference,
            'result_model_root_sha256': journal.data['base_model_root_sha256']}))


def rollback_evidence(files, journal, *, authority=None):
    previous = read_evidence(files, evidence_root(journal.data['transaction_id']) + '/rollback.json')
    action = recovery_action(files, journal, 'rollback', authority=authority)
    receipt = rollback_receipt(journal, action)
    if authority is None:
        if existing_recovery_record(files, receipt) is None:
            raise RecoveryError('recovery_receipt_missing', path=receipt.path, exit_code=6)
    else:
        try:
            persist_evidence(files, receipt)
        except RecoveryError as error:
            error.mutation_possible |= previous is None
            raise
    return action, receipt
