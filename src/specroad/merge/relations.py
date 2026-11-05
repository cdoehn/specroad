"""Read-only relation merge orchestration; no ancestry or writer authority."""
from ..model.canonical import canonical_json_bytes as jcs
from ..model.errors import ModelError
from ..graph.relation_values import Relation
from .fields import merge_fields
from .identity_checks import ROLES, _history, _identity_conflicts, _conflict
from .relation_inputs import _same, _sources, _removals
from .relation_values import RelationMergeResult


def inspect_merge_identities(sources, *, history):
    """Inspect common identity only, across artifacts, relations and resources."""
    observed, _, _ = _sources(sources)
    origins, history_hash = _history(history, sources, observed)
    conflicts = _identity_conflicts(observed, origins)
    for role in ROLES:
        getattr(sources, role).verify_current()
    return RelationMergeResult._create(sources, history_hash, [], conflicts)


def merge_relations(sources, *, history, removed_ours=(), removed_theirs=()):
    """Combine global relation identities after source and origin validation."""
    observed, values, owners = _sources(sources)
    origins, history_hash = _history(history, sources, observed)
    conflicts = _identity_conflicts(observed, origins)
    removed_ours = _removals(removed_ours, values['base'], values['ours'])
    removed_theirs = _removals(removed_theirs, values['base'], values['theirs'])
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
        elif old is not None and ((left is None and identifier not in removed_ours)
                                  or (right is None and identifier not in removed_theirs)):
            kind = 'relation_absence_unproven'
        elif any(len({jcs({name: value['relation'][name]}) if name in value['relation'] else b''
                      for value in present}) > 1 for name in ('created_at', 'created_by')):
            kind = 'relation_origin_metadata_change'
        elif _same(left, right):
            target = left
        elif _same(old, left):
            target = right
        elif _same(old, right):
            target = left
        elif left is None or right is None:
            kind = 'relation_remove_edit'
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
            storage = {observed[role][key][1]['storage_class'] for role in ROLES if key in observed[role]}
            if len(storage) > 1 or target is None or not all(_same(value, target) for value in present):
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
