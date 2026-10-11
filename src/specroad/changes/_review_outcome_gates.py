"""Bound review outcome gates over an independently recomputed target.

Only status findings computed here can qualify as review outcome data. This
module preserves other write gates, subject boundaries and approval invariants.
It grants no publication authority and performs no storage operation.
"""
from ..graph.relation_obligations import RelationObligations
from ..graph.relations import SourceRelations
from ..graph.review_status import RelationReviewStatuses
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.paths import artifact_path
from ..model.record_contracts import SPECIAL_STATES
from ..validation import ModelGate
from ._metadata_policy import bind_policy
from .target_values import TargetError
from .values import ChangeOperation

WITHDRAWAL_GATE = 'extension:review-withdrawal'


def _sources(artifacts):
    return tuple(SourceRelations(canonical_json_bytes(a),
        path=artifact_path(a['artifact_type'], a['id'], a['id'].split('-')[0]))
        for a in artifacts)


def prepare_review_outcome_gates(model, operation, *, actor, planned_at):
    """Prove an isolated review, unchanged subjects and remaining obligations.

    The host supplies authentic prior state. Preserving a standard artifact is
    not a new approval; unsupported specialist lifecycle subjects stay closed.
    """
    owned = model.snapshot(); operation = ChangeOperation(operation.data)
    if operation.op != 'relation_review_record':
        raise TargetError('review_operation_required')
    metadata = bind_policy('change-metadata-v1', actor, planned_at)
    resources = canonical_json_sha256({'model_sources_sha256': owned._sources_sha256,
        'operation': operation.data, 'metadata': metadata})
    allowed = {a['id'] for a in owned.artifacts if a['artifact_type'] == 'relation_review'}
    allowed.add(operation.data['record']['id'])
    allowed.update(w['target'] for w in operation.data['approval_withdrawals'])
    allowed.update(a['id'] for a in owned.artifacts
        if a['artifact_type'] not in SPECIAL_STATES
        and (a['maturity'] != 'approved' or a['artifact_type'] == 'requirement'))

    def fold():
        # The positive fold refuses withdrawals; the negative fold independently
        # recomputes the entire required set. Both preserve every other byte.
        from .reviews import prepare_review_candidates
        return prepare_review_candidates(owned.artifacts, [operation.data],
            **metadata, profile=owned.profile, source_files=owned.source_files, **owned.reservations)

    def retained_approval_findings(artifacts):
        sources = _sources(artifacts)
        statuses = {s.relation_id: s for s in RelationReviewStatuses(sources).statuses}
        approved = {a['id'] for a in artifacts if a['maturity'] == 'approved'}
        checks = RelationObligations(sources, profile_rules=owned.profile.minimum_relation_rules()).checks
        return [{'reason': 'review_retained_approval_invalid', 'severity': 'error',
                 'artifact_id': c.artifact_id}
                for c in checks if c.artifact_id in approved and c.minimum > 0 and c.severity == 'error'
                and (not c.satisfied or any(statuses[key].status != 'current' for key in c.relation_ids))]

    def dependencies(context):
        return context.dependency_result({key: list(context.all_ids) for key in context.subjects})

    def check(context):
        folded = fold()
        expected = {a['id']: a for a in folded.artifacts}
        actual = {key: context.artifact(key) for key in context.all_ids}
        if canonical_json_sha256(expected) != canonical_json_sha256(actual):
            return context.result([{'reason': 'review_target_mismatch', 'severity': 'error'}])
        if not set(context.subjects) <= allowed:
            return context.result([{'reason': 'review_subjects_require_specialized_service', 'severity': 'error'}])
        return context.result()

    def outcomes(context):
        folded = fold()
        expected = {a['id']: a for a in folded.artifacts}
        if canonical_json_sha256(expected) != canonical_json_sha256(
                {key: context.artifact(key) for key in context.all_ids}):
            return context.result([{'reason': 'review_target_mismatch', 'severity': 'error'}])
        # These are freshly recomputed status observations, not findings supplied
        # by another gate. The complete error assessment is retained separately.
        findings = [dict(value.as_dict(), reason=value.rationale)
            for value in RelationReviewStatuses(_sources(folded.artifacts)).diagnostics
            if not (value.code == 'SRV027' and value.severity == 'error'
                    and value.category == 'review_outcome' and value.rationale == 'current_review_rejected')]
        findings.extend(retained_approval_findings(folded.artifacts))
        return context.result(findings)

    return (*tuple(ModelGate(name, 'bound-review-outcome-v1', dependencies, check, resources)
        for name in ('lifecycle', 'review_currentness')),
        ModelGate(WITHDRAWAL_GATE, 'bound-review-outcome-v1', dependencies, outcomes, resources))


def prepare_negative_review_gates(model, operation, *, actor, planned_at):
    """Retain the explicit negative-operation entry point."""
    value = ChangeOperation(operation.data).data
    if value['op'] != 'relation_review_record' or value['record']['decision'] != 'rejected':
        raise TargetError('one_negative_review_operation_required')
    return prepare_review_outcome_gates(model, operation, actor=actor, planned_at=planned_at)
