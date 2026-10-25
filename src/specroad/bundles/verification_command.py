"""Project-free, read-only file adapter for the owned-byte bundle verifier."""
from pathlib import Path

from ..cli.result_schemas import validate_result_document
from ..cli.results import CommandResult, FailureKind, OperationFailure
from ..diagnostics import Diagnostic
from ..model.errors import ModelError
from ..query._read_errors import read_details, read_failure
from ..query.read_work import complete_read_steps
from ..security import ProjectBoundary, SafetyViolation
from ..srx.errors import SrxError
from .errors import BundleError
from .verification import verify_bundle


def _steps(filename, *, expected_sha256=None, cwd=None):
    details = read_details()
    try:
        path = Path(filename)
        if not path.is_absolute():
            path = (Path.cwd() if cwd is None else Path(cwd)) / path
        boundary = ProjectBoundary(path.parent)
        raw = boundary.read_bytes(path.name)
        yield 'loaded'
        result = verify_bundle(raw, expected_sha256=expected_sha256)
        yield 'evaluated'
        if boundary.read_bytes(path.name) != raw:
            raise BundleError('bundle_input_changed', code=None, exit_code=6)
        validate_result_document('bundle-verify-v1', result)
        return CommandResult('bundle.verify', result=result, project=None,
                             details={**details, 'source_bytes_rechecked': True})
    except BundleError as error:
        kind = FailureKind(error.exit_code)
        diagnostic = Diagnostic(error.code or 'CORE_' + kind.name, 'error', 'bundle',
                                'Bundle verification failed.', rationale=error.reason)
        return CommandResult.failed('bundle.verify', kind, diagnostics=(diagnostic,),
                                    details={**details, 'bundle_failure': error.as_dict()})
    except (OperationFailure, ModelError, SafetyViolation, SrxError, OSError) as error:
        return read_failure('bundle.verify', error, None, details)


def verify_bundle_file(filename, *, expected_sha256=None):
    """Read only the explicit input, recheck it, and return a complete result."""
    return complete_read_steps(_steps(filename, expected_sha256=expected_sha256))


def verify_command(invocation):
    return complete_read_steps(_steps(invocation.arguments['file'],
        expected_sha256=invocation.options.get('--expected-sha256'),
        cwd=invocation.resolved.working_directory), call=invocation.consumption_call)
