"""Source-bound read-only conflict catalogue and passive stored-plan inspection."""
from hashlib import sha256

from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object as parsed
from .conflict_schema import FORMAT, ROLES, PENDING, GUARD_CLASSES
from .field_values import _MISSING, FieldValue
from .inventory import _plan_id, _absent
from .identity_checks import _history
from .relation_inputs import _sources
from .relations import merge_relations
from .attachments import merge_attachments
from .lifecycle import inspect_merge_lifecycle
from ._field_merge import merge_owned
from .schema_collections import collection_rules
from .conflict_values import MergeConflicts, _identifier, _allowed, parse_merge_conflicts


def _value(value):
    if value is _MISSING:
        return {'state':'absent'}
    if type(value) is bytes:
        return {'state':'present','domain':'bytes-v1','size':len(value),'sha256':sha256(value).hexdigest()}
    return {'state':'present','domain':'json-v1','value':FieldValue._create(value).value}


def _originals(sources, observed, relations, key):
    result = {}
    for role in ROLES:
        entry = observed[role].get(key)
        if entry is None:
            result[role] = _MISSING
            continue
        identity, observation = entry
        raw = getattr(sources, role).files[observation['path']]
        if identity['kind']=='relation':
            result[role] = relations[role][identity['id']]
        elif observation['value_domain']=='json-v1' and observation['storage_class']!='legacy_immutable':
            result[role] = parsed(raw)
        else:
            result[role] = raw
    return result


def _impact(artifact_ids, relations):
    roles = {}
    for role in ROLES:
        rows = []
        for identifier, value in relations[role].items():
            relation = value['relation']
            if set(artifact_ids).intersection((value['owner_id'], relation['target'])):
                rows.append({'relation_id':identifier,'source_id':value['owner_id'],
                    'target_id':relation['target'],'relation_type':relation['type']})
        roles[role] = sorted(rows, key=jcs)
    return {'scope':'direct_source_relations','depth':1,'transitive':False,'by_role':roles}


def _rules(value):
    if type(value) is not dict or 'artifact_type' not in value:
        return None
    from ..model.domain_schemas import domain_schema, DOMAIN_TYPES
    from ..model.record_schemas import record_schema
    kind = value['artifact_type']
    return collection_rules(domain_schema(kind) if kind in DOMAIN_TYPES else record_schema(kind))


def build_merge_conflicts(sources, *, plan_id, history):
    """Collect every current conflict; pending downstream gates stay explicit."""
    _plan_id(plan_id)
    if type(history) is not dict:
        raise ModelError('merge_history_input_required')
    history = FieldValue._create(history).value
    observed, relations, _ = _sources(sources)
    _, history_hash = _history(history, sources, observed)
    relation_result = merge_relations(sources, history=history)
    lifecycle_result = inspect_merge_lifecycle(sources, history=history)
    document = {'conflict_format_version':FORMAT,'plan_id':plan_id,
        'source_bindings':sources.binding,'source_bindings_sha256':sources.sha256,
        'history_input_sha256':history_hash,'pending_gates':list(PENDING),
        'ready':False,'write_authorized':False,'approval_granted':False}
    rows = {}

    def add(identity, kind, pointer='', values=None, element_keys=()):
        key = jcs(identity)
        observations = {role:observed[role][key][1] if key in observed[role] else _absent() for role in ROLES}
        if values is None:
            values = _originals(sources, observed, relations, key)
        artifact_ids = ([identity['id']] if identity['kind']=='artifact' else sorted({
            obs['owner_id'] for obs in observations.values() if obs['owner_id'] is not None}))
        row = {'identity':identity,'artifact_ids':artifact_ids,'pointer':pointer,'conflict_class':kind,
            'values':{role:_value(values[role]) for role in ROLES},'observations':observations,
            'element_keys':sorted(element_keys, key=jcs),'impact':_impact(artifact_ids,relations),
            'allowed_resolutions':[]}
        row['conflict_id'] = _identifier(document, row)
        previous = rows.setdefault(row['conflict_id'], row)
        if previous != row:
            raise ModelError('merge_conflict_duplicate_identity')

    guards = list(relation_result.conflicts) + list(lifecycle_result.conflicts)
    blocked = {jcs(row['identity']) for row in guards if row['kind']!='relation_content_change'}
    unidentified = {jcs(row['identity']) for row in guards
                    if row['kind'] in ('identity_collision','identity_history_unresolved')}
    for guard in guards:
        if guard['kind']=='relation_content_change':
            continue  # Expanded below into every individual original field branch.
        add(guard['identity'],guard['kind'])
    attachments = [{path:raw for path,raw in getattr(sources,role).files.items()
                    if path.startswith('attachments/')} for role in ROLES]
    for conflict in merge_attachments(*attachments).conflicts:
        add({'kind':'attachment','id':conflict.path,'version':None},conflict.kind)
    ignored = {'revision','created_at','created_by','updated_at','updated_by','relations','maturity'}
    for key in sorted(set().union(*(set(observed[role]) for role in ROLES))):
        identity = next(observed[role][key][0] for role in ROLES if key in observed[role])
        if identity['kind']=='attachment':
            continue
        values = _originals(sources,observed,relations,key)
        old,left,right = (values[role] for role in ROLES)
        if key in unidentified:
            continue
        if old is not _MISSING and (left is _MISSING or right is _MISSING):
            if key not in blocked:
                add(identity,'resource_absence_unproven')
            continue
        if left is _MISSING or right is _MISSING:
            continue  # A single addition, not an implicit deletion.
        observations = [observed[role][key][1] for role in ROLES if key in observed[role]]
        if identity['kind']!='relation' and len({v['path'] for v in observations})>1:
            add(identity,'resource_location_conflict')
            continue
        if type(left) is bytes or type(right) is bytes or type(old) is bytes:
            if key in blocked:
                continue
            if identity['kind']=='archive' and any(value is not _MISSING and value!=left for value in values.values()):
                add(identity,'immutable_original_change')
            elif left!=right and old!=left and old!=right:
                add(identity,'attachment_binary_change' if identity['kind']=='attachment' else 'resource_binary_change')
            continue
        rules = _rules(left) if identity['kind']=='artifact' else None
        _, conflicts = merge_owned(old, left, right, rules=rules)
        for conflict in conflicts:
            head = conflict.pointer.split('/')[1] if conflict.pointer else ''
            if identity['kind']=='artifact' and (head in ignored or
                    (left.get('artifact_type')=='proposal' and head=='status')):
                continue
            add(identity,conflict.kind,conflict.pointer,
                {role:getattr(conflict,role).value if getattr(conflict,role).present else _MISSING for role in ROLES},
                [value.value for value in getattr(conflict,'element_keys',())])
    blocked = {jcs(row['identity']) for row in rows.values() if row['conflict_class'] in GUARD_CLASSES}
    for row in rows.values():
        row['allowed_resolutions'] = _allowed(row, blocked)
    document['conflicts'] = sorted(rows.values(),key=lambda row:row['conflict_id'])
    document['conflicts_sha256'] = digest(document['conflicts'])
    for role in ROLES:
        getattr(sources,role).verify_current()
    return parse_merge_conflicts(jcs(document))


def read_merge_conflicts(raw, sources, *, history):
    stored = parse_merge_conflicts(raw)
    expected = build_merge_conflicts(sources, plan_id=stored.data['plan_id'],history=history)
    if stored.canonical_bytes != expected.canonical_bytes:
        raise ModelError('merge_conflicts_binding_mismatch')
    return expected
