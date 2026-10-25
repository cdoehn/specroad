"""Planning fields and links from one owned supplied project.

The common authoring APIs remain the only writers. This provider neither
creates a second planning model nor derives readiness, Done evidence or dates.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..changes.target_model import TargetModel, _default_scope
from ..graph.hierarchies import validate_hierarchies
from ..graph.references import RelationReferences
from ..graph.symmetry import require_canonical_relations
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from ._relation_projection import _planning_sources, _planning_links, _planning_artifacts


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
    from ..documents._read_model import partial_observation, local_references, read_scope, read_root
    if type(model) is not TargetModel and partial_observation(model) is None:
        raise ModelError('planning_target_model_required')
    model = model.snapshot()
    records, values, bindings = _planning_sources(model.documents)
    references = local_references(model, records)
    require_canonical_relations(references)
    validate_hierarchies(references)
    links = _planning_links(references, values, bindings)
    releases, milestones, tasks, missing = _planning_artifacts(values, bindings, links)
    scope = read_scope(model)
    data = {'format_version': 'planning-relations-v1', 'project_id': model.binding.project_id,
        'input_sha256': model._sources_sha256, 'scope_descriptor': scope,
        'model_root_sha256': read_root(model),
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
