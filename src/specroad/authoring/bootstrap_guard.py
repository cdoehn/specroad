"""Durable, target-bound bootstrap protection; no stored record can resume work.

The parent mutex and exact sibling names protect even a not-yet-created root.
Only the original live creator removes its marker after complete publication.
"""
from contextvars import ContextVar
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import os

from ..changes._lock_files import LockFiles
from ..changes._lock_process import LinuxOwnerProbe
from ..changes._lock_owner_policy import observe_owner
from ..changes.lock_values import OwnerIdentity, ProjectLockError
from ..changes._journal_io import _read
from ..changes._staging_files import _write_new, _image
from ..changes.staging_values import StagingError
from ..model.canonical import canonical_json_bytes as jcs
from ..storage.json_syntax import parse_json_object as parsed
from ..model.errors import ModelError
from ..security import paths as guards
from ._bootstrap_io import BootstrapError, identity, info_at

_active = ContextVar('specroad_native_bootstrap_guard', default=None)


def _checkpoint(event):
    """Compiled durability seam for native process/fault tests."""


def names(target):
    token = sha256(os.fsencode(Path(target).name)).hexdigest()
    prefix = '.specroad-bootstrap-' + token
    return prefix + '.pending.json', prefix + '.owner.json'


def _record(raw, target, parent_identity):
    value = parsed(raw)
    expected = {'format_version', 'command_id', 'target_name', 'parent_identity',
                'root_before', 'input_sha256', 'target_inventory_sha256', 'owner', 'state'}
    if (set(value) != expected or raw != jcs(value)
            or value['format_version'] != 'bootstrap-guard-v1' or value['state'] != 'writing'
            or value['command_id'] not in ('init', 'bundle extract', 'transport open')
            or value['target_name'] != Path(target).name
            or value['parent_identity'] != parent_identity):
        raise BootstrapError('bootstrap_marker_binding', exit_code=5)
    for field in ('input_sha256', 'target_inventory_sha256'):
        token = value[field]
        if type(token) is not str or len(token) != 64 or any(c not in '0123456789abcdef' for c in token):
            raise BootstrapError('bootstrap_marker_binding', exit_code=5)
    before = value['root_before']
    if before is not None and (type(before) is not list or len(before) != 2
            or any(type(x) is not int or x < 0 for x in before)):
        raise BootstrapError('bootstrap_marker_binding', exit_code=5)
    owner = value['owner']
    if type(owner) is not dict or set(owner) != {'lock_id','host_id','process_id','process_start_id'}:
        raise BootstrapError('bootstrap_marker_owner', exit_code=5)
    from uuid import UUID
    uid = UUID(owner['lock_id'])
    if uid.version != 4 or str(uid) != owner['lock_id']:
        raise BootstrapError('bootstrap_marker_owner', exit_code=5)
    native_owner = OwnerIdentity(*(owner[k] for k in ('host_id','process_id','process_start_id')))
    return value, native_owner


def observe_bootstrap(root):
    """Read two bounded exact names, never scan a parent's other projects."""
    target = Path(os.path.abspath(root))
    pending, owner_path = names(target)
    present = False
    state, owner_state = 'clean', None
    try:
        with LockFiles(target.parent) as parent:
            records = []
            for name in (pending, owner_path):
                info = info_at(parent.root_fd, name)
                if info is None:
                    records.append(None)
                    continue
                present = True
                guards._regular(info)
                if (info.st_nlink != 1 or info.st_size > 65536 or info.st_mode & 0o7777 != 0o600
                        or info.st_uid != os.getuid() or info.st_dev != os.fstat(parent.root_fd).st_dev):
                    raise BootstrapError('bootstrap_marker_invalid', exit_code=5)
                raw = _read(parent.root_fd, name, expected_identity=guards._identity(info))
                records.append((raw, guards._identity(info)))
            if present:
                chosen = next(r for r in records if r is not None)
                value, owner = _record(chosen[0], target, identity(os.fstat(parent.root_fd)))
                if any(r is not None and r[0] != chosen[0] for r in records):
                    raise BootstrapError('bootstrap_marker_changed', exit_code=5)
                owner_state = observe_owner(SimpleNamespace(owner=owner), LinuxOwnerProbe())
                with parent.observe_mutex() as busy:
                    state = ('writer_active' if owner_state == 'alive' and busy else
                             'unknown' if owner_state in ('foreign','unverifiable') else 'corrupted')
                for name, original in zip((pending, owner_path), records):
                    info = info_at(parent.root_fd, name)
                    if original is None:
                        if info is not None:
                            raise BootstrapError('bootstrap_marker_changed', exit_code=5)
                    elif (info is None or guards._identity(info) != original[1]
                          or _read(parent.root_fd, name, expected_identity=original[1]) != original[0]):
                        raise BootstrapError('bootstrap_marker_changed', exit_code=5)
            parent.check_root()
    except FileNotFoundError:
        state = 'corrupted' if present else 'clean'
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ProjectLockError,
            ModelError, BootstrapError, guards.SafetyViolation):
        state = 'corrupted' if present else 'unknown'
    return dict(format_version='bootstrap-state-v1', state=state, owner_state=owner_state,
        project_corrupted=state == 'corrupted', manual_git_restore_required=state == 'corrupted',
        normal_operation_started=False, write_authorized=False, observation_only=True,
        exit_code=0 if state == 'clean' else 5)


