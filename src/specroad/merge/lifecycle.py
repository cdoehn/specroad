"""Bound lifecycle/history guards, not a target model or a release decision.

Only protected originals can be returned as bytes. Mutable field composition,
merge metadata, current review qualification and publication remain separate.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..model.canonical import canonical_json_bytes as jcs
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from .identity_checks import ROLES, _history, _identity_conflicts, _conflict
from .relation_inputs import _sources


def protected_record(value):
    return (value['artifact_type'] in ('baseline', 'evidence', 'relation_review') or
            value['artifact_type'] == 'proposal' and
            value['proposal_status'] in ('rejected', 'applied', 'stale'))


def _lifecycle(value):
    if value is None:
        return None
    return {key: value[key] for key in ('maturity', 'proposal_status') if key in value}


def _successors(relations):
    result = {role: {} for role in ROLES}
    for role in ROLES:
        for entry in relations[role].values():
            relation = entry['relation']
            if relation['type'] == 'supersedes':
                result[role].setdefault(relation['target'], set()).add(entry['owner_id'])
    return result


@dataclass(frozen=True, init=False)
class LifecycleMergeResult:
    _encoded: bytes
    _originals: tuple

    @classmethod
    def _create(cls, sources, history_hash, decisions, originals, conflicts):
        result = object.__new__(cls)
        object.__setattr__(result, '_encoded', jcs({
            'source_bindings': sources.binding, 'source_bindings_sha256': sources.sha256,
            'history_sha256': history_hash, 'metadata_policy_version': 'merge-metadata-v1',
            'decisions': decisions, 'conflicts': conflicts, 'ready': False,
            'write_authorized': False, 'approval_granted': False}))
        object.__setattr__(result, '_originals', tuple(sorted(originals.items())) if not conflicts else ())
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
    def compatible(self):
        return not self.conflicts

    @property
    def originals(self):
        """Protected subset only, with exact source bytes; never a full target."""
        if not self.compatible:
            raise ModelError('unresolved_lifecycle_merge')
        return dict(self._originals)

    @property
    def ready(self):
        return False

    @property
    def write_authorized(self):
        return False

    @property
    def approval_granted(self):
        return False

    def __bool__(self):
        raise TypeError('History compatibility is not merge, write or review approval')


def inspect_merge_lifecycle(sources, *, history):
    """Check native original bytes before any field/equality merge shortcut.

Use the same explicit provider-origin contract as the relation merge. No
ancestry, transition event, review authority or deletion is guessed here.
"""
    observed, relations, _ = _sources(sources)
    origins, history_hash = _history(history, sources, observed)
    conflicts = _identity_conflicts(observed, origins)
    blocked = {jcs(row['identity']) for row in conflicts}
    successors = _successors(relations)
    decisions, originals = [], {}
    files = {role: getattr(sources, role).files for role in ROLES}
    for key in sorted(set().union(*(set(observed[role]) for role in ROLES))):
        present = [role for role in ROLES if key in observed[role]]
        identity = observed[present[0]][key][0]
        if identity['kind'] != 'artifact' or key in blocked:
            continue
        raw = {role: files[role][observed[role][key][1]['path']] for role in present}
        values = {role: parse_json_object(raw[role]) if role in raw else None for role in ROLES}
        old, left, right = (values[role] for role in ROLES)
        storage = {observed[role][key][1]['storage_class'] for role in present}
        protected = 'legacy_immutable' in storage or any(protected_record(values[role]) for role in present)
        kind, selected = None, None
        lifecycle = {role: _lifecycle(values[role]) for role in ROLES}
        targets = {role: sorted(successors[role].get(identity['id'], ())) for role in ROLES}
        if protected and (len(set(raw.values())) != 1 or len(storage) != 1):
            kind = 'immutable_original_change'
        elif old is not None and (left is None or right is None):
            kind = 'artifact_absence_unproven'
        elif protected:
            selected = 'ours' if left is not None else 'theirs'
        elif old is not None and left is not None and right is not None:
            if (lifecycle['ours'] != lifecycle['base'] and lifecycle['theirs'] != lifecycle['base']
                    and lifecycle['ours'] != lifecycle['theirs']):
                kind = 'lifecycle_transition_conflict'
            elif (targets['ours'] != targets['base'] and targets['theirs'] != targets['base']
                    and targets['ours'] != targets['theirs']):
                kind = 'supersession_target_conflict'
        if kind:
            conflicts.append(_conflict(identity, kind, observed, origins, key,
                original_values=values, lifecycle_values=lifecycle, successor_ids=targets))
            continue
        original = None
        if selected is not None:
            path = observed[selected][key][1]['path']
            originals[path] = raw[selected]
            original = {'role': selected, 'path': path, 'byte_sha256': sha256(raw[selected]).hexdigest(),
                        'classification': 'unchanged_ours' if selected == 'ours' else 'adopt_existing'}
        decisions.append({'identity': identity, 'protected': protected, 'original': original,
                          'lifecycle_values': lifecycle, 'successor_ids': targets})
    for role in ROLES:
        getattr(sources, role).verify_current()
    return LifecycleMergeResult._create(sources, history_hash, decisions, originals, conflicts)
