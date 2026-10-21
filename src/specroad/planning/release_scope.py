"""Bound Release seeds and closure over an explicitly supplied project.

External means outside the selected Release's native seed membership, not
outside its expanded closure. Dependencies retain their stored direction and
identity. This observation does not evaluate readiness or authorize a release.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..changes import TargetModel
from ..graph.relations import SourceRelations
from ..graph.scope_descriptors import ScopeDescriptor
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from ..verification._required_scope import resolve_required_scope
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

    values, bindings = {}, {}
    for record in records:
        value = parse_json_object(record.source_bytes)
        key = value['id']
        values[key] = value
        bindings[key] = {'artifact_id': key, 'artifact_type': value['artifact_type'],
            'revision': value['revision'], 'path': record.path,
            'source_sha256': sha256(record.source_bytes).hexdigest(),
            'record_sha256': canonical_json_sha256(value)}
    required = []
    for key in closure.artifact_ids:
        for position, relation in enumerate(values[key]['relations']):
            if relation['type'] != 'depends_on':
                continue
            target = relation['target']
            required.append({'relation_id': relation['relation_id'], 'type': 'depends_on',
                'source_id': key, 'target_id': target,
                'path': bindings[key]['path'], 'pointer': '/relations/' + str(position),
                'source_sha256': bindings[key]['source_sha256'],
                'relation_sha256': canonical_json_sha256(relation),
                'target_record_sha256': bindings[target]['record_sha256'],
                'source_is_release_seed': key in seeds, 'target_is_release_seed': target in seeds,
                'external': target not in seeds})
    required.sort(key=lambda row: (row['source_id'], row['target_id'], row['relation_id']))
    external = [row for row in required if row['external']]
    plan = planning.data
    data = {'format_version': 'release-scope-v1', 'generated': True, 'normative': False,
        'project_id': plan['project_id'], 'release_id': release_id,
        'input_sha256': model._sources_sha256,
        'project_model_root_sha256': plan['model_root_sha256'],
        'planning_sha256': planning.sha256, 'scope_descriptor': descriptor.data,
        'scope_descriptor_sha256': descriptor.sha256,
        'configuration_hash': closure.seeds.configuration_sha256,
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
