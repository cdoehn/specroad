"""Cooperating native Linux writer/recovery locks, not a transaction engine.

All lock kinds use one kernel mutex. Metadata alone never grants exclusivity;
orphan records are not stolen automatically, even after their PID disappears.
"""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
import os
from uuid import uuid4
from ..model.canonical import canonical_json_bytes
from ..storage.project import ProjectSource
from ..security import SafetyViolation
from .authoring import normalize_request_id
from .lock_values import (LockKind, LockRecord, LockStatus, OwnerIdentity,
                          ProjectLockError, LOCK_VERSION, text, kind_and_command)
from ._lock_process import LinuxOwnerProbe
from ._lock_owner_policy import observe_owner, _recovery_permitted
from ._lock_files import LockFiles, identity



def _bound(record, files, project_id):
    v = record.data
    if v['project_id'] != project_id or v['root_identity'] != identity(os.fstat(files.root_fd)):
        raise ProjectLockError('lock_project_binding_mismatch', exit_code=6)


def inspect_project_lock(root, *, expected_project_id=None, owner_probe=None):
    """Read-only metadata observation, including broken-config recovery cases.

    Does not acquire a writer lock, create files, repair records or load models.
    An absent record is not a reusable proof that no writer can start later.
    """
    if expected_project_id is not None:
        text(expected_project_id)
    probe = owner_probe if owner_probe is not None else LinuxOwnerProbe()
    with LockFiles(root) as files:
        record, inode = files.read_record()
        journals = files.journal_entries()
        if record is not None and expected_project_id is not None:
            _bound(record, files, expected_project_id)
        state = 'absent' if record is None else observe_owner(record, probe)
        again, again_inode = files.read_record()
        if ((None if again is None else again.source_bytes) != (None if record is None else record.source_bytes)
                or again_inode != inode or files.journal_entries() != journals):
            raise ProjectLockError('lock_status_changed', exit_code=6)
        return LockStatus.create({'format_version': LOCK_VERSION,
            'record': None if record is None else record.data,
            'record_sha256': None if record is None else record.sha256,
            'owner_state': state, 'journal_paths': list(journals),
            'recovery_required': record is not None or bool(journals),
            'observation_only': True, 'exclusive_access_proven': False,
            'write_authorized': False, 'atomic_snapshot': False})


class HeldProjectLock:
    """A live process-local guard, never serializable or transferable to a child."""
    def __init__(self, files, record, inode):
        self._files, self._record, self._inode = files, record, inode
        self._active = True
        self._pid = os.getpid()

    @property
    def record(self):
        return self._record

    def check(self):
        if not self._active or self._pid != os.getpid():
            raise ProjectLockError('lock_handle_not_active', exit_code=7)
        self._files.require_held()
        current, ident = self._files.read_record()
        if current is None or current.source_bytes != self._record.source_bytes or ident != self._inode:
            raise ProjectLockError('lock_owner_changed', exit_code=6)
        return True

    def __reduce__(self):
        raise TypeError('Live project locks cannot be serialized')

    def __copy__(self):
        raise TypeError('Live project locks cannot be copied')

    def __deepcopy__(self, memo):
        raise TypeError('Live project locks cannot be copied')


def _request(kind, command, project_id, request_id, transaction_id):
    selected = kind_and_command(kind, command)
    text(project_id)
    text(transaction_id, optional=True)
    if request_id is not None:
        text(request_id)
        normalize_request_id(request_id)
    if selected in (LockKind.WRITER, LockKind.RECOVERY) and transaction_id is None:
        raise ProjectLockError('lock_transaction_id_required', exit_code=2)
    return selected


