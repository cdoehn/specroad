"""Read-only, origin-bound relation candidates; not a resolved merge plan.

History observations are explicit provider inputs, not inferred ancestry or
proof of authenticity. Native sources and all original observations remain
bound; no result grants writer, lifecycle, metadata or review authority.
"""
from dataclasses import dataclass
from hashlib import sha256
from itertools import combinations

from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..model.errors import ModelError
from ..model.history_values import HistoryOrigin
from ..graph.relation_values import Relation
from ..snapshots.inventory import source_resource_rows
from ..storage.json_syntax import parse_json_object
from .field_values import FieldValue
from .fields import merge_fields
from .sources import MergeSources

ROLES = ('base', 'ours', 'theirs')
IDENTITY_KINDS = frozenset(('configuration', 'artifact', 'relation', 'profile',
                          'rule', 'mapping', 'language_registry', 'language_package'))


def _same(left, right):
    return jcs(left) == jcs(right)


def _sources(sources):
    if type(sources) is not MergeSources:
        raise ModelError('merge_sources_required')
    observed, relations, owners = {}, {}, {}
    for role in ROLES:
        source = getattr(sources, role)
        source.verify_current()
        observed[role], _ = source_resource_rows(source)
        relations[role], owners[role] = {}, {}
        # Use qualified navigation for legacy originals, not their raw arrays.
        from ..bundles._payload_model import owned_payload_model
        from ..migration.model_inputs import records
        keys = tuple(source.binding['baseline']['profile_keys']) if source.kind == 'baseline' else None
        model = owned_payload_model(source.files, source_label='merge-relations:' + source.source_root,
                                    profile_keys=keys)
        for record in records(model):
            owners[role][record.identity.id] = record.identity
            for relation in record.relations:
                relations[role][relation.identity.id] = {'owner_id': record.identity.id,
                                                        'relation': relation.data}
    return observed, relations, owners


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


@dataclass(frozen=True, init=False)
class RelationMergeResult:
    _encoded: bytes

    @classmethod
    def _create(cls, sources, history_hash, candidates, conflicts):
        result = object.__new__(cls)
        object.__setattr__(result, '_encoded', jcs({
            'source_bindings': sources.binding, 'source_bindings_sha256': sources.sha256,
            'history_sha256': history_hash, 'relations': None if conflicts else candidates,
            'conflicts': conflicts, 'ready': False, 'write_authorized': False}))
        return result

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def canonical_bytes(self):
        return self._encoded

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    @property
    def conflicts(self):
        return self.data['conflicts']

    @property
    def merged(self):
        return not self.conflicts

    @property
    def relations(self):
        if not self.merged:
            raise ModelError('unresolved_relation_merge')
        return self.data['relations']

    @property
    def ready(self):
        return False

    @property
    def write_authorized(self):
        return False

    def __bool__(self):
        raise TypeError('Relation candidates do not authorize a merge or write')


def inspect_merge_identities(sources, *, history):
    """Inspect common identity only, across artifacts, relations and resources."""
    observed, _, _ = _sources(sources)
    origins, history_hash = _history(history, sources, observed)
    conflicts = _identity_conflicts(observed, origins)
    for role in ROLES:
        getattr(sources, role).verify_current()
    return RelationMergeResult._create(sources, history_hash, [], conflicts)


def merge_relations(sources, *, history):
    """Combine global relation identities after source and origin validation."""
    observed, values, owners = _sources(sources)
    origins, history_hash = _history(history, sources, observed)
    conflicts = _identity_conflicts(observed, origins)
    blocked = {jcs(row['identity']) for row in conflicts}
    candidates = []
    for identifier in sorted(set().union(*(set(values[role]) for role in ROLES))):
        identity = {'kind': 'relation', 'id': identifier, 'version': None}
        key = jcs(identity)
        if key in blocked:
            continue
        old, left, right = (values[role].get(identifier) for role in ROLES)
        present = [value for value in (old, left, right) if value is not None]
        kind = None
        if len({value['owner_id'] for value in present}) != 1:
            kind = 'relation_owner_change'
        elif old is not None and (left is None or right is None):
            kind = 'relation_absence_unproven'
        elif _same(left, right):
            target = left
        elif _same(old, left):
            target = right
        elif _same(old, right):
            target = left
        else:
            outcome = merge_fields({} if old is None else old, left, right)
            if not outcome.merged:
                conflicts.append(_conflict(identity, 'relation_content_change', observed, origins, key,
                    original_values={'base': old, 'ours': left, 'theirs': right},
                    field_conflicts=[{'pointer': row.pointer, 'kind': row.kind} for row in outcome.conflicts]))
                continue
            target = outcome.value
        if kind is None and any(observed[role][key][1]['storage_class'] == 'legacy_immutable'
                                for role in ROLES if key in observed[role]):
            if not all(_same(value, target) for value in present):
                kind = 'relation_immutable_change'
        if kind:
            conflicts.append(_conflict(identity, kind, observed, origins, key))
            continue
        if target is not None:
            owner = next(owners[role][target['owner_id']] for role in ROLES if target['owner_id'] in owners[role])
            try:
                Relation(owner, target['relation'])
            except ModelError:
                conflicts.append(_conflict(identity, 'relation_invalid_combination', observed, origins, key))
                continue
            candidates.append(target)
    for role in ROLES:
        getattr(sources, role).verify_current()
    return RelationMergeResult._create(sources, history_hash, candidates, conflicts)
