"""Read-only roadmap facts from the existing supplied project model.

Stored dates and priorities are not inherited or estimated. Direct schedule
groups are not Release closures, and risk labels are not readiness decisions.
There is no supplemental planning file, renderer, clock or publication path.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..changes import TargetModel
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from ._roadmap_projection import _roadmap_facts, _roadmap_links, _roadmap_sources
from .relations import assess_planning_relations


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
    from ..documents._read_model import partial_observation
    partial = partial_observation(model)
    if type(model) is not TargetModel and partial is None:
        raise ModelError('roadmap_target_model_required')
    model = model.snapshot()
    planning = assess_planning_relations(model)
    plan = planning.data
    values, bindings = _roadmap_sources(model)
    links = _roadmap_links(values, bindings, partial=partial is not None)
    items, risks, groups, unscheduled = _roadmap_facts(values, bindings, links)

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
