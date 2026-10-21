"""Planning fields and links from one owned supplied project.

The common authoring APIs remain the only writers. This provider neither
creates a second planning model nor derives readiness, Done evidence or dates.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..changes.target_model import TargetModel, _default_scope
from ..graph.hierarchies import validate_hierarchies
from ..graph.references import RelationReferences
from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.domain_artifact import DomainArtifact
from ..storage.json_syntax import parse_json_object


@dataclass(frozen=True, init=False)
class PlanningRelations:
    """Detached stored facts; no workflow, implementation or release approval."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use assess_planning_relations with native model inputs')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Planning relations are not readiness or approval')


def assess_planning_relations(model):
    """Resolve stored planning edges and their exact existing endpoints.

Fields use the shared domain schemas, including owner/Done obligations and
exactly one Release per Milestone. Incoming implemented_by links retain their
stored orientation. Draft Tasks may still lack subject links; the report lists
them explicitly, without inventing an edge or treating them as complete.
The supplied inventory is not proof of completeness on disk or applicability.
"""
    if type(model) is not TargetModel:
        raise ModelError('planning_target_model_required')
    model = model.snapshot()
    records, values, bindings = [], {}, {}
    kinds = {'release', 'milestone', 'task', 'capability', 'requirement', 'decision'}
    for document in sorted(model.documents, key=lambda item: item.path):
        source = SourceRelations(document.content, path=document.path)
        records.append(source)
        if source.identity.artifact_type not in kinds:
            continue
        value = DomainArtifact(document.content, path=document.path).data
        values[value['id']] = value
        bindings[value['id']] = {'artifact_id': value['id'], 'artifact_type': value['artifact_type'],
            'revision': value['revision'], 'path': document.path,
            'source_sha256': sha256(document.content).hexdigest(),
            'record_sha256': canonical_json_sha256(value)}
    references = RelationReferences(records)
    validate_hierarchies(references)
    links = []
    for edge in references.relations:
        kind, source, target = edge.relation.type, edge.source, edge.target
        if not (kind == 'scheduled_for' or
                (kind == 'part_of' and source.artifact_type in ('milestone', 'task')) or
                (kind == 'implemented_by' and target.artifact_type == 'task')):
            continue
        position = next(i for i, relation in enumerate(values[source.id]['relations'])
                        if relation['relation_id'] == edge.relation.identity.id)
        links.append({'relation_id': edge.relation.identity.id, 'type': kind,
            'source_id': source.id, 'source_type': source.artifact_type,
            'target_id': target.id, 'target_type': target.artifact_type,
            'path': bindings[source.id]['path'], 'pointer': '/relations/' + str(position),
            'source_sha256': bindings[source.id]['source_sha256'],
            'relation_sha256': canonical_json_sha256(edge.relation.data)})
    links.sort(key=lambda row: (row['source_id'], row['type'], row['target_id'], row['relation_id']))
    releases, milestones, tasks, missing = [], [], [], []
    for identifier, value in sorted(values.items()):
        bound = bindings[identifier]
        kind = value['artifact_type']
        if kind == 'release':
            releases.append({**bound, **{key: value[key] for key in
                ('name', 'objective', 'maturity', 'readiness_policy')},
                **({'target_date': value['target_date']} if 'target_date' in value else {})})
        elif kind == 'milestone':
            parent, = [row for row in links if row['source_id'] == identifier and row['type'] == 'part_of']
            milestones.append({**bound, **{key: value[key] for key in ('objective', 'owner', 'maturity')},
                'release_id': parent['target_id'], 'release_relation_id': parent['relation_id'],
                **({'done_criteria': value['done_criteria']} if 'done_criteria' in value else {})})
        elif kind == 'task':
            implemented = [row for row in links if row['target_id'] == identifier and
                           row['type'] == 'implemented_by']
            subject_links = [row for row in implemented if row['source_type'] in ('requirement', 'decision')]
            if not subject_links:
                missing.append(identifier)
                if value['maturity'] == 'approved':
                    raise ModelError('planning_task_implementation_required', path=bound['path'], pointer='/relations')
            tasks.append({**bound, **{key: value[key] for key in ('description', 'owner', 'maturity',
                'implementation_status', 'verification_plan_status', 'done_criteria')},
                'implemented_subject_ids': sorted({row['source_id'] for row in implemented}),
                'implementation_relation_ids': sorted(row['relation_id'] for row in implemented)})
    scope = _default_scope()
    data = {'format_version': 'planning-relations-v1', 'project_id': model.binding.project_id,
        'input_sha256': model._sources_sha256, 'scope_descriptor': scope,
        'model_root_sha256': model.manifest(model.artifacts, scope).sha256,
        'validation_scope': 'supplied_planning_fields_and_stored_relations',
        'artifacts': [bindings[key] for key in sorted(bindings)], 'relations': links,
        'releases': releases, 'milestones': milestones, 'tasks': tasks,
        'tasks_without_subject_links': missing, 'task_subject_links_complete': not missing,
        'project_files_verified': False, 'full_validation_passed': False,
        'applicability_evaluated': False, 'done_evidence_evaluated': False,
        'release_readiness_evaluated': False, 'write_authorized': False, 'approval_granted': False}
    result = object.__new__(PlanningRelations)
    object.__setattr__(result, '_encoded', canonical_json_bytes(data))
    return result
