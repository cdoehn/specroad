"""Closed serialized handoffs; native semantic and authorization gates are separate."""
from .result_schemas import _object, _nullable

SHA = {'type': 'string', 'pattern': r'^[0-9a-f]{64}(?![\s\S])'}
PASSIVE = {'approval_granted': {'const': False}, 'write_authorized': {'const': False}}


def plan_schema():
    return _object({'format_version': {'const': 'merge-publication-plan-v1'},
        'change_plan': {'type': 'object'}, 'change_plan_sha256': SHA,
        'project_writes_performed': {'const': False}, **PASSIVE})


def apply_schema():
    return _object({'format_version': {'const': 'merge-apply-command-v1'},
        'mode': {'enum': ['dry_run', 'apply']}, 'change_plan_sha256': SHA,
        'execution': _nullable({'type': 'object', 'properties': {
            'format_version': {'const': 'merge-transaction-v1'}}, 'required': ['format_version']}),
        'project_writes_performed': {'type': 'boolean'}, **PASSIVE})
