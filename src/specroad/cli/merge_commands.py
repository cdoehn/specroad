"""Read-only conflict inspection; stored inputs never authorize a merge."""
from pathlib import Path

from .contracts import CommandSpec, CommandClass, PreflightProfile, EffectScope, CommandProtocol
from .parameters import OptionSpec, PositionalSpec
from .results import CommandResult, FailureKind, OperationFailure


def conflict_command_schema():
    from ..merge.conflict_schema import object_schema, schema
    return object_schema({'format_version':{'const':'merge-conflicts-command-v1'},
        'source_validation':{'const':'not_revalidated'},
        'plan_sha256':{'type':'string','pattern':r'^[0-9a-f]{64}(?![\s\S])'},
        'plan':schema()})


def merge_conflicts_command(invocation):
    # Registry construction must preserve project-free bootstrap commands.
    from ..model.errors import ModelError
    from ..security import ProjectBoundary, SafetyViolation
    from ..merge.conflicts import parse_merge_conflicts
    try:
        path = Path(invocation.arguments['merge_plan']).absolute()
        bound = ProjectBoundary(path.parent)
        if bound.root != path.parent:
            raise SafetyViolation('Canonical plan parent required')
        raw = bound.read_bytes(path.name)
        plan = parse_merge_conflicts(raw)
        if bound.read_bytes(path.name) != raw:
            raise SafetyViolation('Plan changed during inspection')
        return CommandResult('merge.conflicts', result={
            'format_version':'merge-conflicts-command-v1','source_validation':'not_revalidated',
            'plan_sha256':plan.sha256,'plan':plan.data})
    except ModelError as error:
        raise OperationFailure(FailureKind.MODEL, error.reason) from error
    except SafetyViolation as error:
        raise OperationFailure(FailureKind.SECURITY, str(error)) from error


def merge_commands():
    return (CommandSpec('merge.conflicts', ('merge','conflicts'), CommandClass.READ_ONLY,
        PreflightProfile.INPUT_READ, EffectScope.NONE, handler=merge_conflicts_command,
        positionals=(PositionalSpec('merge_plan'),),
        options=(OptionSpec('--format',takes_value=True,choices=('pretty','json')),
                 OptionSpec('--quiet'),OptionSpec('--no-color')),
        protocol=CommandProtocol('merge-conflicts-command-v1', {'command_id':'merge.conflicts',
            'arguments':{'merge_plan':'/plans/merge.json'},'options':{'--format':'json'}},
            handler_exit_codes=(0,2,3,4,5,7),
            diagnostic_codes=('CORE_USAGE','CORE_MODEL','CORE_ENVIRONMENT','CORE_SECURITY'))),)
