"""Closed 0.3 plan projections, independently of their Markdown carrier.

These field checks are not graph, coverage, review or authoring approval.
No identifier, revision, audit stamp or absent optional proof is synthesized.
"""
import unicodedata
from .artifact_schemas import artifact_common_schema, validate_common_fields
from .artifact_types import artifact_type
from ._schema import validate_builtin
from .errors import ModelError
from .versions import PLAN_TYPES, PLAN_SCHEMA_VERSION
from .paths import validate_artifact_address


def _object(fields, required=None):
    return {'type': 'object', 'properties': fields, 'required': sorted(fields if required is None else required),
            'additionalProperties': False}


def _array(item):
    return {'type': 'array', 'items': item}


def _id(kind):
    return {'type': 'string', 'pattern': r'^[A-Z][A-Z0-9]{1,7}-' + artifact_type(kind).prefix +
            r'-[0-7][0-9A-HJKMNP-TV-Z]{25}(?![\s\S])'}


def plan_schema(kind, version=PLAN_SCHEMA_VERSION):
    if type(kind) is not str or kind not in PLAN_TYPES:
        raise ModelError('unknown_plan_type')
    schema = artifact_common_schema(kind, version)
    schema['$id'] = 'urn:specroad:schema:' + version + ':artifact-plan:' + kind
    schema['x-specroad-validation-scope'] = 'plan_projection_fields_only'
    schema['description'] = 'Typed Markdown projection; ownership and review are separate native gates.'
    fields = schema['properties']
    text = {'type': 'string'}
    relation = {'type': 'string', 'pattern': r'^REL-[0-7][0-9A-HJKMNP-TV-Z]{25}(?![\s\S])'}
    ref = _object({'plan_id': _id('implementation_plan'), 'entry_id': _id('plan_entry')})
    prerequisite = _object({**ref['properties'], 'relation_id': relation})
    requirement = {'type': 'string', 'pattern': r'^[A-Z][A-Z0-9]{1,7}-REQ-(?:[0-7][0-9A-HJKMNP-TV-Z]{25}|[0-9]{4})(?![\s\S])'}
    binding = {'requirement_id': requirement, 'requirement_revision': {'type': 'integer', 'minimum': 1},
        'requirement_context_sha256': {'type': 'string', 'pattern': r'^[0-9a-f]{64}(?![\s\S])'}}
    fields.update(display_id={'type': 'string', 'minLength': 1}, description=dict(text),
        children={**_array(_id('plan_entry')), 'uniqueItems': True}, prerequisites=_array(prerequisite))
    schema['required'] += ['display_id', 'description', 'children', 'prerequisites']
    for name in ('notes', 'acceptance_criteria'):
        fields[name] = _array(dict(text))
    fields.update(expected_scope=_object({k: _array(dict(text)) for k in
        ('components', 'modules', 'symbols', 'files')}, required=()), phase=dict(text),
        commit_refs=_array({'type': 'object'}), commit_message_template=dict(text))
    if kind == 'implementation_plan':
        fields.update(format={'const': 'plan-markdown-v1'}, scope={'type': 'object'},
            coverage_claims=_array(_object({**binding,
                'claim_id': {'type': 'string', 'pattern': r'^[0-7][0-9A-HJKMNP-TV-Z]{25}(?![\s\S])'},
                'completeness': {'const': 'full'},
                'contributors': {**_array(ref), 'minItems': 1, 'uniqueItems': True}})))
        schema['required'] += ['format', 'scope', 'coverage_claims']
    else:
        fields.update(plan_id=_id('implementation_plan'), parent_id={'anyOf': [_id('implementation_plan'), _id('plan_entry')]},
            parent_relation_id=relation, implemented={'type': 'boolean'}, required={'type': 'boolean', 'default': True},
            entry_kind={'enum': ['stage', 'step', 'commit']}, work_kind={'enum': [
                'implementation', 'test', 'refactor', 'migration', 'infrastructure', 'documentation']},
            requirement_bindings=_array(_object({**binding, 'relation_id': relation,
                'contribution': {'enum': ['partial', 'full'], 'default': 'partial'}, 'rationale': text},
                required=(*binding, 'relation_id'))))
        schema['required'] += ['plan_id', 'parent_id', 'parent_relation_id', 'implemented',
                               'entry_kind', 'work_kind', 'requirement_bindings']
    schema['additionalProperties'] = False
    return schema


def validate_plan_fields(value, *, id_prefix=None):
    validate_common_fields(value)
    validate_builtin(value, plan_schema(value['artifact_type']))
    prefix = value['id'].split('-')[0] if id_prefix is None else id_prefix
    validate_artifact_address(value['artifact_type'], value['id'], prefix)
    label = value['display_id']
    if (not label.strip() or label != unicodedata.normalize('NFC', label)
            or any(c in '[]\r\n\u2028\u2029' or unicodedata.category(c) in ('Cc', 'Cs') for c in label)):
        raise ModelError('invalid_plan_display_id', pointer='/display_id')
    if value['artifact_type'] == 'implementation_plan':
        from ..graph.scope_descriptors import ScopeDescriptor
        ScopeDescriptor(value['scope'])
    else:
        validate_artifact_address('implementation_plan', value['plan_id'], prefix)
        parent = value['parent_id']
        parent_kind = 'implementation_plan' if '-IPLAN-' in parent else 'plan_entry'
        validate_artifact_address(parent_kind, parent, prefix)
    for child in value['children']:
        validate_artifact_address('plan_entry', child, prefix)
    for ref in value['prerequisites']:
        validate_artifact_address('implementation_plan', ref['plan_id'], prefix)
        validate_artifact_address('plan_entry', ref['entry_id'], prefix)
