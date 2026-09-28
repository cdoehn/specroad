"""Read-only preflight and mandatory last recheck under a real writer lock.

These checks do not implement a journal or a durable filesystem writer. Only
explicitly registered trusted code can publish. Early success is NEVER a
reusable permission; native writers must still check their actual syscalls.
"""
from dataclasses import dataclass
from hashlib import sha256
import os
import stat

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..model.paths import CURRENT_JSON_CLASSES, PathClass
from ..validation import ModelDocument
from ..security import SafetyViolation, ProjectBoundary
from ..security.resource_access import opened_resource
from ..storage.byte_binding import fingerprint_reader
from ..storage.json_syntax import parse_json_object
from ..storage.project import ProjectSource
from ..storage.resource_discovery import current_json_paths
from .execution_values import ChangeExecutionError, PublicationRequest
from .locking import HeldProjectLock
from .lock_values import ProjectLockError
from .target import assess_change_target
from .target_model import TargetModel
from .target_values import TargetPolicy
from .values import ChangePlan

CHECK_VERSION = 'publication-recheck-v1'
_ACCESS_SUPPORTED = os.access in os.supports_dir_fd and os.access in os.supports_effective_ids


class PublicationCheckError(ChangeExecutionError):
    """A refusal is not a rollback of earlier staging or a retry instruction."""
    def __init__(self, reason, *, path=None, exit_code=6, write_state='not_committed'):
        super().__init__(reason, exit_code=exit_code, write_state=write_state)
        self.path = path

    def diagnostic(self):
        return {**super().diagnostic(), 'path': self.path, 'write_authorized': False}


@dataclass(frozen=True)
class PublicationAuthority:
    """Trusted host registration, NEVER reconstructed from project/plan data.

    check(detached_request) must return an actual bool. The host implements real
    authentication/authorization; actor labels and this registration are not an
    authentication mechanism or a sandbox for callback code.
    """
    authority_id: str
    version: str
    check: object

    def __post_init__(self):
        if (any(type(v) is not str or not v.strip() or '\0' in v
                for v in (self.authority_id, self.version)) or not callable(self.check)):
            raise PublicationCheckError('registered_publication_authority_required', exit_code=2)


@dataclass(frozen=True, init=False)
class PublicationPreflight:
    _request: PublicationRequest
    _model: TargetModel
    _policy: TargetPolicy
    _strict: bool
    _footprint: bytes
    _package_files: tuple

    def __init__(self, *args, **kwargs):
        raise TypeError('Use prepare_publication_check')

    @classmethod
    def _create(cls, request, model, policy, strict, footprint, package_files):
        obj = object.__new__(cls)
        for name, value in (('_request', request.detached()), ('_model', model.snapshot()),
                ('_policy', policy), ('_strict', strict), ('_footprint', canonical_json_bytes(footprint)),
                ('_package_files', tuple(ModelDocument(d.path,d.content) for d in package_files))):
            object.__setattr__(obj, name, value)
        return obj

    @property
    def request(self):
        return self._request.detached()

    @property
    def data(self):
        return {'format_version': CHECK_VERSION, 'phase': 'early_diagnostic',
                'request_sha256': self._request.sha256,
                'footprint_sha256': sha256(self._footprint).hexdigest(),
                'observed_paths': sorted([*self._model.source_files, *(d.path for d in self._package_files)]),
                'final_check_required': True, 'write_authorized': False,
                'project_lock_acquired': False, 'atomic_snapshot': False}

    def __bool__(self):
        raise TypeError('A preflight is not a permission to publish')


@dataclass(frozen=True, init=False)
class PublicationRecheck:
    _raw: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use recheck_publication')

    @classmethod
    def _create(cls, request, held_lock, authority):
        obj = object.__new__(cls)
        object.__setattr__(obj, '_raw', canonical_json_bytes({
            'format_version': CHECK_VERSION, 'phase': 'locked_final_check',
            'request_sha256': request.sha256, 'plan_sha256': request.plan.sha256,
            'lock_id': held_lock.record.data['lock_id'],
            'authority_id': authority.authority_id, 'authority_version': authority.version,
            'host_authority_allowed': True, 'ready_for_backend': True,
            'preflight_reused_as_proof': False, 'write_authorized': False,
            'reusable_capability': False, 'normative_writes': 0,
            'atomic_snapshot': False, 'durability_verified': False}))
        return obj

    @property
    def data(self):
        return parse_json_object(self._raw)

    def __bool__(self):
        raise TypeError('A final observation is not a reusable write capability')


