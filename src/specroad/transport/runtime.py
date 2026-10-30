"""Explicit, lazy access to the pinned public PatchHarbor API.

The bootstrap is the unchanged reviewed helper delivered with PatchHarbor 1.4.0.
Its descriptor precheck is deliberately not a full Result/snapshot validator.
No registration, Git action, installer, subprocess or transport is started here.
The returned API grants no proposal, review or automatic host-apply authority.
"""

import importlib
from pathlib import Path
import platform
import re
import sys


_VERSION = '1.4.0'
_ARTIFACT_SHA256 = '4e0d26997bffe9476e79d98211cef2d93be7899063a0eb3480bea2ffa3d8f594'
_PYTHONS = ((3, 10), (3, 11), (3, 12), (3, 13), (3, 14))
_OPERATIONS = ('bundle', 'inspect_patch', 'validate_patch', 'pack_patch', 'apply')
# A requirement identifier, not an invented public PatchHarbor function name.
_RESULT_REQUIREMENT = 'PH-API-RESULT'


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


class PatchHarborRuntime:
    """Bind a trusted Result and a new private runtime directory, without loading.

    Call ``load_api`` only when transport is explicitly requested. The Result's
    SHA must arrive through a trusted channel; a self-declared manifest hash is
    not such a channel. The supplied Result remains byte-identical. On a failed
    import the owned directory and any partially loaded modules are preserved;
    do not try to switch runtimes in that process.
    """

    def __init__(self, reference, *, trusted_source_sha256, workspace):
        if (type(trusted_source_sha256) is not str
                or re.fullmatch(r'[0-9a-f]{64}', trusted_source_sha256) is None):
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
        return {
            'distribution': 'patchharbor', 'version': _VERSION,
            'artifact_sha256': _ARTIFACT_SHA256,
            'profile': 'patchharbor-core-no-watcher-v1',
            'runtime_profile': 'python-present', 'requires_python': '>=3.10',
            'supported_cpython': ['%d.%d' % pair for pair in _PYTHONS],
            'platform_profiles': ['linux-x86_64'],
            'source_result_sha256': self._trusted_sha256,
            'api_capabilities': {name: True for name in _OPERATIONS},
            'unavailable_capabilities': [_RESULT_REQUIREMENT],
            'runtime_loaded': self._api is not None,
            'capability_scope': 'pinned_distribution_contract',
            'full_reference_valid': False,
        }

    def load_api(self, *, required=()):
        """Use only the documented bootstrap and return ``patchharbor.api``.

        ``PH-API-RESULT`` always refuses before loading or materializing code:
        the pinned distribution has no public full Result/snapshot operation.
        Ordinary API presence must not be confused with that missing contract.
        """
        if (type(required) is not tuple
                or any(type(name) is not str for name in required)):
            raise TransportUnavailable('invalid_capability_request')
        for name in required:
            if name not in _OPERATIONS:
                raise TransportUnavailable('api_capability_unavailable', capability=name)
        if (sys.implementation.name != 'cpython'
                or sys.version_info[:2] not in _PYTHONS):
            raise TransportUnavailable('unsupported_transport_python')
        if sys.platform != 'linux' or platform.machine() != 'x86_64':
            raise TransportUnavailable('unsupported_transport_platform')
        if self._failed:
            raise TransportUnavailable('fresh_process_required')
        if self._prepared is None and any(
                name == 'patchharbor' or name.startswith('patchharbor.')
                for name in sys.modules):
            raise TransportUnavailable('runtime_origin_conflict', exit_code=7)

        bootstrap = importlib.import_module('specroad.transport._pyz_bootstrap')
        try:
            assessment = bootstrap.assess(
                self._reference, trusted_source_sha256=self._trusted_sha256)
            if (assessment.version != _VERSION
                    or assessment.artifact_sha256 != _ARTIFACT_SHA256
                    or assessment.requires_python != '>=3.10'):
                raise TransportUnavailable('unsupported_runtime_distribution', exit_code=7)
            if self._prepared is None:
                self._prepared = bootstrap.prepare(assessment, self._workspace)
            api = bootstrap.import_api(self._prepared)
            for name in _OPERATIONS:
                if not callable(getattr(api, name, None)):
                    raise TransportUnavailable('api_capability_unavailable', capability=name)
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
