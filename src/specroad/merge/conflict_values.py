"""Owned stored conflict values; no CLI, paths, source opening or presentation."""
from dataclasses import dataclass
from hashlib import sha256
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..model.errors import ModelError
from ..model._schema import validate_builtin
from ..storage.json_syntax import parse_json_object as parsed
from .inventory import _plan_id
from .conflict_schema import ROLES, FIELD_CLASSES, BINARY_CLASSES, GUARD_CLASSES, schema


@dataclass(frozen=True, init=False)
class MergeConflicts:
    _encoded: bytes

    @classmethod
    def _create(cls, value):
        result = object.__new__(cls)
        object.__setattr__(result, '_encoded', jcs(value))
        return result

    @property
    def data(self):
        return parsed(self._encoded)

    @property
    def canonical_bytes(self):
        return self._encoded

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    @property
    def conflicts(self):
        return self.data['conflicts']

    def conflict(self, conflict_id):
        for row in self.conflicts:
            if row['conflict_id'] == conflict_id:
                return row
        raise ModelError('unknown_merge_conflict')

    @property
    def ready(self):
        return False

    @property
    def write_authorized(self):
        return False

    def __bool__(self):
        raise TypeError('A conflict catalogue is not merge or write authority')



def _identifier(document, row):
    return 'MC-' + digest({**{name:document[name] for name in ('conflict_format_version',
        'plan_id','source_bindings_sha256','history_input_sha256')},
        **{name:row[name] for name in ('identity','pointer','conflict_class','element_keys')}})



def _allowed(row, blocked):
    if jcs(row['identity']) in blocked:
        return []
    kind = row['conflict_class']
    if kind not in FIELD_CLASSES+BINARY_CLASSES:
        return []
    choices = ['take_'+role for role in ('ours','theirs','base') if row['values'][role]['state']=='present']
    if kind in FIELD_CLASSES:
        choices.append('value')
    return choices



def _stored_consistency(row):
    """Reject contradictory passive observations without claiming source truth."""
    identity = row['identity']
    versioned = identity['kind'] in ('profile','rule','mapping','language_registry','language_package')
    if versioned != (identity['version'] is not None):
        raise ModelError('merge_conflict_resource_version')
    expected_artifacts = ([identity['id']] if identity['kind']=='artifact' else sorted({
        obs['owner_id'] for obs in row['observations'].values() if obs['owner_id'] is not None}))
    if row['artifact_ids'] != expected_artifacts:
        raise ModelError('merge_conflict_artifact_binding')
    for role in ROLES:
        observation, value = row['observations'][role], row['values'][role]
        if observation['state']=='absent' and value['state']!='absent':
            raise ModelError('merge_conflict_absent_source')
        if observation['state']=='present':
            if (identity['kind']=='relation') != (observation['owner_id'] is not None):
                raise ModelError('merge_conflict_owner_binding')
            if not row['pointer'] and value['state']!='present':
                raise ModelError('merge_conflict_absent_resource')
        if value['state']=='present':
            if row['conflict_class'] in FIELD_CLASSES and value['domain']!='json-v1':
                raise ModelError('merge_conflict_field_domain')
            if row['conflict_class'] in BINARY_CLASSES and value['domain']!='bytes-v1':
                raise ModelError('merge_conflict_binary_domain')
            if value['domain']=='bytes-v1' and (row['pointer'] or value['sha256']!=observation['byte_sha256']
                    or value['size']!=observation['size']):
                raise ModelError('merge_conflict_byte_binding')
            if value['domain']=='json-v1' and not row['pointer']:
                original = value['value']
                if identity['kind']=='relation':
                    if (type(original) is not dict or set(original)!={'owner_id','relation'}
                            or original['owner_id']!=observation['owner_id']):
                        raise ModelError('merge_conflict_relation_value')
                    original = original['relation']
                if digest(original)!=observation['value_sha256']:
                    raise ModelError('merge_conflict_value_binding')
        impact = row['impact']['by_role'][role]
        if len({edge['relation_id'] for edge in impact})!=len(impact):
            raise ModelError('merge_conflict_impact_identity')
    keys = row['element_keys']
    if (row['conflict_class']=='set_element_conflict') != bool(keys) or any(type(key) in (dict,list) for key in keys):
        raise ModelError('merge_conflict_collection_keys')
    if row['conflict_class'] in GUARD_CLASSES+BINARY_CLASSES and row['pointer']:
        raise ModelError('merge_conflict_resource_pointer')



def parse_merge_conflicts(raw):
    """Inspect stored observations only; never open their claimed source paths."""
    if type(raw) is not bytes:
        raise ModelError('merge_conflicts_bytes_required')
    document = parsed(raw)
    validate_builtin(document, schema())
    _plan_id(document['plan_id'])
    if document['source_bindings_sha256'] != digest(document['source_bindings']):
        raise ModelError('merge_conflicts_source_hash')
    rows = document['conflicts']
    if document['conflicts_sha256'] != digest(rows):
        raise ModelError('merge_conflicts_list_hash')
    ids = [row['conflict_id'] for row in rows]
    if ids != sorted(set(ids)):
        raise ModelError('merge_conflicts_order')
    blocked = {jcs(row['identity']) for row in rows if row['conflict_class'] in GUARD_CLASSES}
    for row in rows:
        _stored_consistency(row)
        if row['conflict_id'] != _identifier(document, row):
            raise ModelError('merge_conflict_identity')
        if row['artifact_ids'] != sorted(set(row['artifact_ids'])):
            raise ModelError('merge_conflict_artifacts')
        keys = [jcs(value) for value in row['element_keys']]
        if keys != sorted(set(keys)):
            raise ModelError('merge_conflict_element_keys')
        if row['allowed_resolutions'] != _allowed(row, blocked):
            raise ModelError('merge_conflict_resolution_policy')
        for role in ROLES:
            impact = row['impact']['by_role'][role]
            tokens = [jcs(value) for value in impact]
            if tokens != sorted(set(tokens)) or any(not set(row['artifact_ids']).intersection(
                    (value['source_id'],value['target_id'])) for value in impact):
                raise ModelError('merge_conflict_impact')
    return MergeConflicts._create(document)
