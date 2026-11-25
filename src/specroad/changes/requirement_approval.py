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

from ._requirement_approval_fold import (APPROVAL_GATE, APPROVAL_BINDING,
    approval_mode, bind_requirement_approval, prepare_requirement_candidates,
    prepare_plan_requirement)


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
            statuses = {s.relation_id: s.status for s in RelationReviewStatuses(sources, force_provenance=model.force_provenance).statuses}
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