def _stamp(info):
    # Timestamps do not establish content identity. Hash every byte on each pass.
    return {'device': str(info.st_dev), 'inode': str(info.st_ino),
            'mode': stat.S_IMODE(info.st_mode), 'uid': str(info.st_uid),
            'gid': str(info.st_gid), 'links': None if stat.S_ISDIR(info.st_mode) else info.st_nlink}


def _root(model):
    root = model.binding.source_root
    info = os.lstat(root)
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise PublicationCheckError('unsafe_publication_root', exit_code=7)
    if (info.st_dev, info.st_ino) != model.binding.root_identity:
        raise PublicationCheckError('publication_root_changed')
    boundary = ProjectBoundary(root)
    if boundary.read_bytes('specroad.json') != model.configuration_bytes:
        raise PublicationCheckError('publication_configuration_changed', path='specroad.json')
    source = ProjectSource(root, expected_project_id=model.binding.project_id)
    if (str(source.boundary.root) != root or
            source.boundary._root_identity != model.binding.root_identity):
        raise PublicationCheckError('publication_root_changed')
    if source.configuration_bytes != model.configuration_bytes:
        raise PublicationCheckError('publication_configuration_changed', path='specroad.json')
    return source


def _rights(fd, path):
    # Advisory even under a cooperating writer lock: actual publication still
    # needs error handling for ACL/mount changes, quotas, ENOSPC and I/O errors.
    if not _ACCESS_SUPPORTED:
        raise PublicationCheckError('effective_permission_probe_unavailable', exit_code=7, path=path)
    mode = os.fstat(fd).st_mode
    if not mode & 0o222 or not mode & 0o111 or not os.access(
            '.', os.W_OK | os.X_OK, dir_fd=fd, effective_ids=True):
        raise PublicationCheckError('publication_parent_not_writable', exit_code=7, path=path)
    if hasattr(os, 'fstatvfs') and os.fstatvfs(fd).f_flag & getattr(os, 'ST_RDONLY', 1):
        raise PublicationCheckError('publication_mount_read_only', exit_code=7, path=path)


