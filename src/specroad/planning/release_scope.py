"""Bound Release seeds and closure over an explicitly supplied project.

External means outside the selected Release's native seed membership, not
outside its expanded closure. Dependencies retain their stored direction and
identity. This observation does not evaluate readiness or authorize a release.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..changes import TargetModel
from ..configurations import resolve_configuration
from ..graph._model_scope import resolve_required_scope
from ..graph.relations import SourceRelations
from ..graph.scope_descriptors import ScopeDescriptor
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from ._release_scope_projection import release_dependencies, release_members
from .relations import assess_planning_relations


@dataclass(frozen=True, init=False)
class ReleaseScope:
    """Owned scope observation; neither a normative ScopeHash nor readiness."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use resolve_release_scope with native bound inputs')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Release scope is not readiness or approval')


def resolve_release_scope(model, release_id, *, scope_bindings, configuration_id=None):
    """Resolve native Release seeds and their closed core closure.

    Resource uses and current-review observations are mandatory explicit inputs.
    The shared adapter rebinds their inventory to this model's actual bytes;
    provider authentication and live inventory completeness remain unevaluated.
    Configuration admission, missing dependencies and closure traversal use the
    existing scope providers. No scheduling or dependency walk is duplicated.
    Every reached artifact uses its native schema and applicability classifier.
    Without a selected configuration, conditional members remain in the closure
    and are explicitly unresolved; they do not become unconditional obligations.
    """
    if type(model) is not TargetModel:
        raise ModelError('release_scope_target_model_required')
    model = model.snapshot()
    descriptor = ScopeDescriptor({'scope_version': 'scope-v1', 'scope_kind': 'release',
        'selector': {'release_id': release_id}, 'configuration_id': configuration_id,
        'closure_profile': 'core-closure-v1', 'boundary_policy': 'closed'})
    planning = assess_planning_relations(model)
    records = [SourceRelations(document.content, path=document.path) for document in model.documents]
    closure = resolve_required_scope(model, records, descriptor, scope_bindings, configuration_id)
    seeds = set(closure.seeds.artifact_ids)
    if release_id not in seeds:
        raise ModelError('release_scope_release_excluded', pointer='/selector/release_id')

    configuration = (None if configuration_id is None else
                     resolve_configuration(records, configuration_id))
    values, bindings, applicability = release_members(records, closure.artifact_ids, configuration)
    required = release_dependencies(values, bindings, closure.artifact_ids, seeds)
    external = [row for row in required if row['external']]
    applicability.sort(key=lambda row: row['artifact_id'].encode('utf-8'))
    unresolved = [row['artifact_id'] for row in applicability if row['status'] == 'potentially_applicable']
    plan = planning.data
    data = {'format_version': 'release-scope-v1', 'generated': True, 'normative': False,
        'project_id': plan['project_id'], 'release_id': release_id,
        'input_sha256': model._sources_sha256,
        'project_model_root_sha256': plan['model_root_sha256'],
        'planning_sha256': planning.sha256, 'scope_descriptor': descriptor.data,
        'scope_descriptor_sha256': descriptor.sha256,
        'configuration_hash': closure.seeds.configuration_sha256,
        'applicability': applicability, 'unresolved_applicability': unresolved,
        'scope_applicability_complete': not unresolved,
        'seed_artifact_ids': list(closure.seeds.artifact_ids),
        'artifact_ids': list(closure.artifact_ids), 'resource_ids': list(closure.resource_ids),
        'artifacts': [bindings[key] for key in closure.artifact_ids],
        'required_dependencies': required, 'external_required_dependencies': external,
        'external_required_artifact_ids': sorted({row['target_id'] for row in external}),
        'external_membership_basis': 'release_seed_artifact_ids',
        'scope_resolution': closure.data, 'scope_resolution_sha256': closure.observation_sha256,
        'validation_scope': 'release_closure_over_supplied_bound_inputs',
        'scope_providers_authenticated': False, 'project_files_verified': False,
        'full_validation_passed': False, 'release_closure_evaluated': True,
        'applicability_evaluated': configuration_id is not None,
        'done_evidence_evaluated': False, 'verification_evaluated': False,
        'release_readiness_evaluated': False, 'write_authorized': False, 'approval_granted': False}
    result = object.__new__(ReleaseScope)
    object.__setattr__(result, '_encoded', canonical_json_bytes(data))
    return result
