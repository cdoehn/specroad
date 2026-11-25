"""Command-specific global options and the thin input-resolution adapter."""

from pathlib import Path

from .contracts import CommandUsageError, Invocation, OptionSpec, PreflightProfile
from .option_values import (
    CORE_PROFILE, OptionLayer, OptionOrigin, OptionResolutionError,
    ResolvedOptions, _compose_values, _validate_layers, policy_exit_code,
)

def select_project(command, options, cwd, *, preflight=None):
    """Do not import project I/O for a contract which does not select a root."""
    if command.preflight_for(options) is PreflightProfile.BOOTSTRAP:
        if "--project" in options:
            raise OptionResolutionError("Bootstrap does not select a project")
        return None, None, {}
    if not command.requires_project and "--project" not in options:
        return None, None, {}
    if command.command_id == 'change.apply' and options.get('--force') is True:
        from ..security import ProjectBoundary
        root = Path(options.get('--project', Path.cwd() if cwd is None else cwd))
        if not root.is_absolute():
            root = (Path.cwd() if cwd is None else Path(cwd)) / root
        boundary = ProjectBoundary(root)
        if preflight is not None:
            preflight.update({'force_raw_selection': True, 'model_validated': False})
        return boundary.root, 'explicit' if '--project' in options else 'cwd', {}
    from .project_selection import select_project as select
    return select(command, options, cwd, preflight=preflight)


_GLOBAL_OPTIONS = {
    "--force": OptionSpec("--force"),
    "--force-reason": OptionSpec("--force-reason", takes_value=True),
    "--force-owner": OptionSpec("--force-owner", takes_value=True, repeatable=True),
    "--project": OptionSpec("--project", takes_value=True),
    "--profile": OptionSpec("--profile", takes_value=True, repeatable=True),
    "--configuration": OptionSpec("--configuration", takes_value=True),
    "--fail-on": OptionSpec("--fail-on", takes_value=True, choices=("error", "warning")),
    "--strict": OptionSpec("--strict"),
    "--no-color": OptionSpec("--no-color"),
    "--quiet": OptionSpec("--quiet"),
    "--metrics": OptionSpec("--metrics"),
    "--format": OptionSpec("--format", takes_value=True, choices=("pretty", "json", "sarif")),
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
        if option.flag == "--format":
            if not option.takes_value or option.repeatable or not option.choices or not set(option.choices) <= set(expected.choices):
                raise CommandUsageError("Command redefines supported result formats")
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
    preflight = {}
    root, source, project = select_project(invocation.command, invocation.options, cwd, preflight=preflight)
    explicit = invocation.options
    if invocation.command.command_class.value == 'transport_operational':
        explicit = {k: v for k, v in explicit.items() if k != '--profile'}
        preflight['command_class'] = 'transport_operational'
    if invocation.command.protocol is not None and invocation.command.protocol.result_schema in (
            'ai-runtime-verify-v1', 'ai-runtime-extract-v1'):
        explicit = {k: v for k, v in explicit.items() if k != '--profile'}
    values, history = _compose_values(project, explicit, profile_layers, configuration_layer)
    origin = None
    if (invocation.command.preflight_for(invocation.options) in (PreflightProfile.ROOT_CREATION, PreflightProfile.INPUT_READ)
            or invocation.command.command_id.startswith(('analyzer.', 'plan.', 'artifact.', 'relation.', 'lifecycle.', 'document.', 'section.', 'block.', 'view.', 'baseline.', 'evidence.'))
            or invocation.command.command_id in ('query', 'diff', 'export', 'change.apply', 'proposal.validate', 'proposal.check',
                                                 'proposal.review.start', 'proposal.review', 'proposal.apply')):
        origin = Path.cwd() if cwd is None else Path(cwd)
    return ResolvedOptions(root, source, values, history, preflight or None, origin)