def _parent(source, path, *, writable=True):
    parent = path.rsplit('/', 1)[0] if '/' in path else ''
    parts = parent.split('/') if parent else []
    observed = {}
    deepest = ''
    fd = os.open(source.boundary.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        root_info = os.fstat(fd)
        if (root_info.st_dev, root_info.st_ino) != source.boundary._root_identity:
            raise PublicationCheckError('publication_root_changed')
        observed[''] = _stamp(root_info)
        if not parts and writable:
            _rights(fd, '')
        for index in range(len(parts)):
            relative = '/'.join(parts[:index + 1])
            try:
                with opened_resource(source.boundary, relative, directory=True) as (directory, info):
                    observed[relative] = _stamp(info)
            except FileNotFoundError:
                # Absence belongs to the observation; no mkdir or write probe.
                for j in range(index, len(parts)):
                    observed['/'.join(parts[:j + 1])] = None
                break
            deepest = relative
        if writable and parts:
            if deepest:
                with opened_resource(source.boundary, deepest, directory=True) as (directory, info):
                    if _stamp(info) != observed[deepest]:
                        raise PublicationCheckError('publication_parent_changed', path=deepest)
                    _rights(directory, deepest)
            else:
                _rights(fd, '')
    finally:
        os.close(fd)
    return observed


def _package_bindings(source, model, package_files):
    if type(package_files) not in (tuple, list) or any(type(d) is not ModelDocument for d in package_files):
        raise PublicationCheckError('explicit_package_file_bindings_required', exit_code=2)
    files = tuple(ModelDocument(d.path,d.content) for d in package_files)
    names = [d.path for d in files]
    if len(set(p.casefold() for p in names)) != len(names) or set(names) & set(model.source_files):
        raise PublicationCheckError('duplicate_publication_package_path', exit_code=2)
    if any(source.classify(d.path) not in (PathClass.PROFILE, PathClass.RULE) for d in files):
        raise PublicationCheckError('publication_package_path_unmanaged', exit_code=7)
    expected = sorted(sha256(p.source_bytes).hexdigest() for p in model.language_packages)
    actual = sorted(sha256(d.content).hexdigest() for d in files)
    if actual != expected:
        raise PublicationCheckError('live_language_package_bindings_required', exit_code=2)
    return files


def _observe(source, model, request, package_files=()):
    source.check_current()
    files = {**model.source_files, **{d.path:d.content for d in package_files}}
    expected_json = tuple(sorted(p for p in files if source.classify(p) in CURRENT_JSON_CLASSES))
    if current_json_paths(source) != expected_json:
        raise PublicationCheckError('publication_inventory_changed')
    states, parents = {}, {}
    for path, expected in sorted(files.items()):
        parents.update(_parent(source, path, writable=False))
        with opened_resource(source.boundary, path) as (fd, info):
            if info.st_nlink != 1:
                raise PublicationCheckError('linked_publication_input', path=path, exit_code=7)
            actual = fingerprint_reader(lambda n: os.read(fd, n), info.st_size)
            if actual.size != len(expected) or actual.sha256 != sha256(expected).hexdigest():
                raise PublicationCheckError('publication_base_changed', path=path)
            states[path] = {**_stamp(info), 'size': actual.size, 'sha256': actual.sha256}
    for document in request.documents:
        path = document.path
        source.require_write_target(path)
        parents.update(_parent(source, path))
        if path not in files:
            try:
                with opened_resource(source.boundary, path):
                    pass
            except FileNotFoundError:
                pass
            else:
                raise PublicationCheckError('publication_create_target_exists', path=path)
    if current_json_paths(source) != expected_json:
        raise PublicationCheckError('publication_inventory_changed')
    source.check_current()
    return {'files': states, 'parents': parents,
            'root': _stamp(os.lstat(source.boundary.root))}


def _translate(error):
    if isinstance(error, PublicationCheckError):
        return error
    if isinstance(error, ProjectLockError):
        return PublicationCheckError(error.reason, exit_code=error.exit_code)
    if isinstance(error, PermissionError):
        return PublicationCheckError('publication_permission_denied', exit_code=7)
    if isinstance(error, FileNotFoundError):
        return PublicationCheckError('publication_resource_missing')
    if isinstance(error, ModelError):
        code = 6 if error.reason in ('configuration_changed', 'project_identity_mismatch') else 3
        return PublicationCheckError(error.reason, exit_code=code)
    if isinstance(error, SafetyViolation):
        return PublicationCheckError('unsafe_publication_path', exit_code=7)
    return PublicationCheckError('publication_check_io_failure', exit_code=5)


def _same_request(actual, expected):
    if (type(actual) is not PublicationRequest or actual._encoded != expected._encoded
            or actual._plan_bytes != expected._plan_bytes or actual.documents != expected.documents):
        raise PublicationCheckError('publication_request_changed')


def prepare_publication_check(plan, model, *, policy, gates=(), strict=False, package_files=()):
    """Early read-only diagnostic. Does not acquire any lock or create paths.

    Captures complete current normative JSON names and all explicitly bound raw
    resource bytes. A journal/authorization/permission observation now cannot
    replace the mandatory fresh checks at the later publication boundary.
    """
    if type(plan) is not ChangePlan or type(model) is not TargetModel or type(policy) is not TargetPolicy:
        raise PublicationCheckError('publication_plan_model_policy_required', exit_code=2)
    if type(gates) not in (list, tuple) or type(strict) is not bool:
        raise PublicationCheckError('publication_explicit_options_required', exit_code=2)
    plan, model = ChangePlan(plan.source_bytes), model.snapshot()
    try:
        source = _root(model)
        package_files = _package_bindings(source, model, package_files)
        checked = assess_change_target(plan, model, policy=policy, gates=tuple(gates), strict=strict)
        if not checked.target_validated:
            raise PublicationCheckError('publication_target_not_validated', exit_code=3)
        request = PublicationRequest._create(checked, model)
        first = _observe(source, model, request, package_files)
        if first != _observe(source, model, request, package_files):
            raise PublicationCheckError('publication_inputs_changed')
        return PublicationPreflight._create(request, model, policy, strict, first, package_files)
    except (OSError, SafetyViolation, ModelError) as error:
        if isinstance(error, PublicationCheckError):
            raise
        raise _translate(error) from error


def recheck_publication(preflight, request, *, held_lock, transaction_id,
                        authority, gates=()):
    """Recompute under the SAME native writer lock, never silently rebase.

    The trusted host is reauthorized and target gates rerun. Afterwards all raw
    bytes, current JSON names, parents, permissions, root, owner and recovery
    state are checked again. Returned observations cannot be used for a later
    write without another fresh check. No file mutation occurs here.
    """
    if type(preflight) is not PublicationPreflight or type(held_lock) is not HeldProjectLock:
        raise PublicationCheckError('preflight_and_native_writer_lock_required', exit_code=2)
    if type(authority) is not PublicationAuthority or type(gates) not in (tuple, list):
        raise PublicationCheckError('registered_authority_and_gates_required', exit_code=2)
    _same_request(request, preflight._request)
    model, plan = preflight._model.snapshot(), preflight._request.plan
    package_files = preflight._package_files
    try:
        source = _root(model)
        def lock_check():
            held_lock.require_publication(source, command='change apply',
                request_id=plan.data['request_id'], transaction_id=transaction_id)
        lock_check()
        first = _observe(source, model, request, package_files)
        if canonical_json_bytes(first) != preflight._footprint:
            raise PublicationCheckError('publication_footprint_changed')
        checked = assess_change_target(plan, model, policy=preflight._policy,
                                      gates=tuple(gates), strict=preflight._strict)
        if not checked.target_validated:
            raise PublicationCheckError('publication_target_not_validated', exit_code=3)
        _same_request(PublicationRequest._create(checked, model), preflight._request)
        handoff = request.detached()
        try:
            allowed = authority.check(handoff)
        except Exception as error:
            raise PublicationCheckError('publication_authority_failed', exit_code=7) from error
        _same_request(handoff, preflight._request)
        if type(allowed) is not bool or not allowed:
            raise PublicationCheckError('publication_authorization_denied', exit_code=7)
        lock_check()
        # Last complete read, after callbacks and immediately before the boundary.
        if canonical_json_bytes(_observe(source, model, request, package_files)) != preflight._footprint:
            raise PublicationCheckError('publication_footprint_changed')
        _same_request(request, preflight._request)
        lock_check()
        return PublicationRecheck._create(request, held_lock, authority)
    except (OSError, SafetyViolation, ModelError) as error:
        if isinstance(error, PublicationCheckError):
            raise
        raise _translate(error) from error


def publish_after_recheck(preflight, request, *, held_lock, transaction_id,
                          authority, publish, gates=()):
    """Invoke trusted host publication directly after the mandatory last check.

    The host retains the actual lock for staging/publication/readback, journal,
    recovery and durable receipt work. No built-in file writer is installed.
    The returned callback value is NOT a durable-commit or target-readback proof.
    This adapter can be used by ChangeBackend.publish; its existing receipt and
    target readback validation still apply. Never retries or rolls back.
    """
    if not callable(publish):
        raise PublicationCheckError('registered_publisher_required', exit_code=2)
    recheck_publication(preflight, request, held_lock=held_lock,
        transaction_id=transaction_id, authority=authority, gates=gates)
    outgoing = request.detached()
    try:
        result = publish(outgoing)
        _same_request(outgoing, preflight._request)
        held_lock.check()
        return result
    except Exception as error:
        reason = error.reason if isinstance(error, ChangeExecutionError) else 'publication_callback_failed'
        raise PublicationCheckError(reason, exit_code=5, write_state='unknown') from error
