"""Explicit restart preparation from persisted inputs; never a write authority."""
from dataclasses import dataclass

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..storage.json_syntax import parse_json_object
from ._journal_codec import _hash, _text, _transaction
from ._lock_files import LockFiles
from ._discard_basis import observe_prepared_basis
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
    def _create(cls, files, journal, basis):
        obj = object.__new__(cls)
        object.__setattr__(obj, '_journal_bytes', journal.source_bytes)
        object.__setattr__(obj, '_root', str(files.boundary.root))
        object.__setattr__(obj, '_root_identity', files.boundary._root_identity)
        object.__setattr__(obj, '_observation', canonical_json_bytes({
            'format_version': 'discard-preflight-v1', 'transaction_id': journal.data['transaction_id'],
            'project_id': journal.data['project_id'], 'journal_sha256': journal.sha256,
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

    def _check(self, files, journal):
        if (journal.source_bytes != self._journal_bytes
                or str(files.boundary.root) != self._root
                or files.boundary._root_identity != self._root_identity):
            raise RecoveryError('discard_preflight_binding_mismatch', exit_code=6)
        return observe_prepared_basis(files, journal)


def prepare_discard_recovery(root, transaction_id, *, expected_project_id, expected_journal_sha256):
    """Prove a complete prepared basis and work set without planning or writing.

    The caller still needs a new native recovery lock and fresh host authority.
    Building, incomplete work and legacy journals lacking explicit selection
    remain protected; no implicit profile choice or original plan is invented.
    """
    from ._recovery_inputs import _read_journal, _parse, _work
    _transaction(transaction_id)
    if not _text(expected_project_id) or not _hash(expected_journal_sha256):
        raise RecoveryError('explicit_discard_binding_required', exit_code=2)
    try:
        with LockFiles(root) as files:
            before = _read_journal(files, transaction_id)
            journal = _parse(before[0], transaction_id, files, expected_project_id)
            if journal.sha256 != expected_journal_sha256:
                raise RecoveryError('recovery_journal_changed', exit_code=6)
            basis = observe_prepared_basis(files, journal)
            work = _work(files, journal)
            if (observe_prepared_basis(files, journal) != basis
                    or _work(files, journal) != work
                    or _read_journal(files, transaction_id) != before):
                raise RecoveryError('discard_preflight_inputs_changed', exit_code=6)
            return DiscardPreflight._create(files, journal, basis)
    except RecoveryError:
        raise
    except (OSError, SafetyViolation, ModelError) as error:
        raise RecoveryError(getattr(error, 'reason', 'discard_preflight_unavailable'),
                            exit_code=getattr(error, 'exit_code', 5)) from error
