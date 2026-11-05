"""Closed declarative resolution formats; schemas do not grant authority."""
from .conflict_schema import object_schema, schema as conflict_schema, ROLES

FORMAT = 'merge-resolutions-v1'
INPUT_FORMAT = 'merge-resolution-inputs-v1'


def schema():
    from ..model.audit_fields import audit_definitions
    catalogue = conflict_schema()
    row = catalogue['properties']['conflicts']['items']
    sha = {'type': 'string', 'pattern': r'^[0-9a-f]{64}(?![\s\S])'}
    props = row['properties']
    value = props['values']['properties']['base']
    audit = audit_definitions()
    choice = {'anyOf': [object_schema({'kind': {'const': 'take'}, 'role': {'enum': list(ROLES)}}),
                       object_schema({'kind': {'const': 'value'}, 'value': {}})]}
    event = object_schema({'resolution_id': {'type': 'string', 'pattern': r'^MR-[0-9a-f]{64}(?![\s\S])'},
        'previous_sha256': sha, 'conflict_id': props['conflict_id'], 'choice': choice,
        'value': value, 'actor': audit['actor'], 'resolved_at': audit['utc']})
    target = object_schema({name: props[name] for name in ('conflict_id', 'identity', 'pointer')}
                          | {'value': value})
    return object_schema({'resolution_format_version': {'const': FORMAT},
        'catalogue': catalogue, 'catalogue_sha256': sha,
        'resolutions': {'type': 'array', 'items': event}, 'resolutions_sha256': sha,
        'targets': {'type': 'array', 'items': target},
        'unresolved_conflict_ids': {'type': 'array', 'items': props['conflict_id']},
        'pending_gates': {'type': 'array', 'items': {'enum': ['audited_resolution',
            'merge_metadata', 'target_validation', 'publication']}},
        'ready': {'const': False}, 'write_authorized': {'const': False}, 'approval_granted': {'const': False}})


def input_schema():
    text = {'type': 'string', 'minLength': 1}
    request = object_schema({'kind': {'enum': ['local', 'git', 'baseline', 'bundle']},
        'root': text, 'reference': {'anyOf': [text, {'type': 'null'}]}})
    return object_schema({'format_version': {'const': INPUT_FORMAT},
        'sources': object_schema({role: request for role in ROLES}), 'history': {'type': 'object'}})
