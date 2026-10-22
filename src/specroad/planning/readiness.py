"""Eight fixed Release gates over native, explicitly bound read observations.

Trusted hosts supply the existing ModelGate services (including lifecycle,
Requirement review and Task Done). Their results are rebound to this complete
readiness input. Project data cannot install a provider or supply a pass flag.
Blocker completion requires an exact, currently authenticated human review;
a terminal label is not proof. This does not open the Release baseline gate.
"""
from dataclasses import dataclass

from ..changes import TargetModel
from ..graph.scope_descriptors import ScopeDescriptor
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.waiver_fields import waiver_time
from ..storage.json_syntax import parse_json_object
from ..validation import ModelGate
from ..verification import prepare_verification_read_input
from ..verification._read_evaluation import resolve_read_evaluation
from ..verification.read_input import VerificationReadBindingConflict
from .release_scope import resolve_release_scope
from ._readiness_policy import readiness_policy
from .release_blockers import blocker_review_inputs
from ._readiness_decisions import GATES, GateDecision, ReadinessBinding
from ._readiness_gates import (IMPLEMENTED, VERIFIED, expected_subjects, assess_scope,
    assess_artifacts, assess_validation, assess_verification, assess_blockers, assess_relations)
from ._readiness_projection import readiness_report

@dataclass(frozen=True, init=False)
class ReleaseReadinessContext:
    """An owned model and evaluation, not an attestation of live disk currency."""
    _encoded: bytes
    _work_encoded: bytes
    _model: TargetModel
    _verification: object

    def __init__(self, model, release_id, *, scope_bindings, evaluated_at,
                 configuration_id=None, evaluation=None, inputs=None, input_roles=None,
                 waiver_reviews=None, waiver_verifier=None):
        if type(model) is not TargetModel:
            raise ModelError('release_readiness_target_model_required')
        model = model.snapshot()
        waiver_time(evaluated_at)
        descriptor = ScopeDescriptor({'scope_version': 'scope-v1', 'scope_kind': 'release',
            'selector': {'release_id': release_id}, 'configuration_id': configuration_id,
            'closure_profile': 'core-closure-v1', 'boundary_policy': 'closed'})
        # Native stored-selection precedence also applies to legacy policies.
        evaluation, selection = resolve_read_evaluation(model, evaluation, descriptor,
            conflict_type=VerificationReadBindingConflict)
        release = next(v for v in model.artifacts if v['id'] == release_id)
        policy, policy_reason = readiness_policy(release['readiness_policy'])
        scope = None
        scope_error = None
        try:
            scope = resolve_release_scope(model, release_id, scope_bindings=scope_bindings,
                                          configuration_id=configuration_id).data
        except ModelError as error:
            scope_error = {'reason': error.reason, 'diagnostic': error.diagnostic()}
        verification = None
        if scope is not None:
            verification = prepare_verification_read_input(model, evaluation,
                configuration_id=configuration_id, inputs=inputs, input_roles=input_roles,
                evaluated_at=evaluated_at, scope_descriptor=descriptor, scope_bindings=scope_bindings,
                waiver_reviews=waiver_reviews, waiver_verifier=waiver_verifier)
        binding = {'release_id': release_id, 'model_sources_sha256': model._sources_sha256,
            'model_resources_sha256': model.resources_sha256,
            'scope_descriptor': descriptor.data, 'release_scope': scope,
            # Blocker decisions bind the effective parent manifest, as native
            # Verification does; the Scope hash also includes project config.
            'configuration_sha256': None if verification is None else verification.data['configuration_hash'],
            'policy_sha256': canonical_json_sha256(policy),
            'evaluation_sha256': None if evaluation is None else evaluation.sha256,
            'verification_input_sha256': None if verification is None else verification.sha256,
            'evaluated_at': evaluated_at}
        data = {'binding': binding, 'policy': policy, 'policy_reason': policy_reason,
            'scope_error': scope_error, 'selection': selection,
            'input_sha256': canonical_json_sha256(binding)}
        object.__setattr__(self, '_encoded', canonical_json_bytes(data))
        object.__setattr__(self, '_work_encoded', canonical_json_bytes({
            'format_version': 'release-readiness-work-input-v1',
            'release_id': release_id, 'configuration_id': configuration_id,
            'evaluation': None if evaluation is None else evaluation.data,
            'evaluation_sha256': None if evaluation is None else evaluation.sha256,
            'evaluated_at': evaluated_at, 'input_sha256': data['input_sha256']}))
        object.__setattr__(self, '_model', model)
        object.__setattr__(self, '_verification', verification)

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def input_sha256(self):
        return self.data['input_sha256']

    @property
    def work_input(self):
        """Semantic input only; no saved gates, approval or executable provider.

        The Work host retains the model/product bytes separately. Restoring a
        context requires fresh native scope and review services, just as the
        synchronous call does. A context is still not a readiness result.
        """
        return self._work_encoded

    def __bool__(self):
        raise TypeError('A readiness context is not a release decision')


@dataclass(frozen=True, init=False)
class ReleaseReadiness:
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use assess_release_readiness')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return canonical_json_sha256(self.data)

    @property
    def exit_code(self):
        return 0 if self.data['ready'] else 3

    def __bool__(self):
        raise TypeError('Readiness is not a lifecycle or publication permit')


def assess_release_readiness(context, *, gates=(), blocker_reviews=(), blocker_verifier=None):
    """Compute all gates, keeping unavailable providers and every blocker.

    ModelGate callbacks are explicitly trusted host code, as in the ordinary
    validator. A version or a callback's presence is not evidence: native gate
    results must cover all subjects and bind the exact current context. The
    host must use the actual lifecycle, Requirement-review and Done services;
    a JSON label, bool or previously bound GateResult cannot stand in for one.
    """
    if type(context) is not ReleaseReadinessContext:
        raise ModelError('typed_release_readiness_context_required')
    if type(gates) not in (tuple, list) or any(type(g) is not ModelGate for g in gates):
        raise ModelError('release_readiness_native_gates_required')
    data = context.data
    model = context._model
    reviews, review_binding = blocker_review_inputs(blocker_reviews, blocker_verifier)
    binding_data = {**data['binding'], 'providers': sorted([
        {'gate_id': g.gate_id, 'version': g.version, 'resources_sha256': g.resources_sha256}
        for g in gates], key=lambda g: g['gate_id'].encode('utf-8')),
        'blocker_review_inputs': review_binding}
    binding = ReadinessBinding.from_value(binding_data)
    scope = binding_data['release_scope']
    records = {v['id']: v for v in model.artifacts}
    release_id = binding_data['release_id']
    complete = scope is not None and scope['scope_applicability_complete']
    ids = [release_id] if scope is None else scope['artifact_ids']
    expected = expected_subjects(records, release_id, ids)
    rows = {key: GateDecision(key, binding, sorted(expected[key])) for key in GATES}

    assess_scope(data, binding_data, records, rows, complete=complete)
    assess_artifacts(records, expected, rows)
    assess_validation(model, binding, gates, ids, rows)
    assess_verification(model, context._verification, expected, ids, rows)
    assess_blockers(data, binding, records, expected, reviews, blocker_verifier, rows)
    assess_relations(model, ids, rows)

    report = readiness_report(binding, data['selection'], rows, complete=complete)
    value = object.__new__(ReleaseReadiness)
    object.__setattr__(value, '_encoded', canonical_json_bytes(report))
    return value
