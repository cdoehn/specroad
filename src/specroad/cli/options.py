"""Command-specific global options and the thin input-resolution adapter."""

from pathlib import Path

from .contracts import CommandUsageError, Invocation, OptionSpec, PreflightProfile
from .option_values import (
    CORE_PROFILE, OptionLayer, OptionOrigin, OptionResolutionError,
    ResolvedOptions, _compose_values, _validate_layers, policy_exit_code,
)
from .project_selection import select_project


_GLOBAL_OPTIONS = {
    "--project": OptionSpec("--project", takes_value=True),
    "--profile": OptionSpec("--profile", takes_value=True, repeatable=True),
    "--configuration": OptionSpec("--configuration", takes_value=True),
    "--fail-on": OptionSpec("--fail-on", takes_value=True, choices=("error", "warning")),
    "--strict": OptionSpec("--strict"),
}


def global_options(*flags: str) -> tuple[OptionSpec, ...]:
    """Opt in per command; there is no universally accepted option catch-all."""
    try:
        return tuple(_GLOBAL_OPTIONS[flag] for flag in flags)
    except KeyError as error:
        raise CommandUsageError("Global option is not implemented") from error


def check_global_contract(command) -> None:
    """A recognized global flag must keep its shared parsing semantics."""
    for option in command.options:
        expected = _GLOBAL_OPTIONS.get(option.flag)
        if expected is None:
            continue
        if (option.takes_value, option.repeatable, option.choices) != (expected.takes_value, expected.repeatable, expected.choices):
            raise CommandUsageError("Command redefines a global option")
    if command.preflight_profile is PreflightProfile.BOOTSTRAP and any(option.flag == "--project" for option in command.options):
        raise CommandUsageError("Bootstrap contract must not select a project")


def resolve_options(invocation: Invocation, *, cwd: Path | None = None,
                    profile_layers: tuple[OptionLayer, ...] = (),
                    configuration_layer: OptionLayer | None = None) -> ResolvedOptions:
    check_global_contract(invocation.command)
    _validate_layers(profile_layers, configuration_layer)
    root, source, project = select_project(invocation.command, invocation.options, cwd)
    values, history = _compose_values(project, invocation.options, profile_layers, configuration_layer)
    return ResolvedOptions(root, source, values, history)
