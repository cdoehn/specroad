"""Early Proposal scope checks shared by argv and structured invocations.

This is the basis part of the Proposal command contract, not a command
registration or a replacement for later authoring, review and writer gates.
"""
from pathlib import Path

from ..model.errors import ModelError
from ..proposals.scope import require_proposal_scope
from ..security import ProjectBoundary, SafetyViolation
from ..storage.json_syntax import parse_json_object
from .results import FailureKind, OperationFailure


def check_proposal_basis_options(invocation, *, cwd=None):
    """Reject invalid selection before project preflight or a command handler.

    A scope file is an explicit data input. It cannot redirect project access,
    supply a trusted hash, select a variant or silently become stdin.
    """
    if not (invocation.command.command_id.startswith('proposal.')
            and invocation.command.words[0] == 'proposal'):
        return
    options = invocation.options
    if '--configuration' in options:
        raise OperationFailure(FailureKind.USAGE, 'proposal_configuration_forbidden')
    if '--base-scope' not in options:
        return
    value = options['--base-scope']
    if value == '-':
        raise OperationFailure(FailureKind.USAGE, 'proposal_base_scope_file_required')
    path = Path(value)
    if not path.is_absolute():
        path = (Path.cwd() if cwd is None else Path(cwd)) / path
    path = path.absolute()
    try:
        boundary = ProjectBoundary(path.parent)
        if boundary.root != path.parent:
            raise SafetyViolation('Canonical Proposal scope input parent required')
        raw = boundary.read_bytes(path.name)
        require_proposal_scope(parse_json_object(raw), exit_code=2)
        if boundary.read_bytes(path.name) != raw:
            raise OperationFailure(FailureKind.CONFLICT, 'proposal_scope_input_changed')
    except ModelError as error:
        raise OperationFailure(FailureKind(getattr(error, 'exit_code', 3)), error.reason,
                               details={'model_failure': error.diagnostic()}) from error
    except SafetyViolation as error:
        raise OperationFailure(FailureKind.SECURITY, 'proposal_scope_input_unsafe') from error


def proposal_basis_failure(command_id, error):
    """Preserve the native dependency diagnostic for Proposal command adapters."""
    from ..diagnostics import from_model_error
    from .results import CommandResult
    if not isinstance(error, ModelError):
        raise TypeError('A native model error is required')
    return CommandResult.failed(command_id, FailureKind(getattr(error, 'exit_code', 3)),
        diagnostics=(from_model_error(error, code=getattr(error, 'code', None)),),
        details={'model_failure': error.diagnostic(), 'write_authorized': False})
