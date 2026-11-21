"""Native isolated Requirement approval; every publication rechecks real services.

The host supplies authenticated review observations and current semantic services.
Plan metadata carries hashes, never callbacks, authority or a cached success bit.
The passive fold below is not a current approval or permission to publish.
"""
from dataclasses import dataclass, replace
import re

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.paths import artifact_path
from ..storage.json_syntax import parse_json_object
from ..validation import (ApprovalContext, HumanRequirementReview, ReviewVerifier,
    ModelGate, assess_requirement_approval)
from .values import ChangeOperation
from .lifecycle_values import LifecycleError, LifecycleResult
from .request_ids import AuthoringError
from ._metadata_policy import bind_policy
from ._metadata_materialize import apply_policy
from ._fold_inputs import _inventory, _preflight, _files
from ._fold_results import _finish
from ._patch_values import _snapshot
from .lifecycle import _history, lifecycle_content_sha256

APPROVAL_GATE = 'extension:requirement-approval'
APPROVAL_BINDING = 'requirement-approval-v1'


def approval_mode(operations):
    return any(op['op'] == 'transition' and op['to'] == 'approved'
        and 'requirement_approval' in op['metadata'] for op in operations)


def bind_requirement_approval(operation, context, review):
    """Bind observations as passive plan data; this does not evaluate a gate."""
    if (type(operation) is not ChangeOperation or type(context) is not ApprovalContext
            or type(review) is not HumanRequirementReview):
        raise LifecycleError('approval_typed_inputs_required')
    value = operation.data
    if (value['op'] != 'transition' or value['from'] != 'in_review'
            or value['to'] != 'approved' or value['target'] != context.requirement_id):
        raise LifecycleError('approval_isolated_requirement_transition_required')
    value['metadata'] = {**value['metadata'], 'requirement_approval': {
        'version': APPROVAL_BINDING, 'input_sha256': context.input_sha256,
        'review_sha256': review.sha256}}
    return ChangeOperation(value)


def _operation(model, operations, actor):
    if len(operations) != 1:
        raise LifecycleError('approval_isolated_requirement_transition_required')
    operation = ChangeOperation(operations[0]).data
    before = next((a for a in model.artifacts if a['id'] == operation.get('target')), None)
    if (operation['op'] != 'transition' or operation['from'] != 'in_review'
            or operation['to'] != 'approved' or before is None
            or before['artifact_type'] != 'requirement' or before['maturity'] != 'in_review'):
        raise LifecycleError('approval_isolated_requirement_transition_required')
    binding = operation['metadata'].get('requirement_approval')
    if (type(binding) is not dict or set(binding) != {'version', 'input_sha256', 'review_sha256'}
            or binding['version'] != APPROVAL_BINDING
            or any(type(binding[k]) is not str or re.fullmatch('[0-9a-f]{64}', binding[k]) is None
                   for k in ('input_sha256', 'review_sha256'))):
        raise LifecycleError('approval_metadata_binding_required')
    if actor['actor_type'] != 'human':
        raise AuthoringError('approval_human_actor_required', exit_code=7)
    return operation, before


def prepare_requirement_candidates(model, operations, *, metadata_policy_version,
        actor, planned_at, preconditions=()):
    """Pure exact transform, selected only for an isolated bound approval intent.

    Current review eligibility is checked by the mandatory native target gate.
    Historical readers can reconstruct the declared transform without claiming
    that the old review is still valid. No ordinary lifecycle fold is relaxed.
    """
    metadata = bind_policy(metadata_policy_version, actor, planned_at)
    operation, before = _operation(model, operations, metadata['actor'])
    history = _history(model.previously_approved_ids)
    base, _, _ = _inventory(model.artifacts, [*model.reserved_artifact_ids, *history])
    checked = _preflight(base, preconditions, _files(model.source_files))
    identity = before['id']
    state = {**base, identity: {**before, 'maturity': 'approved'}}
    folded = _finish(state, base, {identity: [0]}, 1, checked, hasher=canonical_json_sha256)
    prepared = apply_policy(base, folded, metadata)
    content_hash = lifecycle_content_sha256(before)
    decisions = [{'artifact_id': identity, 'base_maturity': 'in_review',
        'final_maturity': 'approved', 'base_content_sha256': content_hash,
        'final_content_sha256': content_hash, 'content_changed': False,
        'approval_withdrawn': False, 'withdrawal_reason': None, 'operation_indices': [0]}]
    events = [{'operation_index': 0, 'target': identity, 'from': 'in_review',
        'to': 'approved', 'actor': metadata['actor'], 'planned_at': metadata['planned_at'],
        'metadata': operation['metadata']}]
    return LifecycleResult(prepared, _snapshot(decisions), _snapshot(events),
        _history=_snapshot(sorted(set(history) | {a['id'] for a in base.values()
                                                if a['maturity'] == 'approved'})))


