"""CLI projection of the root-creation operation and its typed failure classes."""
from ..changes.lock_values import ProjectLockError
from ..cli.results import CommandResult, FailureKind, OperationFailure
from ..model.errors import ModelError
from ..security import SafetyViolation
from ._bootstrap_io import BootstrapError


def initialize_command(invocation):
    from .initialization import initialize_project
    try:
        payload = initialize_project(invocation.arguments.get('path', '.'),
                                     cwd=invocation.resolved.working_directory)
    except BootstrapError as error:
        raise OperationFailure(FailureKind(error.exit_code), 'Project initialization did not complete.',
            details={'bootstrap': {'reason': error.reason, 'path': error.path,
                                    'mutation_possible': error.mutation_possible}}) from error
    except ProjectLockError as error:
        raise OperationFailure(FailureKind(error.exit_code), 'Bootstrap lock unavailable.',
                               details={'bootstrap': {'reason': error.reason}}) from error
    except SafetyViolation as error:
        raise OperationFailure(FailureKind.SECURITY, 'Unsafe bootstrap destination.') from error
    except ModelError as error:
        raise OperationFailure(FailureKind.MODEL, 'Invalid initialization resource.',
                               details={'bootstrap': error.diagnostic()}) from error
    return CommandResult('init', result=payload)
