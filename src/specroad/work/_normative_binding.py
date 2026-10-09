"""Inert original ChangePlan binding; no writer authorization or execution."""

from hashlib import sha256

from ..changes.authoring import bind_plan_authoring
from ..changes.values import ChangePlan
from ._data_contract import _require, _object, _hash, _count


def plan_values(plan):
    _require(type(plan) is ChangePlan)
    plan = ChangePlan(plan.source_bytes)
    authoring = bind_plan_authoring(plan).data
    _require(authoring['request_id'] is not None)
    raw, data = plan.source_bytes, plan.data
    digest = sha256(raw).hexdigest()
    return {'actor': authoring['actor'], 'request_id': authoring['request_id'],
            'operations_sha256': authoring['operation_sequence_sha256'],
            'plan_binding': {'format_version': 'work-change-plan-v1',
                'change_plan_id': data['change_plan_id'], 'change_plan_sha256': plan.sha256,
                'source': {'sha256': digest, 'size': len(raw)}}}, {digest: raw}


def read_plan(value, objects):
    """Require every saved authoring/plan field to describe the original bytes."""
    binding = value['plan_binding']
    _object(binding, ('format_version', 'change_plan_id', 'change_plan_sha256', 'source'))
    _require(binding['format_version'] == 'work-change-plan-v1')
    reference = binding['source']
    _object(reference, ('sha256', 'size')); _hash(reference['sha256']); _count(reference['size'])
    raw = objects.get(reference['sha256'])
    _require(type(raw) is bytes and len(raw) == reference['size']
             and sha256(raw).hexdigest() == reference['sha256'])
    plan = ChangePlan(raw)
    expected, _ = plan_values(plan)
    _require(all(value[name] == item for name, item in expected.items()))
    _require(value['command_id'] == 'change.apply' and value['command_class'] == 'normative_write')
    actor = expected['actor']
    _require(value['normalized_arguments'] == {'arguments': {}, 'options': {
        '--actor-type': actor['actor_type'], '--actor-id': actor['actor_id'],
        '--request-id': expected['request_id']}})
    _require(value['source_bindings']['project_id'] is not None
             and value['source_bindings']['scope'] == ['project']
             and value['source_bindings']['model_root_sha256'] == plan.data['base']['model_root_sha256'])
    return plan