def prepare_plan_requirement(plan, model, *, observed_base_root, observed_scope):
    value = plan.data
    if (value['base']['model_root_sha256'] != observed_base_root
            or value['base']['scope_descriptor'] != observed_scope):
        raise LifecycleError('approval_plan_basis_mismatch')
    folded = prepare_requirement_candidates(model, value['operations'],
        metadata_policy_version=value['metadata_policy_version'], actor=value['actor'],
        planned_at=value['planned_at'], preconditions=value['preconditions'])
    if {c.id: c.candidate_sha256 for c in folded.candidates} != {
            r['artifact']['id']: r['sha256'] for r in value['result_artifacts']}:
        raise LifecycleError('declared_approval_result_mismatch')
    return replace(folded, plan_sha256=plan.sha256, declared_artifacts_verified=True)


@dataclass(frozen=True)
class ApprovalPrerequisiteProvider:
    """Explicit trusted code registration; called afresh with the exact context."""
    provider_id: str
    version: str
    check: object

    def __post_init__(self):
        if (any(type(v) is not str or not v.strip() for v in (self.provider_id, self.version))
                or not callable(self.check)):
            raise ModelError('approval_prerequisite_provider_required')


@dataclass(frozen=True)
class _RequirementApprovalCheck:
    model: object
    operation_bytes: bytes
    metadata_bytes: bytes
    context: ApprovalContext
    review: HumanRequirementReview
    verifier: ReviewVerifier
    provider: ApprovalPrerequisiteProvider
    gate_id: str

    def __call__(self, target):
        model = self.model.snapshot()
        operation = parse_json_object(self.operation_bytes)
        metadata = parse_json_object(self.metadata_bytes)
        context = self.context
        if (context.data['mode'] != 'transition'
                or {d.path: d.content for d in context.documents} != {d.path: d.content for d in model.documents}
                or context.profile is None or context.profile.binding() != model.profile.binding()
                or context.data['configuration'] != model.configuration.data
                or operation['target'] != context.requirement_id
                or operation['metadata']['requirement_approval'] != {
                    'version': APPROVAL_BINDING, 'input_sha256': context.input_sha256,
                    'review_sha256': self.review.sha256}):
            raise ModelError('approval_context_binding_mismatch')
        folded = prepare_requirement_candidates(model, [operation], **metadata)
        expected = {a['id']: a for a in folded.artifacts}
        documents = {d.path: d.content for d in model.documents}
        for candidate in folded.candidates:
            documents[artifact_path(candidate.data['artifact_type'], candidate.id,
                                    model.configuration.id_prefix)] = canonical_json_bytes(candidate.data)
        if (expected != {key: target.artifact(key) for key in target.all_ids}
                or documents != {d.path: d.content for d in target.documents}
                or target.profile_data != model.profile.data):
            raise ModelError('approval_target_binding_mismatch')
        if self.gate_id == APPROVAL_GATE:
            try:
                observations = self.provider.check(context)
                assessment = assess_requirement_approval(context, review=self.review,
                    verifier=self.verifier, prerequisites=observations)
            except Exception:
                return target.result([{'reason': 'approval_prerequisite_service_unavailable',
                    'severity': 'error', 'artifact_id': context.requirement_id}])
            if not assessment.eligible_for_human_approval:
                return target.result([{'reason': 'requirement_approval_not_eligible', 'severity': 'error',
                    'artifact_id': context.requirement_id, 'assessment': assessment.data}])
            # An arbitrary service observation cannot waive native currentness.
            from ..graph.relations import SourceRelations
            from ..graph.review_status import RelationReviewStatuses
            from ..graph.relation_obligations import RelationObligations
            sources = tuple(SourceRelations(canonical_json_bytes(a)) for a in folded.artifacts)
            statuses = {s.relation_id: s.status for s in RelationReviewStatuses(sources).statuses}
            checks = RelationObligations(sources, profile_rules=model.profile.minimum_relation_rules()).checks
            if any(c.artifact_id == context.requirement_id and c.minimum > 0 and c.severity == 'error'
                   and (not c.satisfied or any(statuses[r] != 'current' for r in c.relation_ids)) for c in checks):
                return target.result([{'reason': 'approval_mandatory_relation_not_current',
                    'severity': 'error', 'artifact_id': context.requirement_id}])
        else:
            # Only the single subject and byte-unchanged stored relation reviews
            # have a native lifecycle service here. Unrelated subjects require
            # their own explicitly supplied host gates; never certify them.
            allowed = {context.requirement_id} | {a['id'] for a in model.artifacts
                                                if a['artifact_type'] == 'relation_review'}
            if not set(target.subjects) <= allowed:
                return target.result([{'reason': 'approval_unrelated_service_required', 'severity': 'error'}])
        return target.result()


