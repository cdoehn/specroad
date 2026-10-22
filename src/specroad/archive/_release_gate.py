"""Native Release admission inside every ordinary target/publication recheck.

The existing model remains byte-identical when a sealed Baseline is appended.
Its semantic providers are evaluated on those original bytes; the new record
and the entire target are independently recomputed and exactly bound. This
preserves existing Task/Requirement reviews without certifying a changed model.
"""
from dataclasses import dataclass

from ..changes.baselines import prepare_baseline_candidates, object_documents
from ..changes._target_materialization import validation_resources
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.paths import artifact_path
from ..storage.json_syntax import parse_json_object
from ..validation import ModelGate, validate_model
from ._release_snapshot import release_selection
from .readiness import _native_readiness

RELEASE_GATE = 'extension:release-baseline'


@dataclass(frozen=True)
class _ReleaseAdmission:
    model: object
    release_id: str
    context: object
    _gates: tuple
    reviews: tuple
    verifier: object

    def require_ready(self):
        if self.context is None:
            raise ModelError('release_baseline_readiness_required')
        fresh = _native_readiness(self.model, self.release_id, self.context,
                                 self._gates, self.reviews, self.verifier)
        if not fresh.data['ready'] or fresh.data['provisional']:
            raise ModelError('release_baseline_readiness_required')
        return fresh


@dataclass(frozen=True)
class _ReleaseBaselineCheck:
    model: object
    operation_bytes: bytes
    readiness: object
    gate_id: str

    def __call__(self, target):
        value = parse_json_object(self.operation_bytes)
        record = value['record']
        owned = self.model.snapshot()
        folded = prepare_baseline_candidates(owned, [value], metadata_policy_version='change-metadata-v1',
            actor=record['created_by'], planned_at=record['created_at'])
        expected = {a['id']: a for a in folded.artifacts}
        documents = {d.path: d.content for d in owned.documents}
        documents[artifact_path('baseline', record['id'], owned.configuration.id_prefix)] = canonical_json_bytes(record)
        if (expected != {key: target.artifact(key) for key in target.all_ids}
                or documents != {d.path: d.content for d in target.documents}
                or target.profile_data != owned.profile.data):
            raise ModelError('release_baseline_target_changed')
        if self.gate_id == RELEASE_GATE:
            # Never reuse the report's ready flag. Re-evaluate all eight gates,
            # including current human reviews, at every publication boundary.
            fresh = self.readiness.require_ready()
            selected = release_selection(record, {d.path: d.content for d in object_documents(value)})
            if (fresh.data['binding']['scope_descriptor'] != selected['scope_descriptor']
                    or fresh.data['binding']['evaluation_sha256'] != selected['evaluation_sha256']
                    or fresh.data['selection']['stored_evaluation'] != selected['verification_evaluation']):
                raise ModelError('release_baseline_readiness_binding_mismatch')
            archived = {r['id'] for r in record['manifest'] if r['role'] == 'artifact'}
            if not set(fresh.data['binding']['release_scope']['artifact_ids']) <= archived:
                raise ModelError('release_baseline_required_artifact_not_archived')
            return target.result()
        # Rebind every host observation to this exact target check. Wrapping a
        # provider does not allow a previously bound GateResult to be replayed.
        bound = tuple(ModelGate(g.gate_id, g.version, g.dependencies, g.check,
            canonical_json_sha256({'target_input_sha256': target.input_sha256,
                'provider_resources_sha256': g.resources_sha256})) for g in self.readiness._gates)
        report = validate_model(owned.documents, profile=owned.profile, gates=bound,
                                resources=validation_resources(owned))
        stage = next((s for s in report.data['stages'] if s['stage'] == self.gate_id), None)
        subjects = set(target.subjects) - {record['id']}
        if (stage is None or stage['status'] not in ('passed', 'not_applicable')
                or not subjects <= set(stage['checked_ids'])):
            return target.result([{'reason': 'release_baseline_existing_gate_required',
                'gate_id': self.gate_id, 'severity': 'error', 'observation': stage}])
        return target.result(stage['diagnostics'])


def release_baseline_gates(model, operation, *, readiness_context, gates=(),
                           blocker_reviews=(), blocker_verifier=None):
    owned = model.snapshot()
    selected = release_selection(operation['record'],
        {d.path: d.content for d in object_documents(operation)})
    from ..planning.readiness import ReleaseReadinessContext
    from ..planning.release_blockers import blocker_review_inputs
    if readiness_context is not None and type(readiness_context) is not ReleaseReadinessContext:
        raise ModelError('typed_release_readiness_context_required')
    if type(gates) not in (tuple, list) or any(type(g) is not ModelGate for g in gates):
        raise ModelError('release_readiness_native_gates_required')
    gates = tuple(gates)
    if len({g.gate_id for g in gates}) != len(gates):
        raise ModelError('target_distinct_registered_gates_required')
    reviews, review_binding = blocker_review_inputs(blocker_reviews, blocker_verifier)
    readiness = _ReleaseAdmission(owned, selected['release_id'], readiness_context,
        gates, tuple(reviews[key] for key in sorted(reviews)), blocker_verifier)
    if any(g.gate_id == RELEASE_GATE for g in gates):
        raise ModelError('release_baseline_reserved_gate')
    raw = canonical_json_bytes(operation)
    # Defer actual admission to the ordinary writer's target recheck. Its
    # durable receipt replay must stay available even after later revocation.
    binding = canonical_json_sha256({'operation': operation,
        'readiness_input': None if readiness_context is None else readiness_context.input_sha256,
        'blocker_reviews': review_binding,
        'providers': [{'id': g.gate_id, 'version': g.version, 'resources': g.resources_sha256} for g in gates],
                                    'model_sources_sha256': owned._sources_sha256})

    def dependencies(target):
        return target.dependency_result({key: list(target.all_ids) for key in target.subjects})

    names = {g.gate_id for g in gates} | {'lifecycle', 'baseline_integrity', RELEASE_GATE}
    return tuple(ModelGate(name, 'native-release-baseline-v1', dependencies,
        _ReleaseBaselineCheck(owned, raw, readiness, name), binding) for name in sorted(names))


def require_release_baseline_gate(gates, plan):
    """A same-named callback is not the native M13 integration."""
    providers = [g for g in gates if g.gate_id == RELEASE_GATE]
    if len(providers) != 1 or type(providers[0].check) is not _ReleaseBaselineCheck:
        raise ModelError('release_baseline_readiness_required')
    check = providers[0].check
    if check.gate_id != RELEASE_GATE or check.operation_bytes != canonical_json_bytes(plan.data['operations'][0]):
        raise ModelError('release_baseline_readiness_binding_mismatch')
