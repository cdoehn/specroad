"""Explicit, lazy access to the pinned public PatchHarbor API.

The bootstrap is the unchanged reviewed helper delivered with PatchHarbor 1.6.0.
Its descriptor precheck is deliberately not a full Result/snapshot validator.
No registration, Git action, installer, subprocess or transport is started here.
The returned API grants no proposal, review or automatic host-apply authority.
"""

import importlib
from pathlib import Path
import platform
import sys
from zipimport import zipimporter

from . import _contract


class TransportUnavailable(ValueError):
    """Machine-readable refusal; it never represents transport or gate success."""

    def __init__(self, reason, *, exit_code=2, capability=None, cause_type=None):
        super().__init__(reason)
        self.reason = reason
        self.exit_code = exit_code
        self.capability = capability
        self.cause_type = cause_type

    def as_dict(self):
        return {'status': 'unavailable', 'reason': self.reason,
                'exit_code': self.exit_code, 'capability': self.capability,
                'cause_type': self.cause_type, 'full_reference_valid': False}


def _check_request(required):
    if (type(required) is not tuple
            or any(type(name) is not str for name in required)):
        raise TransportUnavailable('invalid_capability_request')
    for name in required:
        if name != 'PH-API-RESULT' and name not in _contract.OPERATIONS:
            raise TransportUnavailable('api_capability_unavailable', capability=name)


def _check_platform():
    if (sys.implementation.name != 'cpython'
            or sys.version_info[:2] not in _contract.PYTHONS):
        raise TransportUnavailable('unsupported_transport_python')
    if sys.platform != 'linux' or platform.machine() != 'x86_64':
        raise TransportUnavailable('unsupported_transport_platform')


def _check_distribution(assessment):
    if (assessment.version != _contract.VERSION
            or assessment.artifact_sha256 != _contract.ARTIFACT_SHA256
            or assessment.requires_python != _contract.REQUIRES_PYTHON):
        raise TransportUnavailable('unsupported_runtime_distribution', exit_code=7)


def _check_api(api):
    for name in _contract.OPERATIONS:
        if not callable(getattr(api, name, None)):
            raise TransportUnavailable('api_capability_unavailable', capability=name)
    capabilities = api.integration_capabilities()
    if (type(capabilities.contract_version) is not int
            or capabilities.contract_version != 1
            or type(capabilities.snapshot_contract_version) is not int
            or capabilities.snapshot_contract_version != 1):
        raise TransportUnavailable('unsupported_api_contract', capability='PH-API-RESULT')


class PatchHarborRuntime:
    """Bind a trusted Result and a new private runtime directory, without loading.

    Call ``load_api`` only when transport is explicitly requested. The Result's
    SHA must arrive through a trusted channel; a self-declared manifest hash is
    not such a channel. The supplied Result remains byte-identical. On a failed
    import the owned directory and any partially loaded modules are preserved;
    do not try to switch runtimes in that process.
    """

    def __init__(self, reference, *, trusted_source_sha256, workspace):
        if not _contract.valid_digest(trusted_source_sha256):
            raise TransportUnavailable('trusted_result_digest_required', exit_code=7)
        try:
            reference, workspace = Path(reference), Path(workspace)
        except (TypeError, ValueError) as error:
            raise TransportUnavailable('invalid_runtime_paths') from error
        if not reference.is_absolute() or not workspace.is_absolute():
            raise TransportUnavailable('absolute_runtime_paths_required')
        self._reference = reference
        self._trusted_sha256 = trusted_source_sha256
        self._workspace = workspace
        self._prepared = None
        self._api = None
        self._failed = False

    def describe(self):
        """Return the bound distribution contract, not fabricated acceptance."""
        return _contract.describe_distribution(self._trusted_sha256, loaded=self._api is not None)

    def _check_origins(self):
        """Keep foreign/partially loaded modules; never evict or repair them."""
        if self._prepared is None:
            if any(name == 'patchharbor' or name.startswith('patchharbor.')
                   for name in sys.modules):
                raise TransportUnavailable('runtime_origin_conflict', exit_code=7)
            return
        for name, module in tuple(sys.modules.items()):
            if name != 'patchharbor' and not name.startswith('patchharbor.'):
                continue
            spec = getattr(module, '__spec__', None)
            loader = getattr(spec, 'loader', None)
            prefix = str(self._prepared.path) + '/'
            if (not isinstance(loader, zipimporter)
                    or Path(loader.archive) != self._prepared.path
                    or not str(getattr(spec, 'origin', '')).startswith(prefix)
                    or not str(getattr(module, '__file__', '')).startswith(prefix)):
                self._failed = True
                raise TransportUnavailable('runtime_origin_conflict', exit_code=7)

    def load_api(self, *, required=()):
        """Use only the documented bootstrap and return ``patchharbor.api``.

        This explicitly prepares trusted library code, not project contents.
        Snapshot reads are a separate, read-only operation and never bootstrap
        a library from their input. API presence is not Result validation.
        """
        _check_request(required)
        _check_platform()
        if self._failed:
            raise TransportUnavailable('fresh_process_required')
        self._check_origins()

        bootstrap = importlib.import_module('specroad.transport._pyz_bootstrap')
        try:
            assessment = bootstrap.assess(
                self._reference, trusted_source_sha256=self._trusted_sha256)
            _check_distribution(assessment)
            if self._prepared is None:
                self._prepared = bootstrap.prepare(assessment, self._workspace)
            api = bootstrap.import_api(self._prepared)
            _check_api(api)
        except TransportUnavailable:
            self._failed = True
            raise
        except bootstrap.BootstrapUnavailable as error:
            self._failed = True
            raise TransportUnavailable('runtime_bootstrap_unavailable',
                                       cause_type=type(error).__name__) from error
        except OSError as error:
            self._failed = True
            raise TransportUnavailable('runtime_io_error', exit_code=5,
                                       cause_type=type(error).__name__) from error
        except (ValueError, ImportError) as error:
            self._failed = True
            raise TransportUnavailable('runtime_validation_failed', exit_code=7,
                                       cause_type=type(error).__name__) from error
        self._api = api
        return api

    def read_snapshot(self, result, *, expected_sha256):
        """Read complete immutable inventories through the pinned public API.

        Runtime preparation must be requested separately with ``load_api``.
        A Result supplied here cannot supply code, bootstrap, switch runtimes
        or request extraction. In particular, failed/dirty historical Results
        retain their real facts; validation is not an Apply-success assertion.
        """
        from .snapshots import read_snapshot
        if self._api is None or self._failed:
            raise TransportUnavailable('explicit_runtime_load_required')
        # Recheck the original trust binding and loaded module origins even
        # when inspecting another (possibly historical) Result as passive data.
        api = self.load_api(required=('read_result_snapshot',))
        return read_snapshot(api, result, expected_sha256=expected_sha256)
