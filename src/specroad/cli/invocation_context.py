"""Current-call prerequisites only; no cached root, session or model service.

This prepares the existing option/metadata layer. Transaction preflights and
resource budgets are separate later plan steps, not success placeholders here.
"""

from dataclasses import replace

from .. import runtime
from .contracts import CommandUsageError, Invocation
from .options import resolve_options
from .results import FailureKind, OperationFailure


def prepare_invocation(invocation, *, cwd=None, profile_layers=(), configuration_layer=None):
    """Recompute inputs on every invocation, even inside an embedding process."""
    if not isinstance(invocation, Invocation):
        raise CommandUsageError("A parsed invocation is required")
    # A supplied Invocation is a request, never a reusable preflight certificate.
    current = replace(invocation, resolved=None)
    try:
        runtime.check_runtime()
    except runtime.UnsupportedRuntimeError as error:
        raise OperationFailure(FailureKind.ENVIRONMENT, "The current runtime is unsupported.") from error
    return replace(current, resolved=resolve_options(
        current, cwd=cwd, profile_layers=profile_layers,
        configuration_layer=configuration_layer))
