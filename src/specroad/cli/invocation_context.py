"""Current-call prerequisites only; no cached root, session or model service.

This prepares the existing option/metadata layer. Transaction preflights and
resource budgets are separate later plan steps, not success placeholders here.
"""

from dataclasses import dataclass, replace
from typing import Callable

from .. import runtime
from .contracts import CommandUsageError, Invocation
from .options import resolve_options
from .results import FailureKind, OperationFailure


@dataclass(frozen=True)
class InvocationContextBuilder:
    """Trusted dependencies, separate from the command registry's handlers.

    Injection is a Python embedding seam, never controlled by project data.
    Neither this builder nor its default services retain a selected root.
    """
    runtime_check: Callable | None = None
    option_resolver: Callable | None = None

    def prepare(self, invocation, *, cwd=None, profile_layers=(), configuration_layer=None):
        if not isinstance(invocation, Invocation):
            raise CommandUsageError("A parsed invocation is required")
        # An old context is not a reusable preflight certificate.
        current = replace(invocation, resolved=None)
        check = runtime.check_runtime if self.runtime_check is None else self.runtime_check
        resolve = resolve_options if self.option_resolver is None else self.option_resolver
        try:
            check()
        except runtime.UnsupportedRuntimeError as error:
            raise OperationFailure(FailureKind.ENVIRONMENT, "The current runtime is unsupported.") from error
        return replace(current, resolved=resolve(
            current, cwd=cwd, profile_layers=profile_layers,
            configuration_layer=configuration_layer))


def prepare_invocation(invocation, **context_inputs):
    """Default context builder without stored per-invocation state."""
    return InvocationContextBuilder().prepare(invocation, **context_inputs)
