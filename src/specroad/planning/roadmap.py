"""Read-only roadmap facts from the existing supplied project model.

Stored dates and priorities are not inherited or estimated. Direct schedule
groups are not Release closures, and risk labels are not readiness decisions.
There is no supplemental planning file, renderer, clock or publication path.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..changes import TargetModel
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.domain_artifact import DomainArtifact
from ..storage.json_syntax import parse_json_object
from .relations import assess_planning_relations

_ITEM_TYPES = frozenset(('release', 'milestone', 'task', 'capability', 'requirement', 'decision'))
_STORED_FIELDS = ('title', 'name', 'objective', 'description', 'statement', 'decision',
    'owner', 'maturity', 'implementation_status', 'verification_plan_status',
    'done_criteria', 'priority', 'target_date')
_RISK_FIELDS = ('title', 'description', 'owner', 'maturity', 'probability', 'impact',
                'risk_status', 'acceptance_rationale')


@dataclass(frozen=True, init=False)
class RoadmapProjection:
    """Owned generated facts, never a second normative model or an approval."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use project_roadmap with a native model')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Roadmap facts are not readiness or approval')


def project_roadmap(model):
    """Project direct planning links, stored fields and risk observations.

    The shared planning provider validates its fields and the complete supplied
    relation graph before this projection. Risk fields use their common schema.
    Applicability, live-file completeness, Done and readiness remain unevaluated.
    Unscheduled means no explicit scheduled_for edge, not missing ownership.
    """
    if type(model) is not TargetModel:
        raise ModelError('roadmap_target_model_required')
    model = model.snapshot()
    planning = assess_planning_relations(model)
    plan = planning.data
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

    data = {'format_version': 'roadmap-projection-v1', 'generated': True, 'normative': False,
        'project_id': plan['project_id'], 'scope_descriptor': plan['scope_descriptor'],
        'input_sha256': model._sources_sha256, 'model_root_sha256': plan['model_root_sha256'],
        'planning_sha256': planning.sha256,
        'validation_scope': 'supplied_roadmap_fields_and_stored_relations',
        'artifacts': [bindings[key] for key in sorted(bindings)],
        'items': items, 'risks': risks, 'relations': links, 'schedule_groups': groups,
        'unscheduled_ids': unscheduled,
        'tasks_without_subject_links': plan['tasks_without_subject_links'],
        'task_subject_links_complete': plan['task_subject_links_complete'],
        'project_files_verified': False, 'full_validation_passed': False,
        'applicability_evaluated': False, 'done_evidence_evaluated': False,
        'verification_evaluated': False, 'release_closure_evaluated': False,
        'release_readiness_evaluated': False, 'dates_estimated': False,
        'effort_estimated': False, 'critical_path_evaluated': False,
        'write_authorized': False, 'approval_granted': False}
    result = object.__new__(RoadmapProjection)
    object.__setattr__(result, '_encoded', canonical_json_bytes(data))
    return result
