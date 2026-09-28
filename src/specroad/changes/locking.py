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
from .authoring import normalize_request_id
from .lock_values import (LockKind, LockRecord, LockStatus, OwnerIdentity,
                          ProjectLockError, LOCK_VERSION, text, kind_and_command)
from ._lock_process import LinuxOwnerProbe
from ._lock_files import LockFiles, identity


def observe_owner(record, probe):
    owner = record.owner
    host = probe.host_id()
    if host is None or owner.host_id is None:
        return 'unverifiable'
    if host != owner.host_id:
        return 'foreign'
    if owner.process_start_id is None:
        return 'unverifiable'
    state, start = probe.process(owner.process_id)
    if state == 'absent':
        return 'dead'
    if state not in ('alive', 'dead') or start is None:
        return 'unverifiable'
    if start != owner.process_start_id:
        return 'pid_reused'
    return state


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
