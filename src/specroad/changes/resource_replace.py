"""An explicitly named byte replacement; no inferred repair or replay program."""
import base64
import binascii
from hashlib import sha256
from ..force import ForceRequest, operations_hash
from ..model.canonical import canonical_json_sha256 as digest
from ..model.paths import project_path
from ._schema_fields import obj, text
from .errors import ChangePlanError


def operation_schema():
    return obj({'op': {'const': 'resource_replace'}, 'path': text(),
        'observed_byte_sha256': {'anyOf': [{'const': 'absent'},
            {'type': 'string', 'pattern': r'^[0-9a-f]{64}(?![\s\S])'}]},
        'target': {'anyOf': [obj({'bytes_base64': {'type': 'string'}}), obj({'delete': {'const': True}})]},
        'reason': text(), 'force': obj({'requested': {'const': True},
            'reason': {'anyOf': [text(), {'type': 'null'}]}})})


def target_bytes(operation):
    target = operation['target']
    if 'delete' in target:
        return None
    try:
        raw = base64.b64decode(target['bytes_base64'], validate=True)
        if base64.b64encode(raw).decode('ascii') != target['bytes_base64']:
            raise ValueError('noncanonical')
        return raw
    except (TypeError, ValueError, binascii.Error) as error:
        raise ChangePlanError('resource_replace_base64_required') from error


def validate_operation(value, pointer=''):
    from ..model._schema import validate_builtin
    validate_builtin(value, operation_schema())
    project_path(value['path'])
    ForceRequest.from_mapping(value['force'])
    target_bytes(value)


def check_plan(value):
    raw = any(op['op'] == 'resource_replace' for op in value['operations'])
    if not raw:
        return False
    if (value['format_version'] != '1.3.0' or 'force' not in value
            or not ForceRequest.from_mapping(value['force']).requested
            or any(op['op'] != 'resource_replace' for op in value['operations'])
            or value['result_artifacts'] or value['preconditions']):
        raise ChangePlanError('resource_replace_explicit_plan_required')
    paths = [op['path'] for op in value['operations']]
    if len(paths) != len(set(paths)):
        raise ChangePlanError('resource_replace_duplicate_target')
    if any(op['force'] != value['force'] for op in value['operations']):
        raise ChangePlanError('resource_replace_force_binding')
    return True


def prepare_resource_plan(*, operations, project_id, actor, request_id, planned_at,
                          change_plan_id, base_model_root=None, target_model_root=None,
                          force=False, reason=None):
    """Build passive complete intent. No filesystem observation or authority."""
    from .core import prepare_change_plan
    from .target_model import _default_scope
    request = ForceRequest(force, reason)
    return prepare_change_plan({'format_version': '1.3.0', 'metadata_policy_version': 'change-metadata-v1',
        'change_plan_id': change_plan_id, 'request_id': request_id, 'planned_at': planned_at,
        'actor': actor, 'force': request.data, 'project_id': project_id,
        'base': {'scope_descriptor': _default_scope(), 'model_root_sha256': base_model_root},
        'operations': operations, 'preconditions': [], 'result_artifacts': [],
        'expected_result': {'model_root_sha256': target_model_root}})
