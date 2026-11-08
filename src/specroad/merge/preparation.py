"""Complete passive preparation, shared by direct and checkpointed callers.

Owned originals prove a historical observation, never current write authority.
Every phase is the existing native engine; there is no second merge algorithm.
"""
from hashlib import sha256

from ..model.canonical import canonical_json_bytes as jcs
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object as parsed
from ..migration.plan_values import b64, unb64
from .sources import MergeSources
from ._recorded import capture_sources, recorded_sources
from .inventory import build_merge_inventory, _plan_id
from .conflicts import build_merge_conflicts
from .resolutions import read_merge_resolutions
from .resolution_values import parse_resolution_plan
from .metadata import prepare_merge_metadata
from .target import prepare_merge_target

PHASES = ('inventory', 'comparison', 'metadata', 'target_validation')
FORMAT = 'merge-preparation-v1'


def require(ok, reason):
    if not ok:
        raise ModelError(reason)


def capture_preparation(sources, *, plan_id, history, plan_raw=None, expected_plan_sha256=None):
    """Seal a complete native observation and explicit original resolution bytes."""
    require(type(sources) is MergeSources, 'merge_live_sources_required')
    _plan_id(plan_id)
    require(type(history) is dict, 'merge_history_input_required')
    require((plan_raw is None) == (expected_plan_sha256 is None), 'merge_resolution_binding_required')
    if plan_raw is not None:
        require(type(plan_raw) is bytes and sha256(plan_raw).hexdigest() == expected_plan_sha256,
                'merge_preparation_plan_hash')
        plan = parse_resolution_plan(plan_raw).data
        catalogue = plan.get('catalogue', plan)
        require(catalogue['plan_id'] == plan_id, 'merge_preparation_plan_id_changed')
    for role in ('base', 'ours', 'theirs'):
        getattr(sources, role).verify_current()
    value = {'format_version': 'merge-preparation-input-v1', 'plan_id': plan_id,
        'history': parsed(jcs(history)), 'sources': capture_sources(sources),
        'plan_bytes_base64': None if plan_raw is None else b64(plan_raw),
        'plan_sha256': expected_plan_sha256}
    for role in ('base', 'ours', 'theirs'):
        getattr(sources, role).verify_current()
    return value


def phase_result(inputs, phase, previous, *, services=None):
    """Advance one native global phase; finished phases are retained as data."""
    sources = recorded_sources(inputs['sources'])
    history = inputs['history']
    if phase == 'inventory':
        return build_merge_inventory(sources, plan_id=inputs['plan_id']).data
    if phase == 'comparison':
        if inputs['plan_bytes_base64'] is None:
            raw = build_merge_conflicts(sources, plan_id=inputs['plan_id'], history=history).canonical_bytes
        else:
            raw = unb64(inputs['plan_bytes_base64'])
            require(sha256(raw).hexdigest() == inputs['plan_sha256'], 'merge_preparation_plan_hash')
            selected = read_merge_resolutions(raw, sources, history=history,
                expected_plan_sha256=sha256(jcs(parsed(raw))).hexdigest()).data
            require(selected.get('catalogue', selected)['plan_id'] == inputs['plan_id'],
                    'merge_preparation_plan_id_changed')
        return {'plan_bytes_base64': b64(raw), 'plan_sha256': sha256(raw).hexdigest()}
    selected = previous['comparison']
    raw = unb64(selected['plan_bytes_base64'])
    if phase == 'metadata':
        return prepare_merge_metadata(raw, sources, history=history,
            expected_plan_sha256=selected['plan_sha256']).data
    require(phase == 'target_validation', 'merge_preparation_phase_invalid')
    metadata = jcs(previous['metadata'])
    result = prepare_merge_target(metadata, raw, sources, history=history,
        expected_metadata_sha256=sha256(metadata).hexdigest(),
        expected_plan_sha256=selected['plan_sha256'], services=services)
    files = result.files if result.target_validated else {}
    return {'target': result.data,
        'target_files': [{'path': path, 'bytes_base64': b64(content)}
                         for path, content in sorted(files.items())],
        'changed': files != sources.ours.files if result.target_validated else None}


def outcome(results):
    require(set(results) == set(PHASES), 'merge_preparation_incomplete')
    return {'format_version': FORMAT, 'source_observation': 'sealed_snapshot',
        'inventory': results['inventory'], **results['comparison'],
        'metadata': results['metadata'], **results['target_validation'],
        'project_writes_performed': False, 'write_authorized': False, 'approval_granted': False}


def calculate(inputs, *, services=None):
    results = {}
    for phase in PHASES:
        results[phase] = phase_result(inputs, phase, results, services=services)
    return outcome(results), results


def prepare_merge(sources, *, plan_id, history, plan_raw=None, expected_plan_sha256=None, services=None):
    inputs = capture_preparation(sources, plan_id=plan_id, history=history,
        plan_raw=plan_raw, expected_plan_sha256=expected_plan_sha256)
    result, _ = calculate(inputs, services=services)
    for role in ('base', 'ours', 'theirs'):
        getattr(sources, role).verify_current()
    return result


def result_schema():
    from .conflict_schema import object_schema
    return object_schema({'format_version': {'const': FORMAT},
        'source_observation': {'const': 'sealed_snapshot'},
        'inventory': {'type': 'object'}, 'plan_bytes_base64': {'type': 'string', 'minLength': 1},
        'plan_sha256': {'type': 'string', 'pattern': r'^[0-9a-f]{64}(?![\s\S])'},
        'metadata': {'type': 'object'}, 'target': {'type': 'object'},
        'target_files': {'type': 'array', 'items': object_schema({
            'path': {'type': 'string', 'minLength': 1}, 'bytes_base64': {'type': 'string'}})},
        'changed': {'anyOf': [{'type': 'boolean'}, {'type': 'null'}]},
        **{name: {'const': False} for name in ('project_writes_performed', 'write_authorized', 'approval_granted')}})
