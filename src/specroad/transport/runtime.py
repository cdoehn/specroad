"""Explicit, lazy use of the hash-pinned public PatchHarbor 1.8.0 API.

Only the selected standalone PYZ supplies code. Results are passive snapshot
inputs, never a bootstrap or fallback. No installer or external process runs.
"""
import importlib
import os
from pathlib import Path
import platform
import stat
import sys
from zipimport import zipimporter

from . import _contract


# Reuse only a completely checked private copy, regardless of request kind.
# A failed or foreign import is never evicted or adopted.
_prepared_runtime = None


class TransportUnavailable(ValueError):
    """Machine-readable refusal, never transport or gate success."""

    def __init__(self, reason, *, exit_code=2, capability=None, cause_type=None):
        super().__init__(reason)
        self.reason, self.exit_code = reason, exit_code
        self.capability, self.cause_type = capability, cause_type

    def as_dict(self):
        return {'status': 'unavailable', 'reason': self.reason,
                'exit_code': self.exit_code, 'capability': self.capability,
                'cause_type': self.cause_type, 'full_reference_valid': False}


def _check_request(required, *, safe_reference=False):
    if type(required) is not tuple or any(type(name) is not str for name in required):
        raise TransportUnavailable('invalid_capability_request')
    for name in required:
        if name != 'PH-API-RESULT' and name not in (_contract.OPERATIONS +
                (_contract.SAFE_OPERATIONS if safe_reference else ())):
            raise TransportUnavailable('api_capability_unavailable', capability=name)


def _check_platform():
    if (sys.implementation.name != 'cpython'
            or sys.version_info[:2] not in _contract.PYTHONS):
        raise TransportUnavailable('unsupported_transport_python')
    if sys.platform != 'linux' or platform.machine() != 'x86_64':
        raise TransportUnavailable('unsupported_transport_platform')


def _check_api(api, *, safe_reference=False):
    for name in _contract.OPERATIONS + (_contract.SAFE_OPERATIONS if safe_reference else ()):
        if not callable(getattr(api, name, None)):
            raise TransportUnavailable('api_capability_unavailable', capability=name)
    capabilities = api.integration_capabilities()
    for name in ('contract_version', 'snapshot_contract_version', 'guarded_apply_contract_version'):
        if type(getattr(capabilities, name, None)) is not int or getattr(capabilities, name) != 1:
            raise TransportUnavailable('unsupported_api_contract', capability='PH-API-RESULT')
    if safe_reference and (type(getattr(capabilities, 'safe_reference_contract_version', None)) is not int
            or capabilities.safe_reference_contract_version != 1):
        raise TransportUnavailable('unsupported_safe_reference_contract')