def requirement_approval_gates(model, operation, *, actor, planned_at, context,
        review, verifier, prerequisite_provider, gates=()):
    """Register the native approval gate; leave unrelated host failures intact."""
    from .target_model import TargetModel
    if (type(model) is not TargetModel or type(operation) is not ChangeOperation
            or type(context) is not ApprovalContext or type(review) is not HumanRequirementReview
            or type(verifier) is not ReviewVerifier
            or type(prerequisite_provider) is not ApprovalPrerequisiteProvider
            or type(gates) not in (tuple, list) or any(type(g) is not ModelGate for g in gates)):
        raise LifecycleError('approval_typed_inputs_required')
    owned = model.snapshot()
    metadata = bind_policy('change-metadata-v1', actor, planned_at)
    # Keep registration passive: the writer must resolve a confirmed original
    # receipt before checking the source maturity or current review services.
    # A fresh plan still calls _operation and requires a human in_review source.
    if len({g.gate_id for g in gates}) != len(gates) or any(g.gate_id == APPROVAL_GATE for g in gates):
        raise LifecycleError('approval_reserved_or_duplicate_gate')
    binding = canonical_json_sha256({'model': owned._sources_sha256, 'operation': operation.data,
        'metadata': metadata, 'context': context.input_sha256, 'review': review.sha256,
        'verifier': [verifier.verifier_id, verifier.version],
        'provider': [prerequisite_provider.provider_id, prerequisite_provider.version]})
    def dependencies(target):
        return target.dependency_result({key: list(target.all_ids) for key in target.subjects})
    names = {APPROVAL_GATE, 'lifecycle', 'review_currentness'} - {g.gate_id for g in gates}
    return (*gates, *(ModelGate(name, APPROVAL_BINDING, dependencies,
        _RequirementApprovalCheck(owned, canonical_json_bytes(operation.data), canonical_json_bytes(metadata),
            context, review, verifier, prerequisite_provider, name), binding) for name in sorted(names)))


def approval_target_contexts(gates, documents, model):
    """Carry explicit quality/interface projections into the actual target check.

    The new stored-mode context grants nothing. The original transition context
    remains the only input accepted by the human and semantic admission gate.
    """
    return tuple(ApprovalContext(g.check.context.requirement_id, documents,
        profile=model.profile, configuration=model.configuration.data, mode='stored',
        quality_fields=g.check.context.data['quality_fields'],
        interface_fields=g.check.context.data['interface_fields'])
        for g in gates if type(g) is ModelGate and g.gate_id == APPROVAL_GATE
        and type(g.check) is _RequirementApprovalCheck)


def require_requirement_approval_gate(gates, operations, model, *, actor, planned_at):
    if not approval_mode(operations):
        return
    providers = [g for g in gates if type(g) is ModelGate and g.gate_id == APPROVAL_GATE]
    if len(providers) != 1 or type(providers[0].check) is not _RequirementApprovalCheck:
        raise LifecycleError('approval_gate_required')
    check = providers[0].check
    if (check.gate_id != APPROVAL_GATE or len(operations) != 1
            or check.operation_bytes != canonical_json_bytes(operations[0])
            or check.model._sources_sha256 != model._sources_sha256
            or check.metadata_bytes != canonical_json_bytes(bind_policy('change-metadata-v1', actor, planned_at))):
        raise LifecycleError('approval_gate_binding_mismatch')
