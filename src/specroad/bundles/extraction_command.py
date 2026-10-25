"""Project-free CLI adapter; explicit input and a new or empty target only."""
from pathlib import Path

from ..authoring._bootstrap_io import BootstrapError
from ..changes.lock_values import ProjectLockError
from ..cli.results import CommandResult, FailureKind, OperationFailure
from ..diagnostics import Diagnostic
from ..model.errors import ModelError
from ..security import ProjectBoundary, SafetyViolation
from .errors import BundleError
from .extraction import extract_bundle


def extract_bundle_file(filename, target, *, expected_sha256=None, cwd=None):
    try:
        path = Path(filename)
        if not path.is_absolute():
            path = (Path.cwd() if cwd is None else Path(cwd)) / path
        boundary = ProjectBoundary(path.parent)
        raw = boundary.read_bytes(path.name)
        def recheck():
            if boundary.read_bytes(path.name) != raw:
                raise BundleError('bundle_input_changed', code=None, exit_code=6)
        value = extract_bundle(raw, target, expected_sha256=expected_sha256,
                               cwd=cwd, _recheck_input=recheck)
        return CommandResult('bundle.extract', result=value, project=None)
    except BundleError as error:
        kind = FailureKind(error.exit_code)
        diagnostic = Diagnostic(error.code or 'CORE_' + kind.name, 'error', 'bundle',
                                'Bundle extraction failed.', rationale=error.reason)
        return CommandResult.failed('bundle.extract', kind, diagnostics=(diagnostic,),
                                    details={'bundle_failure': error.as_dict()})
    except (BootstrapError, ProjectLockError) as error:
        raise OperationFailure(FailureKind(error.exit_code), 'Bundle extraction did not complete.',
            details={'bootstrap': {'reason': error.reason,
                'mutation_possible': getattr(error, 'mutation_possible', False)}}) from error
    except SafetyViolation as error:
        raise OperationFailure(FailureKind.SECURITY, 'Unsafe bundle extraction path.') from error
    except ModelError as error:
        raise OperationFailure(FailureKind.MODEL, 'Invalid bundle extraction input.') from error


def extract_command(invocation):
    return extract_bundle_file(invocation.arguments['file'], invocation.options['--output'],
        expected_sha256=invocation.options.get('--expected-sha256'),
        cwd=invocation.resolved.working_directory)
