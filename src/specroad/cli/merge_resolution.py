"""Native plan-only conflict resolution; imported only after command dispatch."""
from pathlib import Path

from ..bundles.errors import BundleError
from ..srx.errors import SrxError
from ..merge.resolution_schema import input_schema
from ..merge.resolutions import resolve_merge_conflict, parse_resolution_value, _prepare_resolution
from ..merge.sources import SourceRequest, load_merge_sources
from ..model._schema import validate_builtin
from ..model.errors import ModelError
from ..security import ProjectBoundary, SafetyViolation
from ..storage.json_syntax import parse_json_object
from .results import CommandResult, FailureKind, OperationFailure


def _read_file(value):
    path = Path(value).absolute()
    boundary = ProjectBoundary(path.parent)
    if boundary.root != path.parent:
        raise SafetyViolation('Canonical input parent required')
    return boundary, path.name, boundary.read_bytes(path.name)


def resolve_command(invocation):
    options = invocation.options
    try:
        if ('--take' in options) == ('--value' in options):
            raise OperationFailure(FailureKind.USAGE, 'Choose exactly one of take or value')
        decision = ({'take': options['--take']} if '--take' in options else
                    {'value': parse_resolution_value(options['--value'].encode('utf-8'))})
        plan_file = _read_file(invocation.arguments['merge_plan'])
        audit = {'actor': {'actor_type': options['--actor-type'], 'actor_id': options['--actor-id']},
                 'resolved_at': options['--resolved-at']}
        selection = {'expected_plan_sha256': options['--expected-plan-sha256'],
                     'conflict_id': options['--conflict'], **audit, **decision}
        # A bad plan/decision cannot cause access to otherwise irrelevant input paths.
        _prepare_resolution(plan_file[2], **selection)
        inputs_file = _read_file(options['--inputs'])
        inputs = parse_json_object(inputs_file[2])
        validate_builtin(inputs, input_schema())
        requests = []
        for role in ('base', 'ours', 'theirs'):
            item = inputs['sources'][role]
            if not Path(item['root']).is_absolute():
                raise ModelError('merge_source_absolute_root_required')
            requests.append(SourceRequest(**item))
        sources = load_merge_sources(*requests)
        plan = resolve_merge_conflict(plan_file[2], sources, history=inputs['history'], **selection)
        for boundary, name, raw in (plan_file, inputs_file):
            if boundary.read_bytes(name) != raw:
                raise SafetyViolation('Resolution input changed during reading')
        for source in (sources.base, sources.ours, sources.theirs):
            source.verify_current()
        return CommandResult('merge.resolve', result={'format_version': 'merge-resolve-command-v1',
            'source_validation': 'revalidated', 'plan_sha256': plan.sha256, 'plan': plan.data})
    except BundleError as error:
        raise OperationFailure(FailureKind(error.exit_code), error.reason) from error
    except (ModelError, SrxError) as error:
        raise OperationFailure(FailureKind.MODEL, error.reason) from error
    except SafetyViolation as error:
        raise OperationFailure(FailureKind.SECURITY, str(error)) from error
