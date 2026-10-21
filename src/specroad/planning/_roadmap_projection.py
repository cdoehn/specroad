"""Private roadmap facts, independent of any timeline or table renderer.

The public provider validates its native snapshot and planning graph first.
These projections retain stored fields and direct edges; they neither reopen
project files nor estimate, authorize, render or publish anything.
"""
from hashlib import sha256

from ..model.canonical import canonical_json_sha256
from ..storage.domain_artifact import DomainArtifact
from ..storage.json_syntax import parse_json_object

_ITEM_TYPES = frozenset(('release', 'milestone', 'task', 'capability', 'requirement', 'decision'))
_STORED_FIELDS = ('title', 'name', 'objective', 'description', 'statement', 'decision',
    'owner', 'maturity', 'implementation_status', 'verification_plan_status',
    'done_criteria', 'priority', 'target_date')
_RISK_FIELDS = ('title', 'description', 'owner', 'maturity', 'probability', 'impact',
                'risk_status', 'acceptance_rationale')


def _roadmap_sources(model):
    """Retain exact source bindings and validate risks with their shared schema."""
    values, bindings = {}, {}
    for document in model.documents:
        value = parse_json_object(document.content)
        if value['artifact_type'] == 'risk':
            value = DomainArtifact(document.content, path=document.path).data
        key = value['id']
        values[key] = value
        bindings[key] = {'artifact_id': key, 'artifact_type': value['artifact_type'],
            'revision': value['revision'], 'path': document.path,
            'source_sha256': sha256(document.content).hexdigest(),
            'record_sha256': canonical_json_sha256(value)}
    return values, bindings


def _roadmap_links(values, bindings):
    """Select direct stored edges while preserving source direction and pointers."""
    links = []
    for key, value in sorted(values.items()):
        for position, relation in enumerate(value['relations']):
            kind, target = relation['type'], values[relation['target']]
            include = (kind in ('scheduled_for', 'mitigates') or
                (kind == 'part_of' and value['artifact_type'] in ('milestone', 'task')) or
                (kind == 'implemented_by' and target['artifact_type'] == 'task') or
                (kind == 'depends_on' and
                 (value['artifact_type'] in _ITEM_TYPES or target['artifact_type'] in _ITEM_TYPES)))
            if include:
                links.append({'relation_id': relation['relation_id'], 'type': kind,
                    'source_id': key, 'source_type': value['artifact_type'],
                    'target_id': target['id'], 'target_type': target['artifact_type'],
                    'path': bindings[key]['path'], 'pointer': '/relations/' + str(position),
                    'source_sha256': bindings[key]['source_sha256'],
                    'relation_sha256': canonical_json_sha256(relation)})
    links.sort(key=lambda row: (row['source_id'], row['type'], row['target_id'], row['relation_id']))
    return links


def _roadmap_facts(values, bindings, links):
    """Keep stored facts, direct schedule groups and explicit missing assignments."""
    def outgoing(identifier, kind):
        return sorted({row['target_id'] for row in links
                       if row['source_id'] == identifier and row['type'] == kind})

    def incoming(identifier, kind):
        return sorted({row['source_id'] for row in links
                       if row['target_id'] == identifier and row['type'] == kind})

    items, risks, groups, unscheduled = [], [], [], []
    for key, value in sorted(values.items()):
        kind = value['artifact_type']
        if kind in _ITEM_TYPES:
            scheduled = outgoing(key, 'scheduled_for')
            items.append({**bindings[key],
                'stored': {field: value[field] for field in _STORED_FIELDS if field in value},
                'scheduled_for_ids': scheduled, 'parent_ids': outgoing(key, 'part_of'),
                'dependency_ids': outgoing(key, 'depends_on'),
                'mitigates_ids': outgoing(key, 'mitigates'),
                'implemented_subject_ids': incoming(key, 'implemented_by')})
            if kind in ('capability', 'requirement', 'task') and not scheduled:
                unscheduled.append(key)
        elif kind == 'risk':
            risks.append({**bindings[key],
                'stored': {field: value[field] for field in _RISK_FIELDS if field in value},
                'mitigated_by_ids': incoming(key, 'mitigates')})
        if kind in ('release', 'milestone'):
            groups.append({'planning_id': key, 'artifact_type': kind,
                'scheduled_artifact_ids': incoming(key, 'scheduled_for'),
                'milestone_ids': sorted(row['source_id'] for row in links
                    if row['target_id'] == key and row['type'] == 'part_of'
                    and row['source_type'] == 'milestone')})
    return items, risks, groups, unscheduled
