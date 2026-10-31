"""Public Result snapshots and independent SpecRoad failure classifications."""

from pathlib import Path
import re


class TransportFailure(ValueError):
    """A failed API operation, preserving upstream facts without numeric reuse."""

    def __init__(self, exit_code, *, reason, patchharbor=None, cause_type=None):
        super().__init__(reason)
        self.exit_code = exit_code
        self.reason = reason
        self.patchharbor = patchharbor
        self.cause_type = cause_type

    def as_dict(self):
        return {'status': 'failed', 'exit_code': self.exit_code,
                'reason': self.reason, 'patchharbor': self.patchharbor,
                'cause_type': self.cause_type, 'full_reference_valid': False}


def api_failure(api, error):
    """Use documented semantic fields, never CLI numbers or error text."""
    if isinstance(error, api.PatchHarborError):
        facts = {'reason': error.reason.value, 'kind': error.error_kind.value,
                 'code': error.code.value if isinstance(error, api.ResultSnapshotError) else None}
        code = 5
        if facts['reason'] in ('usage_error', 'interpreter_error'):
            code = 2
        elif facts['reason'] in ('source_error', 'patch_package_error', 'no_valid_script'):
            code = 3
        elif facts['reason'] in ('state_mismatch', 'repository_busy'):
            code = 6
        elif facts['reason'] == 'unsupported_repository_state':
            code = 7
        if facts['kind'] == 'admission_rejected' or facts['code'] == 'path_collision':
            code = 7
        elif facts['code'] == 'digest_mismatch':
            code = 6
        elif facts['code'] == 'unsupported_patch':
            code = 2
        cause = error
        seen = set()
        while cause is not None and id(cause) not in seen:
            seen.add(id(cause))
            if isinstance(cause, OSError):
                code = 5
                break
            cause = cause.__cause__
        return TransportFailure(code, reason='patchharbor_operation_failed',
                                patchharbor=facts, cause_type=type(error).__name__)
    if isinstance(error, OSError):
        return TransportFailure(5, reason='transport_io_error', cause_type=type(error).__name__)
    if isinstance(error, (TypeError, ValueError)):
        return TransportFailure(2, reason='invalid_api_arguments', cause_type=type(error).__name__)
    raise error


def read_snapshot(api, result, *, expected_sha256):
    """Delegate capture, validation and all five layers to the public API."""
    try:
        if (type(expected_sha256) is not str
                or re.fullmatch(r'[0-9a-f]{64}', expected_sha256) is None):
            raise ValueError('a complete expected Result SHA-256 is required')
        path = Path(result)
        if not path.is_absolute():
            raise ValueError('an absolute Result path is required')
        return api.read_result_snapshot(path, expected_sha256=expected_sha256)
    except (api.PatchHarborError, OSError, TypeError, ValueError) as error:
        raise api_failure(api, error) from error