def require_bootstrap_complete(root):
    current = _active.get()
    if type(current) is BootstrapGuard and current.target == Path(os.path.abspath(root)):
        current.check()
        return
    target=Path(os.path.abspath(root))
    state = observe_bootstrap(target)
    if state['state']=='clean' and target.name=='project':
        state=observe_bootstrap(target.parent)
    if state['state'] != 'clean':
        error = BootstrapError('project_corrupted' if state['project_corrupted'] else
                               'bootstrap_' + state['state'], exit_code=5)
        error.observation = state
        raise error


class BootstrapGuard:
    """A live, descriptor-bound creator capability, never reconstructed from disk."""
    def __init__(self, parent, target, command, content, directories, *, input_binding):
        if type(parent) is not LockFiles:
            raise BootstrapError('bootstrap_native_mutex_required', exit_code=7)
        parent.require_held()
        self.parent, self.target = parent, Path(target)
        self.pending, self.owner_path = names(target)
        self.records = {}
        self.removed = set()
        self.token = None
        self.completed = False
        self.started = False
        self.root_before = info_at(parent.root_fd, self.target.name)
        for name in (self.pending, self.owner_path):
            if info_at(parent.root_fd, name) is not None:
                raise BootstrapError('project_corrupted', exit_code=5, path=name)
        inventory = dict(files=[dict(path=p, size=len(raw), sha256=sha256(raw).hexdigest())
                                for p, raw in sorted(content.items())], directories=sorted(directories))
        owner = LinuxOwnerProbe().current()
        self.value = dict(format_version='bootstrap-guard-v1', command_id=command,
            target_name=self.target.name, parent_identity=identity(os.fstat(parent.root_fd)),
            root_before=None if self.root_before is None else identity(self.root_before),
            input_sha256=sha256(jcs(input_binding)).hexdigest(),
            target_inventory_sha256=sha256(jcs(inventory)).hexdigest(),
            owner=dict(lock_id=str(uuid4()), **owner.as_dict()), state='writing')
        self.raw = jcs(self.value)
        _record(self.raw, self.target, identity(os.fstat(parent.root_fd)))

    def _create_record(self, name):
        try:
            return _write_new(self.parent.root_fd, name, self.raw)
        except StagingError as error:
            raise BootstrapError('bootstrap_marker_write_failed', exit_code=5,
                                 path=name, mutation_possible=True) from error

    def start(self):
        self.parent.require_held()
        _checkpoint('before_marker')
        current = info_at(self.parent.root_fd, self.target.name)
        if (None if current is None else identity(current)) != self.value['root_before']:
            raise BootstrapError('bootstrap_root_changed')
        for name in (self.pending, self.owner_path):
            if info_at(self.parent.root_fd, name) is not None:
                raise BootstrapError('project_corrupted', exit_code=5, path=name)
        # The owner survives a failed marker unlink/fsync; neither is cleaned on error.
        self.started = True
        self.records[self.owner_path] = self._create_record(self.owner_path)
        _checkpoint('owner_synced')
        self.records[self.pending] = self._create_record(self.pending)
        self.token = _active.set(self)
        self.check()
        _checkpoint('marker_synced')
        self.check()

    def check(self):
        self.parent.require_held()
        for name in self.removed:
            if info_at(self.parent.root_fd,name) is not None:
                raise BootstrapError("bootstrap_marker_reappeared",exit_code=5)
        for name, ident in self.records.items():
            try:
                _image(self.parent.root_fd, name, len(self.raw), sha256(self.raw).hexdigest(), identity=ident)
            except StagingError as error:
                raise BootstrapError('bootstrap_marker_changed', exit_code=5,
                                     path=name, mutation_possible=True) from error
            info=info_at(self.parent.root_fd,name)
            if info.st_mode & 0o7777 != 0o600 or info.st_uid != os.getuid():
                raise BootstrapError('bootstrap_marker_metadata_changed',exit_code=5)

    def finish(self, verify):
        self.check()
        verify()
        self.check()
        _checkpoint('target_verified')
        verify()
        self.check()
        _checkpoint('before_marker_unlink')
        self.check()
        os.unlink(self.pending, dir_fd=self.parent.root_fd)
        self.records.pop(self.pending)
        self.removed.add(self.pending)
        _checkpoint('marker_unlinked')
        os.fsync(self.parent.root_fd)
        _checkpoint('marker_removed')
        self.check()
        verify()
        self.check()
        # Publication is now durably complete. The owner is ordinary lock cleanup.
        self.completed = True
        os.unlink(self.owner_path, dir_fd=self.parent.root_fd)
        self.records.pop(self.owner_path)
        self.removed.add(self.owner_path)
        os.fsync(self.parent.root_fd)
        _checkpoint('owner_removed')
        self.check()
        verify()

    def close(self):
        if self.token is not None:
            _active.reset(self.token)
            self.token = None
