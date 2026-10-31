"""Public Result snapshots and independent SpecRoad failure classifications."""

from pathlib import Path

from ._contract import valid_digest


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


def _semantic_exit_code(facts):
    """Admission/snapshot facts take precedence over the general reason."""
    if facts['kind'] == 'admission_rejected' or facts['code'] == 'path_collision':
        return 7
    if facts['code'] == 'digest_mismatch':
        return 6
    if facts['code'] == 'unsupported_patch':
        return 2
    if facts['reason'] in ('usage_error', 'interpreter_error'):
        return 2
    if facts['reason'] in ('source_error', 'patch_package_error', 'no_valid_script'):
        return 3
    if facts['reason'] in ('state_mismatch', 'repository_busy'):
        return 6
    if facts['reason'] == 'unsupported_repository_state':
        return 7
    return 5


def _has_io_cause(error):
    """The original I/O cause wins, including in a cyclic exception chain."""
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if isinstance(error, OSError):
            return True
        error = error.__cause__
    return False


def api_failure(api, error):
    """Use documented semantic fields, never CLI numbers or error text."""
    if isinstance(error, api.PatchHarborError):
        facts = {'reason': error.reason.value, 'kind': error.error_kind.value,
                 'code': error.code.value if isinstance(error, api.ResultSnapshotError) else None}
        code = _semantic_exit_code(facts)
        if _has_io_cause(error):
            code = 5
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
        if not valid_digest(expected_sha256):
            raise ValueError('a complete expected Result SHA-256 is required')
        path = Path(result)
        if not path.is_absolute():
            raise ValueError('an absolute Result path is required')
        return api.read_result_snapshot(path, expected_sha256=expected_sha256)
    except (api.PatchHarborError, OSError, TypeError, ValueError) as error:
        raise api_failure(api, error) from error
