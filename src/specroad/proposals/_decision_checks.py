"""Reobserve historical authority at every writer gate, including after publish."""
from dataclasses import replace
from hashlib import sha256

from ..model.canonical import canonical_json_bytes
from ..validation import ModelGate
from ..validation.values import HOOK_NAMES
from .context import ProposalContext
from .history import ProposalInputs
from .observations import ProposalVerification, ProposalVerifier
from ._review_checks import _initial_inputs
from ._decision_control import GATE, read_review_observations
from ._decision_evidence import assessment, operation_proof
from .values import require


def gates(snapshot, original, after, operation, actor, planned_at, services):
    from ..recovery._validation import validate_project
    old = _initial_inputs(snapshot.model, original, services)
    require(type(old) is ProposalInputs, 'proposal_native_inputs_required')
    context = ProposalContext(original, snapshot.model)
    raw, report = operation_proof(operation)
    review, controls = read_review_observations(after, context)
    added = (review, *controls)
    require(review.reviewer.as_fields() == actor and review.reviewed_at.value == planned_at,
            'proposal_live_review_binding_changed', exit_code=6)

    def verify(inputs):
        item = inputs.observation
        if item in added:
            require(item.original.source_bytes == after.source_bytes and item.context == context
                and inputs.native_result == canonical_json_bytes(report['native_check']),
                'proposal_live_review_binding_changed', exit_code=6)
            return ProposalVerification(inputs.sha256, sha256(item.row_bytes).hexdigest(),
                True, True, item == review and review.decision == 'approved')
        return old.verifier.check(inputs)

    extended = ProposalInputs((*old.originals, after),
        (*old.contexts, ProposalContext(after, snapshot.model)), (*old.reviews, review),
        (*old.controls, *controls), ProposalVerifier('native-live-human-review', '1', verify), old.publications)

    def provider(model, value):
        if value.binding.proposal_id == after.binding.proposal_id:
            require(value.source_bytes == after.source_bytes, 'proposal_target_changed', exit_code=6)
            return extended
        return _initial_inputs(model, value, services)

    qualified = replace(services, proposal_inputs=provider)
    files = {**snapshot.raw, after.path: after.source_bytes}
    expected = {d.path: (after.source_bytes if d.path == after.path else d.content)
                for d in snapshot.model.documents}

    def dependencies(context):
        return context.dependency_result({identity: list(context.all_ids) for identity in context.subjects})

    def check(context):
        require({d.path: d.content for d in context.documents} == expected,
                'proposal_review_target_changed', exit_code=6)
        # Stored hashes alone cannot authenticate a past human or a fresh quorum.
        require(assessment(snapshot, original, services) == raw,
                'proposal_review_authority_changed', exit_code=6)
        validate_project(files, services=qualified)
        return context.result()

    return tuple(ModelGate(name, 'proposal-review-native-v1', dependencies, check,
        snapshot.model._sources_sha256) for name in (
            *(name for name in HOOK_NAMES if name not in ('profile_lint', 'language_policy')),
            GATE, 'extension:target-resources'))
