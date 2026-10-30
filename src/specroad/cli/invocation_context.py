"""Current-call prerequisites only; no cached root, session or model service.

This prepares the current option/metadata layer and its read-profile transaction
gate. Resource budgets and write authority remain separate contracts.
"""

from dataclasses import dataclass, replace
from typing import Callable

from .. import runtime
from .contracts import CommandUsageError, Invocation, PreflightProfile
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
    recovery_authority: object = None
    recovery_actor: object = None
    restore_services: object = None

    def prepare(self, invocation, *, cwd=None, profile_layers=(), configuration_layer=None):
        if not isinstance(invocation, Invocation):
            raise CommandUsageError("A parsed invocation is required")
        # An old context is not a reusable preflight certificate.
        current = replace(invocation, resolved=None, recovery_authority=None, recovery_actor=None, restore_services=None)
        check = runtime.check_runtime if self.runtime_check is None else self.runtime_check
        resolve = resolve_options if self.option_resolver is None else self.option_resolver
        try:
            check()
        except runtime.UnsupportedRuntimeError as error:
            raise OperationFailure(FailureKind.ENVIRONMENT, "The current runtime is unsupported.") from error
        if self.recovery_authority is not None:
            from ..changes.recovery_values import RecoveryAuthority
            if type(self.recovery_authority) is not RecoveryAuthority:
                raise CommandUsageError('A trusted RecoveryAuthority is required')
        services = None
        # Bootstrap does not load project services merely to create defaults.
        # Explicit host inputs still receive their native type validation.
        if (self.restore_services is not None
                or current.command.preflight_for(current.options) is not PreflightProfile.BOOTSTRAP):
            from ..recovery.services import native_services
            services = native_services(self.restore_services)
        actor = None
        if self.recovery_actor is not None:
            from ..changes.authoring import normalize_authoring_actor
            actor = normalize_authoring_actor(self.recovery_actor).as_fields()
        return replace(current, recovery_authority=self.recovery_authority, recovery_actor=actor, restore_services=services, resolved=resolve(
            current, cwd=cwd, profile_layers=profile_layers,
            configuration_layer=configuration_layer))


def prepare_invocation(invocation, **context_inputs):
    """Default context builder without stored per-invocation state."""
    return InvocationContextBuilder().prepare(invocation, **context_inputs)
