"""Explicit current inputs for the public adapter, never saved-path authority."""
from hashlib import sha256
from pathlib import Path

from ..model.canonical import canonical_json_bytes as jcs
from ..model.errors import ModelError
from ..security import ProjectBoundary, SafetyViolation
from ..snapshots import SourceRequest
from ..merge.sources import load_merge_sources
from ..merge.publication import plan_merge_publication
from ..migration.plan_values import unb64
from .merge_resolution import _read_file
from .results import FailureKind, OperationFailure


PUBLICATION_OPTIONS = ('--project', '--change-plan-id', '--actor-type', '--actor-id',
                       '--planned-at', '--request-id')


def required(options, *names):
    if any(name not in options for name in names):
        raise OperationFailure(FailureKind.USAGE, 'merge_explicit_options_required')


def require(ok, reason):
    if not ok:
        raise ModelError(reason)


def root_option(options):
    required(options, '--project')
    root = Path(options['--project'])
    if not root.is_absolute():
        raise OperationFailure(FailureKind.USAGE, 'merge_absolute_project_required')
    boundary = ProjectBoundary(root)
    if boundary.root != root:
        raise SafetyViolation('Canonical merge project root required')
    return boundary.root


def live_sources(options):
    required(options, '--base', '--ours', '--theirs')
    requests = [SourceRequest(options['--'+role], options.get('--'+role+'-kind', 'local'),
                              options.get('--'+role+'-ref')) for role in ('base', 'ours', 'theirs')]
    if any(not Path(request.root).is_absolute() for request in requests):
        raise OperationFailure(FailureKind.USAGE, 'merge_absolute_sources_required')
    return load_merge_sources(*requests)


def input_file(path):
    bound, name, raw = _read_file(path)
    def current():
        if bound.read_bytes(name) != raw:
            raise SafetyViolation('Merge command input changed')
    return raw, current


def from_preparation(root, document, sources, history, options, services):
    required(options, '--change-plan-id', '--actor-type', '--actor-id', '--planned-at')
    require(document['target']['target_validated'] is True, 'merge_publication_target_invalid')
    metadata, target = jcs(document['metadata']), jcs(document['target'])
    return plan_merge_publication(root, target, metadata, unb64(document['plan_bytes_base64']), sources,
        history=history, expected_plan_sha256=document['plan_sha256'],
        expected_metadata_sha256=sha256(metadata).hexdigest(), expected_target_sha256=sha256(target).hexdigest(),
        change_plan_id=options['--change-plan-id'], planned_at=options['--planned-at'],
        actor={'actor_type': options['--actor-type'], 'actor_id': options['--actor-id']},
        request_id=options.get('--request-id'), services=services)


def revalidate(root, plan, sources, services):
    """Same native producer and complete gates, including original source bytes."""
    value = plan.data
    inputs = value['operations'][0]['inputs']
    rebuilt = plan_merge_publication(root, unb64(inputs['target_bytes_base64']),
        unb64(inputs['metadata_bytes_base64']), unb64(inputs['plan_bytes_base64']), sources,
        history=inputs['history'], expected_target_sha256=inputs['target_sha256'],
        expected_metadata_sha256=inputs['metadata_sha256'], expected_plan_sha256=inputs['plan_sha256'],
        **{key: value[key] for key in ('change_plan_id', 'actor', 'planned_at', 'request_id')}, services=services)
    require(rebuilt.canonical_bytes == plan.canonical_bytes, 'merge_publication_plan_recomputation')


def command_error(error):
    code = (7 if isinstance(error, SafetyViolation) else 5 if isinstance(error, OSError)
            else getattr(error, 'exit_code', 3))
    reason = getattr(error, 'reason', 'merge_publication_io_failure')
    details = {'reason': reason}
    if hasattr(error, 'write_state'):
        details['write_state'] = error.write_state
    return OperationFailure(FailureKind(code), reason, details=details)
