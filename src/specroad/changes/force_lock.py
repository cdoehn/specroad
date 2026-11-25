"""A separate observed Force attempt using the native lock and writer handles.

No foreign record is removed. A refused advisory mutex is overridden only for
the exact owner selected by the caller; byte/identity changes still fail.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import os
from uuid import uuid4

from ..force_operations import current, selected_owner
from ..model.errors import ModelError
from ..model.canonical import canonical_json_bytes as jcs
from ._lock_files import LockFiles, identity
from ._lock_process import LinuxOwnerProbe
from ._lock_owner_policy import observe_owner
from .locking import HeldProjectLock
from .lock_values import LockRecord, LOCK_VERSION, ProjectLockError
from ._schema_transition_io import project_files
from ._staging_files import _write_new
from .write_guard_values import require, inventory

ATTEMPTS = '.specroad/write-state/force-attempts'


def attempt_root(transaction):
    from ._journal_codec import _transaction
    _transaction(transaction)
    return ATTEMPTS + '/' + transaction


def observation(files, *, excluding=None):
    """All original operational bytes and real file identities, never a PID guess."""
    values, _, _ = project_files(files)
    values = {p: raw for p, raw in values.items() if p.startswith('.specroad/')
        and not (excluding and p.startswith(excluding + '/'))}
    identities = {}
    for path in values:
        with files.directory(tuple(path.split('/')[:-1])) as fd:
            info = os.stat(path.rsplit('/', 1)[-1], dir_fd=fd, follow_symlinks=False)
            identities[path] = (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid)
    from .force_bootstrap import observe
    siblings, sibling_ids = observe(files)
    values.update(siblings); identities.update(sibling_ids)
    return values, identities


def check_selected_owner(files, originals, decisions, selected):
    """Observe the actual owner even if an unrelated broken marker hides diagnosis."""
    from ..model.errors import ModelError
    from .force_bootstrap import check_selection
    check_selection(files, originals, decisions, selected)
    raw = originals.get('.specroad/locks/project.json')
    state = None
    if raw is not None:
        try:
            state = observe_owner(LockRecord(raw), LinuxOwnerProbe())
        except (ValueError, TypeError, ModelError):
            state = 'unknown'
    with files.observe_mutex() as busy:
        required = busy or state in ('alive', 'foreign', 'unverifiable', 'unknown')
        explicitly_selected = any(row['path'] == '.specroad/locks/project.json' for row in selected['owners'])
        require(not (required or explicitly_selected) or selected_owner('.specroad/locks/project.json', raw),
            'explicit_concurrent_owner_required', exit_code=6)
        if raw is not None:
            decisions.decide(False, gate_id='lock:retained_owner', diagnostic_code='CORE_SECURITY',
                subject='.specroad/locks/project.json', operation='change.apply',
                observed_binding={'sha256': sha256(raw).hexdigest(), 'owner_state': state},
                requested_binding=selected, effect='preserve_foreign_owner_execute_own_attempt')
        if busy:
            decisions.decide(False, gate_id='lock:exclusive_access', diagnostic_code='CORE_SECURITY',
                subject='project', operation='change.apply', observed_binding={'exclusive_access_proven': False},
                requested_binding=selected, effect='execute_without_exclusivity_guarantee')


class AttemptFiles(LockFiles):
    def __init__(self, root, transaction, original):
        super().__init__(root)
        self.attempt = attempt_root(transaction)
        self.original = original
        self.exclusive = False
        self._force_access = False

    def acquire(self):
        try:
            super().acquire()
            self.exclusive = True
        except ProjectLockError as error:
            if error.reason != 'project_lock_busy':
                raise
            raw = self.original[0].get('.specroad/locks/project.json')
            require(selected_owner('.specroad/locks/project.json', raw),
                'explicit_concurrent_owner_required', exit_code=6)
            self._force_access = True
        self.check_original()

    def require_held(self):
        if self._force_access:
            require(self.creator_pid == os.getpid(), 'inherited_force_handle', exit_code=7)
            self.check_root()
        else:
            super().require_held()

    def check_original(self):
        actual = observation(self, excluding=self.attempt)
        if actual != self.original:
            call = current()
            if call is not None:
                call.decisions.decide(False, gate_id='hash:operational_source',
                    diagnostic_code='CORE_CONFLICT', subject='operational_state', operation='change.apply',
                    observed_binding=inventory(actual[0]), requested_binding=inventory(self.original[0]),
                    effect='own_publication_not_confirmed_original_changed')
            require(False, 'force_original_changed', exit_code=6)

    def read_record(self):
        with self.directory(tuple(self.attempt.split('/'))) as fd:
            if fd is None or 'owner.json' not in os.listdir(fd):
                return None, None
            raw, ident = self._read(fd, 'owner.json')
            self.check_original()
            return LockRecord(raw), ident

    def create_record(self, record):
        self.require_held()
        with self.directory(tuple(self.attempt.split('/'))) as fd:
            require(fd is None, 'force_attempt_collision', exit_code=6)
        with self.directory(tuple(self.attempt.split('/')), create=True) as fd:
            require(not os.listdir(fd), 'force_attempt_collision', exit_code=6)
            return _write_new(fd, 'owner.json', record.source_bytes)


@contextmanager
def force_project_lock(root, *, plan, transaction_id, original, decisions):
    data = plan.data
    with AttemptFiles(root, transaction_id, original) as files:
        files.acquire()
        old_journals = files.journal_entries()
        raw = original[0].get('.specroad/locks/project.json')
        if raw is not None:
            try:
                old = LockRecord(raw)
                state = observe_owner(old, LinuxOwnerProbe())
            except (ValueError, TypeError, ModelError):
                state = 'unknown'
            if state in ('alive', 'foreign', 'unverifiable', 'unknown'):
                require(selected_owner('.specroad/locks/project.json', raw),
                    'explicit_concurrent_owner_required', exit_code=6)
            decisions.decide(False, gate_id='lock:retained_owner', diagnostic_code='CORE_SECURITY',
                subject='.specroad/locks/project.json', operation='change.apply',
                observed_binding={'sha256': sha256(raw).hexdigest(), 'owner_state': state},
                requested_binding=data['operational_binding'], effect='preserve_foreign_owner_execute_own_attempt')
        if not files.exclusive:
            decisions.decide(False, gate_id='lock:exclusive_access', diagnostic_code='CORE_SECURITY',
                subject='project', operation='change.apply', observed_binding={'exclusive_access_proven': False},
                requested_binding=data['operational_binding'], effect='execute_without_exclusivity_guarantee')
        stamp = {'format_version': 'force-attempt-before-v1', 'plan_sha256': plan.sha256,
            'root_identity': identity(os.fstat(files.root_fd)),
            'operational_inventory': inventory(original[0]),
            'operational_identities': {p: list(i) for p, i in sorted(original[1].items())},
            'exclusive_access_proven': files.exclusive, 'foreign_operation_completed': False}
        record = LockRecord(jcs(dict(format_version=LOCK_VERSION, kind='writer', lock_id=str(uuid4()),
            project_id=data['project_id'], root_identity=stamp['root_identity'],
            **LinuxOwnerProbe().current().as_dict(),
            created_at=datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z'),
            command='change apply', request_id=data['request_id'], transaction_id=transaction_id)))
        inode = files.create_record(record)
        guard = HeldProjectLock(files, record, inode)
        guard.force_journals = old_journals
        guard.force_before = stamp
        guard.force_storage = tuple(files.attempt.split('/'))
        try:
            guard.check()
            yield guard
            guard.check()
        finally:
            # Retain the attempt's owner as provenance; never unlock a foreign OFD.
            guard._active = False