class _PreparedRuntime:
    """Own one exclusive copy; use existing descriptor-bound passive reads."""

    def __init__(self, source, workspace):
        from ._files import PassiveFile, directory, require
        parent = directory(workspace.parent, owned=True)
        descriptor = os.open(parent.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        child = None
        try:
            info = os.fstat(descriptor)
            require((info.st_dev, info.st_ino) == parent._root_identity, 'runtime_parent_changed')
            os.mkdir(workspace.name, mode=0o700, dir_fd=descriptor)
            child = os.open(workspace.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=descriptor)
            info = os.fstat(child)
            self.identity = info.st_dev, info.st_ino
            self.path = workspace / _contract.ARTIFACT_FILENAME
            output = os.open(_contract.ARTIFACT_FILENAME,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=child)
            with os.fdopen(output, 'wb') as stream:
                if stream.write(source.raw) != len(source.raw):
                    raise OSError('incomplete private runtime write')
                stream.flush(); os.fsync(stream.fileno())
            os.fsync(child)
            parent._check_root()
            info = workspace.lstat()
            require((info.st_dev, info.st_ino) == self.identity, 'runtime_workspace_changed')
            self.captured = PassiveFile(self.path, expected_sha256=_contract.ARTIFACT_SHA256,
                                        limit=_contract.MAX_ARTIFACT_BYTES)
        finally:
            if child is not None:
                os.close(child)
            os.close(descriptor)

    def verify(self):
        from ._files import directory, require
        boundary = directory(self.path.parent, owned=True)
        require(boundary._root_identity == self.identity, 'runtime_workspace_changed')
        for path in (self.path.parent, self.path):
            info = path.lstat()
            require(info.st_uid == os.getuid() and not stat.S_IMODE(info.st_mode) & 0o077,
                    'runtime_private_access_changed')
        self.captured.verify_current()


class PatchHarborRuntime:
    """Bind a standalone PYZ and its external digest without loading or writing.

Load explicitly into a new private workspace. Each use checks the original
input and the retained private copy; failed imports require a fresh process.
The immutable distribution pin is additional to the caller's expected digest.
"""

    def __init__(self, pyz, *, trusted_artifact_sha256, workspace, safe_reference=False):
        if type(safe_reference) is not bool:
            raise TransportUnavailable('invalid_runtime_contract')
        self._safe_reference = safe_reference
        if not _contract.valid_digest(trusted_artifact_sha256):
            raise TransportUnavailable('trusted_artifact_digest_required', exit_code=7)
        try:
            pyz, workspace = Path(pyz), Path(workspace)
        except (TypeError, ValueError) as error:
            raise TransportUnavailable('invalid_runtime_paths') from error
        if any(not p.is_absolute() or '..' in p.parts for p in (pyz, workspace)):
            raise TransportUnavailable('absolute_runtime_paths_required')
        self._source_path, self._workspace = pyz, workspace
        self._trusted_sha256 = trusted_artifact_sha256
        self._source = self._prepared = self._api = None
        self._failed = False

    def describe(self):
        value = _contract.describe_distribution(self._trusted_sha256, loaded=self._api is not None)
        if self._safe_reference:
            value['safe_reference_contract_version'] = 1
            value['api_capabilities'].update({name: True for name in _contract.SAFE_OPERATIONS})
        return value

    def _check_origins(self):
        for name, module in tuple(sys.modules.items()):
            if name != 'patchharbor' and not name.startswith('patchharbor.'):
                continue
            spec = getattr(module, '__spec__', None)
            loader = getattr(spec, 'loader', None)
            path = None if self._prepared is None else self._prepared.path
            if (path is None or not isinstance(loader, zipimporter)
                    or Path(loader.archive) != path
                    or not str(getattr(spec, 'origin', '')).startswith(str(path) + '/')
                    or not str(getattr(module, '__file__', '')).startswith(str(path) + '/')):
                raise TransportUnavailable('runtime_origin_conflict', exit_code=7)

    def load_api(self, *, required=()):
        """Verify the explicit artifact, prepare code once, return public API."""
        global _prepared_runtime
        _check_request(required, safe_reference=self._safe_reference)
        _check_platform()
        if self._failed:
            raise TransportUnavailable('fresh_process_required')
        from ._files import PassiveFile, directory
        from .snapshots import TransportFailure
        try:
            if self._source is None:
                self._source = PassiveFile(self._source_path, expected_sha256=self._trusted_sha256,
                                          limit=_contract.MAX_ARTIFACT_BYTES)
            else:
                directory(self._source_path.parent)
                self._source.verify_current()
            if self._source.sha256 != _contract.ARTIFACT_SHA256:
                raise TransportUnavailable('unsupported_runtime_distribution', exit_code=7)
            if self._prepared is None and _prepared_runtime is not None:
                self._prepared = _prepared_runtime
            self._check_origins()
            if self._prepared is None:
                self._prepared = _PreparedRuntime(self._source, self._workspace)
            self._prepared.verify()
            path = str(self._prepared.path)
            if not sys.path or sys.path[0] != path:
                sys.path.insert(0, path)
            api = importlib.import_module('patchharbor.api')
            self._check_origins()
            if getattr(sys.modules.get('patchharbor'), '__version__', None) != _contract.VERSION:
                raise TransportUnavailable('unsupported_runtime_distribution', exit_code=7)
            _check_api(api, safe_reference=self._safe_reference)
            # Imports/capability calls may have yielded control. Recheck both
            # physical inputs before adopting any API or publishing the cache.
            directory(self._source_path.parent)
            self._source.verify_current()
            self._prepared.verify()
        except BaseException as error:
            # Retain evidence and partial modules; never retry/switch in place.
            self._failed = True
            if isinstance(error, TransportUnavailable):
                raise
            if isinstance(error, OSError):
                raise TransportUnavailable('runtime_io_error', exit_code=5,
                                           cause_type=type(error).__name__) from error
            if isinstance(error, (ValueError, ImportError, TransportFailure)):
                raise TransportUnavailable('runtime_validation_failed', exit_code=7,
                                           cause_type=type(error).__name__) from error
            raise
        self._api = api
        _prepared_runtime = self._prepared
        return api

    def read_snapshot(self, result, *, expected_sha256):
        """Validate a passive Result using separately prepared public code."""
        from .snapshots import read_snapshot
        if self._api is None or self._failed:
            raise TransportUnavailable('explicit_runtime_load_required')
        api = self.load_api(required=('read_result_snapshot',))
        return read_snapshot(api, result, expected_sha256=expected_sha256)
