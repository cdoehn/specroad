"""Read-only explanation paths over one supplied, bound planning model.

Container membership and Task implementation links are traversed backwards
explicitly; origin links retain their stored direction. Scheduling, ownership,
dependencies and mitigations are separate observations, not origin shortcuts
or a Release closure. The configured trace depth bounds every returned path.
"""
from collections import deque
from dataclasses import dataclass
from hashlib import sha256

from ..changes import TargetModel
from ..graph._shortest_search import discover_predecessor
from ..graph.indices import RelationIndex
from ..graph.path_output import PathRecord
from ..graph.references import RelationReferences
from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.domain_artifact import DomainArtifact
from ..storage.json_syntax import parse_json_object
from .roadmap import project_roadmap


@dataclass(frozen=True, init=False)
class RoadmapExplanation:
    """Owned non-normative paths; never a completeness or approval authority."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use explain_roadmap with a native model')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Roadmap explanations are not readiness or approval')


def _context_edge(view):
    if not view.inverse:
        return view.type in ('addresses', 'refines', 'derived_from')
    return ((view.type == 'implemented_by' and view.source.artifact_type == 'task') or
            (view.type == 'scheduled_for' and view.source.artifact_type in ('release', 'milestone')) or
            (view.type == 'part_of' and view.source.artifact_type == 'release'
             and view.target.artifact_type == 'milestone'))


def _context_paths(index, start, depth):
    """All shortest paths under the explicit explanation link policy."""
    distances, predecessors = {start: 0}, {start: []}
    pending = deque([start])
    while pending:
        current = pending.popleft()
        if distances[current] == depth:
            continue
        for view in index.for_artifact(current):
            if _context_edge(view) and discover_predecessor(
                    distances, predecessors, current, view.target.id, view, keep_equal=True):
                pending.append(view.target.id)
    identities = {value.id: value for value in index.references.sources}
    paths = []
    for target in sorted(distances):
        # Iterate the predecessor DAG without a recursive Python depth limit.
        stack = [(target, ())]
        while stack:
            current, reverse = stack.pop()
            if current == start:
                paths.append(PathRecord.from_views(identities[start], tuple(reversed(reverse))))
            else:
                for view in reversed(predecessors[current]):
                    stack.append((view.source.id, (*reverse, view)))
    return paths


def explain_roadmap(model, artifact_id):
    """Explain stored membership, subjects and origins, plus direct neighbors.

    No inferred scheduling, transitive dependency closure, applicability or
    lifecycle decision is made. Empty goal/requirement paths remain visible;
    the supplied inventory is not evidence of current live-file completeness.
    """
    if type(model) is not TargetModel:
        raise ModelError('roadmap_explanation_target_model_required')
    model = model.snapshot()
    roadmap = project_roadmap(model)
    facts = roadmap.data
    records = [SourceRelations(d.content, path=d.path) for d in model.documents]
    index = RelationIndex(RelationReferences(records))
    index.for_artifact(artifact_id)  # Includes strict identity/type validation.
    limits = model.configuration.data.get('resource_limits', {})
    if 'trace_depth' not in limits:
        raise ModelError('roadmap_explanation_depth_not_configured', path='specroad.json',
                         pointer='/resource_limits/trace_depth')
    depth = limits['trace_depth']
    values = {record.identity.id: record.data for record in records}
    for document in model.documents:
        value = parse_json_object(document.content)
        if value['artifact_type'] in ('goal', 'need', 'assumption'):
            values[value['id']] = DomainArtifact(document.content, path=document.path).data
    bindings = {row['artifact_id']: row for row in facts['artifacts']}
    context = _context_paths(index, artifact_id, depth)
    paths = [('context', path) for path in context]
    for path in context:
        if len(path.relations) >= depth:
            continue
        for view in index.for_artifact(path.artifacts[-1].id, direction='outgoing'):
            purpose = {'scheduled_for': 'assignment', 'depends_on': 'dependency',
                       'mitigates': 'risk'}.get(view.type)
            if view.type == 'part_of' and view.source.artifact_type in ('task', 'milestone'):
                purpose = 'parent'
            if purpose is None or view.target.id in {a.id for a in path.artifacts}:
                continue
            extended = PathRecord((*path.artifacts, view.target),
                                  (*path.relations, view.stored.relation.identity), (*path.inverse, False))
            paths.append((purpose, extended))
            if (purpose == 'assignment' and view.target.artifact_type == 'milestone'
                    and len(extended.relations) < depth):
                for parent in index.for_artifact(view.target.id, direction='outgoing'):
                    if parent.type == 'part_of' and parent.target.id not in {a.id for a in extended.artifacts}:
                        paths.append((purpose, PathRecord((*extended.artifacts, parent.target),
                            (*extended.relations, parent.stored.relation.identity), (*extended.inverse, False))))
    paths = sorted(set(paths), key=lambda row: (row[0], tuple(a.id for a in row[1].artifacts),
                   tuple(r.id for r in row[1].relations), row[1].inverse))
    included = {a.id for _, path in paths for a in path.artifacts}
    used_relations = {r.id for _, path in paths for r in path.relations}
    relations = []
    for record in records:
        for position, relation in enumerate(record.data['relations']):
            if relation['relation_id'] in used_relations:
                relations.append({'relation_id': relation['relation_id'], 'type': relation['type'],
                    'source_id': record.identity.id, 'target_id': relation['target'],
                    'path': record.path, 'pointer': '/relations/' + str(position),
                    'source_sha256': bindings[record.identity.id]['source_sha256'],
                    'relation_sha256': canonical_json_sha256(relation)})
    context_ids = {path.artifacts[-1].id for path in context}
    goals = sorted(key for key in context_ids if values[key]['artifact_type'] == 'goal')
    requirements = sorted(key for key in context_ids if values[key]['artifact_type'] == 'requirement')
    stored_fields = ('title', 'name', 'statement', 'description', 'objective', 'decision',
                     'priority', 'target_date', 'probability', 'impact', 'risk_status', 'validation_status')
    data = {'format_version': 'roadmap-explanation-v1', 'generated': True, 'normative': False,
        'project_id': facts['project_id'], 'scope_descriptor': facts['scope_descriptor'],
        'input_sha256': model._sources_sha256, 'model_root_sha256': facts['model_root_sha256'],
        'roadmap_sha256': roadmap.sha256, 'artifact_id': artifact_id, 'depth': depth,
        'traversal_policy': 'roadmap-explanation-links-v1',
        'context_path_semantics': 'all_shortest_membership_implementation_and_origin_paths',
        'neighbor_path_semantics': 'direct_stored_edges_and_assignment_milestone_parent',
        'validation_scope': 'supplied_planning_origins_risks_and_stored_relations',
        'context_ids': sorted(context_ids), 'goal_ids': goals, 'requirement_ids': requirements,
        'assumption_ids': sorted(key for key in context_ids if values[key]['artifact_type'] == 'assumption'),
        'dependency_ids': sorted({path.artifacts[-1].id for purpose, path in paths if purpose == 'dependency'}),
        'risk_ids': sorted({path.artifacts[-1].id for purpose, path in paths if purpose == 'risk'}),
        'open_items': [name for name, found in (
            ('no_requirement_path_within_depth', requirements), ('no_goal_path_within_depth', goals)) if not found],
        'paths': [{'purpose': purpose, 'target_id': path.artifacts[-1].id,
                   'path': path.as_dict()} for purpose, path in paths],
        'artifacts': [{**bindings[key], 'stored': {field: values[key][field]
            for field in stored_fields if field in values[key]}} for key in sorted(included)],
        'relations': sorted(relations, key=lambda row: row['relation_id']),
        'project_files_verified': False, 'full_validation_passed': False,
        'applicability_evaluated': False, 'done_evidence_evaluated': False,
        'verification_evaluated': False, 'release_closure_evaluated': False,
        'release_readiness_evaluated': False, 'write_authorized': False, 'approval_granted': False}
    result = object.__new__(RoadmapExplanation)
    object.__setattr__(result, '_encoded', canonical_json_bytes(data))
    return result
