"""Pure value diffs and one-hop impact for later Change Plans and adapters.

No natural-language interpretation, source discovery, printing, file mutation,
transitive impact or write authorization is provided by these primitives.
"""
from dataclasses import dataclass
import json

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from .relations import SourceRelations
from .references import RelationReferences
from .indices import RelationIndex


def _owned(value):
    encoded = canonical_json_bytes(value)
    try:
        return json.loads(encoded)
    except (ValueError, RecursionError) as error:
        raise ModelError('comparison_nesting_not_supported') from error


@dataclass(frozen=True, init=False)
class ComparisonResult:
    """Owned, immutable result data; neither a report renderer nor a JSON Patch."""
    _encoded: bytes

    def __init__(self, value):
        object.__setattr__(self, '_encoded', canonical_json_bytes(_owned(value)))

    @property
    def data(self):
        return json.loads(self._encoded)

    @property
    def sha256(self):
        return canonical_json_sha256(self.data)


@dataclass(frozen=True, init=False)
class ComparisonInputs:
    """An explicit artifact set. Absence means removal only from THIS set."""
    project_id: str
    records: tuple

    def __init__(self, project_id, records):
        if type(project_id) is not str or not project_id.strip() or '\0' in project_id:
            raise ModelError('comparison_project_required')
        canonical_json_bytes(project_id)
        if isinstance(records, (str, bytes, dict)):
            raise ModelError('comparison_records_required')
        try:
            records = tuple(records)
        except TypeError as error:
            raise ModelError('comparison_records_required') from error
        seen, prefixes = set(), set()
        for record in records:
            if type(record) is not SourceRelations:
                raise ModelError('source_relations_required')
            if record.identity.id in seen:
                raise ModelError('duplicate_artifact_id')
            if 'project_id' in record.data and record.data['project_id'] != project_id:
                raise ModelError('comparison_project_mismatch')
            seen.add(record.identity.id); prefixes.add(record.identity.id_prefix)
        if len(prefixes) > 1:
            raise ModelError('mixed_project_prefix')
        object.__setattr__(self, 'project_id', project_id)
        object.__setattr__(self, 'records', tuple(sorted(records,
            key=lambda record: record.identity.id.encode('utf-8'))))

    @property
    def fingerprint(self):
        return canonical_json_sha256({'project_id': self.project_id,
            'artifacts': [{'id': r.identity.id, 'sha256': canonical_json_sha256(r.data)}
                          for r in self.records]})


def _category(parts, before, after):
    # Only the declared field location, never words or numbers inside prose.
    if parts and parts[0] in ('statement', 'description', 'rationale', 'title'):
        return 'text_changed'
    return 'field_changed'


def field_diff(before, after):
    """Compare exact JSON values with RFC-6901 locations. Arrays are atomic.

    Presence flags distinguish missing from explicit null. Object-key order and
    equivalent JCS number encodings are not changes. Array order IS data.
    """
    left, right = _owned(before), _owned(after)
    pending, changes = [((), True, left, True, right)], []
    while pending:
        parts, has_before, old, has_after, new = pending.pop()
        if has_before and has_after and canonical_json_bytes(old) == canonical_json_bytes(new):
            continue
        if has_before and has_after and type(old) is dict and type(new) is dict:
            keys = sorted(set(old) | set(new), key=lambda k: k.encode('utf-8'), reverse=True)
            pending.extend((parts + (key,), key in old, old.get(key), key in new, new.get(key))
                           for key in keys)
            continue
        changes.append({'pointer': ''.join('/' + p.replace('~', '~0').replace('/', '~1') for p in parts),
            'operation': 'add' if not has_before else 'remove' if not has_after else 'replace',
            'before_present': has_before, 'after_present': has_after,
            'before': old, 'after': new, 'category': _category(parts, old, new)})
    return ComparisonResult({'comparison_version': 'field-diff-v1', 'changes': changes,
                             'changed': bool(changes)})


def compare_artifacts(before, after):
    """Compare supplied sets by immutable artifact ID; not a legal edit plan."""
    if type(before) is not ComparisonInputs or type(after) is not ComparisonInputs:
        raise ModelError('comparison_inputs_required')
    if before.project_id != after.project_id:
        raise ModelError('comparison_project_mismatch')
    if len({r.identity.id_prefix for r in before.records + after.records}) > 1:
        raise ModelError('mixed_project_prefix')
    left = {r.identity.id: r for r in before.records}
    right = {r.identity.id: r for r in after.records}
    changes = []
    for identity in sorted(set(left) | set(right), key=lambda value: value.encode('utf-8')):
        old, new = left.get(identity), right.get(identity)
        if old is not None and new is not None and old.identity != new.identity:
            raise ModelError('comparison_identity_changed')
        delta = field_diff(old.data if old is not None else None,
                           new.data if new is not None else None).data
        if delta['changed']:
            changes.append({'artifact_id': identity,
                'change_kind': 'added' if old is None else 'removed' if new is None else 'modified',
                'before_sha256': canonical_json_sha256(old.data) if old is not None else None,
                'after_sha256': canonical_json_sha256(new.data) if new is not None else None,
                'fields': delta['changes']})
    return ComparisonResult({'comparison_version': 'artifact-diff-v1',
        'project_id': before.project_id, 'before_sha256': before.fingerprint,
        'after_sha256': after.fingerprint, 'changes': changes, 'changed': bool(changes),
        'validation_scope': 'supplied_artifact_sets_only', 'write_authorized': False})


def direct_impact(artifact_id, references):
    """All directly connected artifacts, both directions, grouped by stored type."""
    if type(references) is not RelationReferences:
        raise ModelError('resolved_relations_required')
    index = RelationIndex(references)
    views = index.for_artifact(artifact_id, direction='both')
    groups = {}
    for view in views:
        edge = view.stored
        kind = edge.relation.type
        entry = {'relation_id': edge.relation.identity.id,
            'related_id': view.target.id, 'direction': 'incoming' if view.inverse else 'outgoing'}
        groups.setdefault(kind, []).append(entry)
    result = []
    for kind in sorted(groups):
        connections = sorted(groups[kind], key=lambda c: (c['related_id'], c['direction'], c['relation_id']))
        result.append({'relation_type': kind,
            'artifact_ids': sorted({c['related_id'] for c in connections}), 'connections': connections})
    return ComparisonResult({'impact_version': 'direct-impact-v1', 'artifact_id': artifact_id,
        'groups': result, 'depth': 1, 'transitive': False,
        'validation_scope': 'supplied_relation_set_only', 'write_authorized': False})