@contextmanager
def project_lock(root, *, kind, command, project_id, transaction_id=None, request_id=None):
    """Acquire a nonblocking exclusive guard; release only this exact owner record.

    Writer: configuration identity and absence of unresolved journals required.
    Recovery: no normal model loading; journals remain for the recovery engine.
    Operational: same mutual exclusion, not permission to edit model data.
    Unknown host/start metadata stays null and later requires explicit recovery.
    """
    selected = _request(kind, command, project_id, request_id, transaction_id)
    source = ProjectSource(root, expected_project_id=project_id) if selected is LockKind.WRITER else None
    probe = LinuxOwnerProbe()
    owner = probe.current()
    with LockFiles(root) as files:
        files.acquire()
        if source is not None:
            if source.boundary._root_identity != files.boundary._root_identity:
                raise ProjectLockError('lock_project_binding_mismatch', exit_code=6)
            source.check_current()
        previous, _ = files.read_record()
        if previous is not None:
            _bound(previous, files, project_id)
            raise ProjectLockError('lock_recovery_required')
        journals = files.journal_entries()
        if selected is not LockKind.RECOVERY and journals:
            raise ProjectLockError('transaction_journal_blocks_lock')
        record = LockRecord(canonical_json_bytes({'format_version': LOCK_VERSION,
            'kind': selected.value, 'lock_id': str(uuid4()), 'project_id': project_id,
            'root_identity': identity(os.fstat(files.root_fd)), **owner.as_dict(),
            'created_at': datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z'),
            'command': command, 'request_id': request_id, 'transaction_id': transaction_id}))
        inode = files.create_record(record)
        guard = HeldProjectLock(files, record, inode)
        try:
            guard.check()
            if source is not None:
                source.check_current()
            if selected is not LockKind.RECOVERY and files.journal_entries():
                raise ProjectLockError('transaction_journal_blocks_lock')
            yield guard
        finally:
            # Child cleanup must never remove/unlock its parent's ownership.
            if os.getpid() == guard._pid:
                try:
                    guard.check()
                    files.remove_record(record, inode)
                finally:
                    guard._active = False



def recover_project_lock(root, *, project_id, expected_lock_sha256, actor, reason,
                         force=False, accept_remote_risk=False, owner_probe=None):
    """Explicit audited orphan removal, never a transaction recovery or takeover.

    A held native mutex, active same-host owner, unexpected root/owner bytes or
    pending journal always blocks removal. Consent only resolves owner-identity
    uncertainty; it never overrides these other checks. Host/PID observations
    are fresh kernel observations, not authenticated distributed ownership.
    """
    from .authoring import normalize_authoring_actor
    text(project_id); text(reason)
    if type(force) is not bool or type(accept_remote_risk) is not bool or not force:
        raise ProjectLockError('explicit_lock_recovery_force_required', exit_code=2)
    if (type(expected_lock_sha256) is not str or len(expected_lock_sha256) != 64
            or any(c not in '0123456789abcdef' for c in expected_lock_sha256)):
        raise ProjectLockError('expected_lock_sha256_required', exit_code=2)
    actor = normalize_authoring_actor(actor)
    # The explicit trusted adapter exists for embedded applications and tests;
    # the ordinary path only reads the local native kernel, never project code.
    probe = owner_probe if owner_probe is not None else LinuxOwnerProbe()
    attempted = False
    try:
        with LockFiles(root) as files:
            files.acquire()
            record, inode = files.read_record()
            if record is None:
                raise ProjectLockError('lock_record_missing', exit_code=6)
            _bound(record, files, project_id)
            if record.sha256 != expected_lock_sha256:
                raise ProjectLockError('lock_owner_changed', exit_code=6)
            if files.journal_entries():
                raise ProjectLockError('transaction_journal_blocks_lock')
            state = _recovery_permitted(record, probe, accept_remote_risk)
            event_id = str(uuid4())
            base = {'format_version': LOCK_VERSION, 'event_id': event_id,
                'command': 'lock recover', 'actor': actor.as_fields(), 'reason': reason,
                'force': True, 'accept_remote_risk': accept_remote_risk,
                'old_record': record.data, 'old_record_sha256': record.sha256,
                'observed_owner_state': state,
                'recoverer': LinuxOwnerProbe().current().as_dict(),
                'actor_authenticated': False, 'journal_recovery_performed': False,
                'write_authorized': False}
            def audit(phase):
                data = {**base, 'phase': phase,
                    'record_removed': phase == 'completed',
                    'observed_at': datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')}
                return files.append_audit(event_id, phase, canonical_json_bytes(data))
            # Persist intention first. It explicitly does not claim completion.
            attempted = True
            intent_path = audit('intent')
            current, current_inode = files.read_record()
            if current is None or current.source_bytes != record.source_bytes or current_inode != inode:
                raise ProjectLockError('lock_owner_changed', exit_code=6)
            _bound(current, files, project_id)
            _recovery_permitted(current, probe, accept_remote_risk)
            if files.journal_entries():
                raise ProjectLockError('transaction_journal_blocks_lock')
            files.remove_record(record, inode)
            completion_path = audit('completed')
            return LockStatus.create({**base, 'record_removed': True,
                'intent_path': intent_path, 'completion_path': completion_path,
                'new_lock_acquired': False, 'atomic_snapshot': False})
    except ProjectLockError as error:
        if attempted:
            error.mutation_possible = True
        raise
    except (OSError, SafetyViolation) as error:
        raise ProjectLockError('lock_recovery_io_failure', mutation_possible=attempted) from error
