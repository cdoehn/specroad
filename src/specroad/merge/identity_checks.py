"""One origin policy for artifacts, relations and normative resources.

Inputs bind explicit provider observations; this module never invents ancestry.
"""
from itertools import combinations
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..model.errors import ModelError
from ..model.history_values import HistoryOrigin
from .field_values import FieldValue

ROLES = ('base', 'ours', 'theirs')
IDENTITY_KINDS = frozenset(('configuration', 'artifact', 'relation', 'profile',
                          'rule', 'mapping', 'language_registry', 'language_package'))


def _history(history, sources, observed):
    if type(history) is not dict:
        raise ModelError('merge_history_input_required')
    value = FieldValue._create(history).value
    if (set(value) != {'history_format_version', 'source_bindings_sha256', 'observations'}
            or value['history_format_version'] != 'merge-history-input-v1'
            or type(value['observations']) is not list):
        raise ModelError('invalid_merge_history_input')
    if value['source_bindings_sha256'] != sources.sha256:
        raise ModelError('merge_history_source_mismatch')
    result = {role: {} for role in ROLES}
    for row in value['observations']:
        if type(row) is not dict or set(row) != {'role', 'identity', 'origin'}:
            raise ModelError('invalid_merge_history_observation')
        role, identity = row['role'], row['identity']
        if (type(role) is not str or role not in ROLES or type(identity) is not dict
                or set(identity) != {'kind', 'id', 'version'}
                or type(identity['kind']) is not str or identity['kind'] not in IDENTITY_KINDS):
            raise ModelError('invalid_merge_history_identity')
        key = jcs(identity)
        if key not in observed[role]:
            raise ModelError('merge_history_identity_absent')
        if key in result[role]:
            raise ModelError('duplicate_merge_history_observation')
        origin = row['origin']
        if origin is not None:
            if type(origin) is not dict or set(origin) != {'namespace', 'creation_event'}:
                raise ModelError('invalid_merge_history_origin')
            HistoryOrigin(identity['id'], origin['namespace'], origin['creation_event'])
        result[role][key] = origin
    value['observations'].sort(key=lambda row: (ROLES.index(row['role']), jcs(row['identity'])))
    return result, digest(value)


def _observation(observed, origins, role, key):
    if key not in observed[role]:
        return {'state': 'absent', 'origin': None}
    return {**observed[role][key][1], 'origin': origins[role].get(key)}


def _conflict(identity, kind, observed, origins, key, **extra):
    return {'identity': identity, 'kind': kind,
            **{role: _observation(observed, origins, role, key) for role in ROLES}, **extra}


def _identity_conflicts(observed, origins):
    conflicts = []
    for key in sorted(set().union(*(set(observed[role]) for role in ROLES))):
        present = [role for role in ROLES if key in observed[role]]
        identity = observed[present[0]][key][0]
        if identity['kind'] not in IDENTITY_KINDS or len(present) < 2:
            continue
        values = [observed[role][key][1] for role in present]
        known = [origins[role].get(key) for role in present]
        collision = (len({value['id_scheme'] for value in values}) > 1
                     or any(a is not None and b is not None and a != b for a, b in combinations(known, 2)))
        if collision:
            conflicts.append(_conflict(identity, 'identity_collision', observed, origins, key,
                                       diagnostic_code='SRV101'))
        elif any(origin is None for origin in known):
            conflicts.append(_conflict(identity, 'identity_history_unresolved', observed, origins, key))
    return conflicts
