"""Bound lifecycle/history guards, not a target model or a release decision.

Only protected originals can be returned as bytes. Mutable field composition,
merge metadata, current review qualification and publication remain separate.
"""
from hashlib import sha256

from ..model.canonical import canonical_json_bytes as jcs
from ..storage.json_syntax import parse_json_object
from ..model.history_protection import protected_record
from ..model.lifecycle_content import _content_hash
from .identity_checks import ROLES, _history, _identity_conflicts, _conflict
from .relation_inputs import _sources
from .lifecycle_values import LifecycleMergeResult




def _lifecycle(value):
    if value is None:
        return None
    return {key: value[key] for key in ('maturity', 'proposal_status') if key in value}


def _successors(relations, *, inverse=True):
    result = {role: {} for role in ROLES}
    for role in ROLES:
        for entry in relations[role].values():
            relation = entry['relation']
            if relation['type'] == 'supersedes':
                source, target = entry['owner_id'], relation['target']
                key, value = (target, source) if inverse else (source, target)
                result[role].setdefault(key, set()).add(value)
    return result




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
    supersedes = _successors(relations, inverse=False)
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
        predecessors = {role: sorted(supersedes[role].get(identity['id'], ())) for role in ROLES}
        if protected and (len(set(raw.values())) != 1 or len(storage) != 1):
            kind = 'immutable_original_change'
        elif old is not None and (left is None or right is None):
            kind = 'artifact_absence_unproven'
        elif protected:
            selected = 'ours' if left is not None else 'theirs'
        elif left is not None and right is not None:
            if (lifecycle['ours'] != lifecycle['base'] and lifecycle['theirs'] != lifecycle['base']
                    and lifecycle['ours'] != lifecycle['theirs']):
                kind = 'lifecycle_transition_conflict'
            elif (targets['ours'] != targets['base'] and targets['theirs'] != targets['base']
                    and targets['ours'] != targets['theirs']):
                kind = 'supersession_target_conflict'
            elif (predecessors['ours'] != predecessors['base'] and predecessors['theirs'] != predecessors['base']
                    and predecessors['ours'] != predecessors['theirs']):
                kind = 'supersession_target_conflict'
            elif old is not None and old['maturity'] != 'retired' and any(
                    side['maturity'] == 'retired' and _content_hash(other) != _content_hash(old)
                    for side, other in ((left, right), (right, left))):
                kind = 'retirement_content_conflict'
            elif old is not None and old['maturity'] == 'retired' and any(
                    side['maturity'] != 'retired' for side in (left, right)):
                kind = 'lifecycle_reactivation'
        if kind is None and not protected and any(
                values[role]['maturity'] == 'superseded' and not targets[role] for role in present):
            kind = 'supersession_target_missing'
        if kind:
            conflicts.append(_conflict(identity, kind, observed, origins, key,
                original_values=values, lifecycle_values=lifecycle, successor_ids=targets,
                supersedes_ids=predecessors))
            continue
        original = None
        if selected is not None:
            path = observed[selected][key][1]['path']
            originals[path] = raw[selected]
            original = {'role': selected, 'path': path, 'byte_sha256': sha256(raw[selected]).hexdigest(),
                        'classification': 'unchanged_ours' if selected == 'ours' else 'adopt_existing'}
        decisions.append({'identity': identity, 'protected': protected, 'original': original,
                          'lifecycle_values': lifecycle, 'successor_ids': targets,
                          'supersedes_ids': predecessors})
    for role in ROLES:
        verify_observation(getattr(sources, role))
    return LifecycleMergeResult._create(sources, history_hash, decisions, originals, conflicts)

from ._recorded import verify_observation
