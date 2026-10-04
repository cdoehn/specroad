"""Explicit restart preparation from persisted inputs; never a write authority."""
from dataclasses import dataclass

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..storage.json_syntax import parse_json_object
from ._journal_codec import _hash, _text, _transaction
from ._lock_files import LockFiles
from ._discard_basis import observe_discard_basis
from .recovery_values import RecoveryError


@dataclass(frozen=True, init=False)
class DiscardPreflight:
    """Ephemeral read observation, freshly checked again by the mutating API."""
    _journal_bytes: bytes
    _root: str
    _root_identity: tuple
    _observation: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use prepare_discard_recovery with persistent project inputs')

    @classmethod
    def _create(cls, files, journal, basis, *, current=None):
        obj = object.__new__(cls)
        object.__setattr__(obj, '_journal_bytes', journal.source_bytes)
        object.__setattr__(obj, '_root', str(files.boundary.root))
        object.__setattr__(obj, '_root_identity', files.boundary._root_identity)
        object.__setattr__(obj, '_observation', canonical_json_bytes({
            'format_version': 'discard-preflight-v1', 'transaction_id': journal.data['transaction_id'],
            'project_id': journal.data['project_id'],
            'journal_sha256': journal.sha256 if current is None else current.sha256,
            'original_journal_sha256': journal.sha256,
            'base_model_root_sha256': basis['base_model_root_sha256'],
            'observed_paths': sorted(basis['files']), 'base_verified': True,
            'final_check_required': True, 'project_lock_acquired': False,
            'model_loaded': False, 'write_authorized': False, 'atomic_snapshot': False}))
        return obj

    @property
    def data(self):
        return parse_json_object(self._observation)

    def __bool__(self):
        raise TypeError('A discard observation is not write authorization')

    def _check(self, files, journal, *, include_images=False):
        if (journal.source_bytes != self._journal_bytes
                or str(files.boundary.root) != self._root
                or files.boundary._root_identity != self._root_identity):
            raise RecoveryError('discard_preflight_binding_mismatch', exit_code=6)
        return observe_discard_basis(files, journal, include_images=include_images)


def prepare_discard_recovery(root, transaction_id, *, expected_project_id, expected_journal_sha256):
    """Prove an unpublished basis or resume its proved discard from current files.

    The caller still needs a new native recovery lock and fresh host authority.
    Incomplete/foreign evidence remains protected. No implicit profile choice,
    original plan or permission is invented, including after a lost completion.
    """
    _transaction(transaction_id)
    if not _text(expected_project_id) or not _hash(expected_journal_sha256):
        raise RecoveryError('explicit_discard_binding_required', exit_code=2)
    try:
        with LockFiles(root) as files:
            proof, before = _observe_restart(files, transaction_id, expected_project_id, expected_journal_sha256)
            _, after = _observe_restart(files, transaction_id, expected_project_id, expected_journal_sha256)
            if after != before:
                raise RecoveryError('discard_preflight_inputs_changed', exit_code=6)
            return proof
    except RecoveryError:
        raise
    except (OSError, SafetyViolation, ModelError) as error:
        raise RecoveryError(getattr(error, 'reason', 'discard_preflight_unavailable'),
                            exit_code=getattr(error, 'exit_code', 5)) from error


def _observe_restart(files, transaction_id, project_id, expected_hash):
    from ._recovery_inputs import _parse, _work
    from ._journal_codec import journal_path
    from ._discard_completion import (archived_discard, original_discard,
        pending_discard, discard_completion_record)
    from ._recovery_evidence import EvidenceRecord, read_evidence, rollback_receipt
    from ._recovery_receipts import existing_recovery_record
    from ._recovery_barrier import barrier_record
    from ._recovery_work import work_file_inventory
    from .recovery_values import DiscardedJournal
    from .receipt_values import transaction_receipt_path

    record = read_evidence(files, journal_path(transaction_id))
    if record is None:
        current = archived_discard(files, transaction_id)
        record = read_evidence(files, transaction_receipt_path(transaction_id))
    else:
        current = _parse(record.source_bytes, transaction_id, files, project_id)
    if current.data['project_id'] != project_id:
        raise RecoveryError('recovery_journal_binding_mismatch', exit_code=6)
    if current.sha256 != expected_hash:
        raise RecoveryError('recovery_journal_changed', exit_code=6)
    tokens = [(record, existing_recovery_record(files, record))]
    terminal = current if type(current) is DiscardedJournal else pending_discard(files, current)
    pending = terminal is not None and type(current) is not DiscardedJournal
    journal, intent = (current, None) if terminal is None else original_discard(files, terminal)
    basis = observe_discard_basis(files, journal)
    proof = DiscardPreflight._create(files, journal, basis, current=current)
    if terminal is None:
        work = _work(files, journal, preflight=proof)
    else:
        prefix = tuple(journal.path.split('/')[:-1])
        audit_path = terminal.data['discard']['audit_path']
        archive = tuple((audit_path + '/work').split('/'))
        with files.directory(prefix) as directory:
            active_work = directory is not None
        with files.directory(archive) as directory:
            archived_work = directory is not None
        if active_work == archived_work or (pending and not active_work):
            raise RecoveryError('recovery_discard_work_unproven', exit_code=6)
        work = _work(files, journal, raw=journal.source_bytes if pending else terminal.source_bytes,
            prefix=prefix if active_work else archive, preflight=proof,
            pending=terminal.source_bytes if pending else None)
        inventory = [{'path': 'journal.json', 'size': len(journal.source_bytes), 'sha256': journal.sha256}]
        inventory.extend(work_file_inventory(work))
        if parse_json_object(intent.source_bytes).get('work_files') != sorted(inventory, key=lambda i: i['path']):
            raise RecoveryError('recovery_discard_inventory_mismatch', exit_code=6)
        records = [intent, EvidenceRecord(audit_path + '/journal.before.json', journal.source_bytes),
            rollback_receipt(terminal, intent, action='discard'), barrier_record(terminal, intent, 'discard'),
            discard_completion_record(terminal, journal, intent)]
        if pending:
            records.append(EvidenceRecord(journal.path.rsplit('/', 1)[0] + '/journal.discard', terminal.source_bytes))
        tokens.extend((item, existing_recovery_record(files, item)) for item in records)
    return proof, (tokens, current.source_bytes, basis, work, files.journal_entries())
