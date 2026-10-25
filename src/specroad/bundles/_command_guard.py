"""The explicit partial command allowlist, independent of handler authority."""
from ..cli.results import FailureKind, OperationFailure
from ..cli.registry import PreflightProfile
from ..security import ProjectBoundary, SafetyViolation
from ._extracted_root import has_extracted_metadata, require_complete_root
from ._read_context import PartialReadContext


def require_partial_command(invocation):
    require_partial_command_at(invocation.resolved.project_root, invocation.command, invocation.options)


def require_partial_command_at(root, command, options):
    """Refuse disallowed partial commands before normal operational preflight."""
    if root is None or command.preflight_profile is PreflightProfile.BOOTSTRAP:
        return
    if PartialReadContext.allows(command, options):
        return
    try:
        boundary = ProjectBoundary(root)
        if has_extracted_metadata(boundary):
            require_complete_root(boundary)
    except SafetyViolation as error:
        raise OperationFailure(FailureKind.SECURITY, 'This operation requires a complete project.') from error
