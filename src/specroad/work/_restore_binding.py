"""Original Restore execution inputs, without live reads or recovery authority."""
from hashlib import sha256

from ..cli._restore_options import restore_request
from ..model.canonical import canonical_json_bytes
from ..recovery._execution_binding import original_active
from ..recovery._journal_selection import journal_selection
from ..recovery.values import RestorePlan, require, guarded, persisted_contract
from ._data_contract import _object, _copy, _hash


def _reference(raw):
    return {'sha256': sha256(raw).hexdigest(), 'size': len(raw)}


@guarded
@persisted_contract
def plan_values(plan, request, selection):
    """Reconstruct the native plan and original selection, never current approval."""
    require(type(plan) is RestorePlan, 'restore_work_plan_required')
    plan = RestorePlan(plan.source_bytes)
    options = restore_request(request).options
    require('--plan' in options, 'restore_work_execution_required', exit_code=2)
    data = plan.data
    require(options['--project'] == data['project_root']
            and options['--expected-target-root'] == data['expected_target_root'],
            'restore_work_request_conflict', exit_code=6)
    selected = journal_selection(plan, selection, original_active(plan))
    require('--affected-journals' in options or not selected['entries'],
            'restore_work_selection_conflict', exit_code=6)
    raw_selection = canonical_json_bytes(selected)
    metadata = {
        'actor': {'actor_type': options['--actor-type'], 'actor_id': options['--actor-id']},
        'request_id': options.get('--request-id'), 'operations_sha256': None,
        'plan_binding': {'format_version': 'work-restore-binding-v1',
            'restore_plan_sha256': data['restore_plan_sha256'],
            'plan_source': _reference(plan.source_bytes),
            'journal_selection': _reference(raw_selection)},
    }
    sources = {'project_id': data['project_id'], 'scope': ['project'], 'model_root_sha256': None}
    # Logical input names, independent of the external transport locations.
    inputs = [{'root_id': 'restore', 'path': 'plan.json', 'raw': plan.source_bytes},
              {'root_id': 'restore', 'path': 'selection.json', 'raw': raw_selection}]
    return metadata, sources, inputs


def semantic_command(command):
    """Transport locators are retained in the checkpoint, not unit identity.

    Original project/source roots remain in the unchanged plan bytes. A runtime
    relocation does not rewrite any saved argument or trusted prior checkpoint.
    """
    value = _copy(command)
    options = value['normalized_arguments']['options']
    for name in ('--plan-root', '--plan', '--selection-root', '--affected-journals'):
        options.pop(name, None)
    return value


@guarded
@persisted_contract
def read_plan(value, objects, inputs):
    from ..cli.requests import CommandRequest
    from .manifest import _bytes
    binding = value['plan_binding']
    _object(binding, ('format_version', 'restore_plan_sha256', 'plan_source', 'journal_selection'))
    require(binding['format_version'] == 'work-restore-binding-v1', 'restore_work_binding_invalid')
    _hash(binding['restore_plan_sha256'])
    plan = RestorePlan(_bytes(binding['plan_source'], objects))
    selection = _bytes(binding['journal_selection'], objects)
    request = CommandRequest(value['command_id'], **value['normalized_arguments'])
    metadata, sources, _ = plan_values(plan, request, selection)
    require(all(value[name] == item for name, item in metadata.items())
            and value['source_bindings'] == sources, 'restore_work_binding_conflict', exit_code=6)
    for reference in (binding['plan_source'], binding['journal_selection']):
        require(any({key: row[key] for key in ('sha256', 'size')} == reference for row in inputs),
                'restore_work_input_missing')
    return plan
