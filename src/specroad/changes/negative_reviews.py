"""Bound negative-review candidates and their exact approval withdrawals.

Only the dedicated review operation may use these semantics. Ordinary target
diagnostics retain their gates; a review outcome remains a visible error.
"""
from dataclasses import dataclass

from ..diagnostics import assess_diagnostics
from ..graph.relation_obligations import RelationObligations
from ..graph.review_status import RelationReviewStatuses
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.identity_values import artifact_identity
from ..profiles.composition_values import EffectiveProfile
from ._common import _artifact
from ._fold_inputs import (_inventory, _relation_inventory, _preflight, _files,
                          _check_expected, _owned_sequence)
from ._metadata_policy import bind_policy, select_policy
from ._patch_values import _snapshot
from .metadata_values import MetadataArtifact
from .review_record import review_context, review_time, prepare_review_record
from .target_values import TargetError
from .values import ChangeOperation
from ._review_outcome_gates import (WITHDRAWAL_GATE, _sources,
    prepare_review_outcome_gates, prepare_negative_review_gates)


def required_review_withdrawals(artifacts, source_id, relation_id, *, profile):
    """Recompute affected approved Requirements from actual composed rules.

    Unsupported non-Requirement withdrawals fail closed. Existing approval
    authenticity is supplied by the host, never inferred from these fields.
    """
    if type(profile) is not EffectiveProfile:
        raise TargetError('review_withdrawal_profile_required')
    state, _, _ = _inventory(artifacts, ())
    _relation_inventory(state, ())
    review_context(list(state.values()), source_id, relation_id)
    sources = _sources(state.values())
    statuses = RelationReviewStatuses(sources)
    by_relation = {value.relation_id: value for value in statuses.statuses}
    checks = RelationObligations(sources, profile_rules=profile.minimum_relation_rules()).checks
    mandatory = [check for check in checks if check.minimum > 0 and check.severity == 'error'
                 and state[check.artifact_id]['maturity'] == 'approved']
    affected = {check.artifact_id for check in mandatory if relation_id in check.relation_ids}
    withdrawals = []
    for identity in sorted(affected):
        artifact = state[identity]
        if artifact['artifact_type'] != 'requirement':
            raise TargetError('review_withdrawal_target_requires_specialized_service')
        relevant = [check for check in mandatory if check.artifact_id == identity]
        if any(not check.satisfied for check in relevant):
            raise TargetError('review_approval_baseline_incomplete')
        if any(by_relation[key].status != 'current' for check in relevant for key in check.relation_ids):
            raise TargetError('review_approval_baseline_not_current')
        withdrawals.append({'target': identity, 'reason': 'mandatory_relation_not_current',
            'expected_revision': artifact['revision'], 'expected_sha256': canonical_json_sha256(artifact)})
    return withdrawals


def prepare_negative_review_record(context, identity, *, actor, planned_at, reason, comment=None):
    record = prepare_review_record(context, identity, actor=actor, planned_at=planned_at,
                                   decision='confirmed', reason=reason, comment=comment)
    record['decision'] = 'rejected'
    _artifact(record, '/record', 'relation_review')
    return record


@dataclass(frozen=True)
class _NegativeCandidates:
    _model: object
    candidates: tuple
    _decisions: object
    _history: tuple
    review_diagnostics: tuple

    @property
    def artifacts(self): return self._model.data
    @property
    def metadata_applied(self): return True
    @property
    def decisions(self): return self._decisions.data
    @property
    def previously_approved_ids(self): return list(self._history)


def prepare_negative_review_candidates(artifacts, operations, *, metadata_policy_version,
        actor, planned_at, profile, preconditions=(), source_files=None,
        reserved_artifact_ids=(), reserved_relation_ids=(), previously_approved_ids=()):
    ops = [ChangeOperation(v).data for v in _owned_sequence(operations, '/operations')]
    if len(ops) != 1 or ops[0]['op'] != 'relation_review_record' or ops[0]['record']['decision'] != 'rejected':
        raise TargetError('one_negative_review_operation_required')
    metadata = bind_policy(metadata_policy_version, actor, planned_at)
    history = _owned_sequence(previously_approved_ids, '/previously_approved_ids')
    reserved = _owned_sequence(reserved_artifact_ids, '/reserved_artifact_ids')
    state, seen, prefixes = _inventory(artifacts, [*reserved, *history])
    _relation_inventory(state, reserved_relation_ids)
    _preflight(state, preconditions, _files(source_files))
    value = ops[0]; record = value['record']
    if not {'expected_revision', 'expected_sha256'} & value.keys():
        raise TargetError('review_source_guard_required', pointer='/operations/0')
    context = review_context(list(state.values()), value['source'], record['relation_id'])
    _check_expected(state[value['source']], value)
    if value['target'] != context.target.artifact_id:
        raise TargetError('review_target_binding_mismatch')
    identity = artifact_identity(record)
    if identity.id in seen:
        raise TargetError('review_identity_exists', pointer='/record/id')
    if prefixes and identity.id_prefix not in prefixes:
        raise TargetError('mixed_project_prefix', pointer='/record/id')
    if review_time(list(state.values()), context, planned_at) != planned_at:
        raise TargetError('review_timestamp_not_newest', pointer='/planned_at')
    expected = prepare_negative_review_record(context, identity, actor=metadata['actor'],
        planned_at=planned_at, reason=record.get('reason'), comment=record.get('comment'))
    if canonical_json_bytes(record) != canonical_json_bytes(expected):
        raise TargetError('review_record_binding_mismatch', pointer='/record')
    withdrawals = required_review_withdrawals(list(state.values()), value['source'],
        record['relation_id'], profile=profile)
    if canonical_json_bytes(value['approval_withdrawals']) != canonical_json_bytes(withdrawals):
        raise TargetError('review_withdrawal_set_mismatch', pointer='/approval_withdrawals')
    candidates, decisions = [], []
    for withdrawal in withdrawals:
        old = state[withdrawal['target']]
        candidate = {**old, 'maturity': 'proposed'}
        disposition, fields = select_policy(metadata_policy_version).fields(old, candidate, metadata, old['id'])
        candidate.update(fields)
        _artifact(candidate, '/approval_withdrawals/' + old['id'])
        state[old['id']] = candidate
        candidates.append(MetadataArtifact(old['id'], _snapshot(candidate),
            canonical_json_sha256(old), canonical_json_sha256(candidate), (0,), disposition))
        decisions.append({'artifact_id': old['id'], 'base_revision': old['revision'],
            'target_revision': candidate['revision'], 'from': 'approved', 'to': 'proposed',
            'relation_id': record['relation_id'], 'review_id': record['id'],
            'reason': 'mandatory_relation_not_current'})
    state[identity.id] = expected
    candidates.append(MetadataArtifact(identity.id, _snapshot(expected), None,
        canonical_json_sha256(expected), (0,), 'created'))
    statuses = RelationReviewStatuses(_sources(state.values()))
    selected = statuses.for_relation(value['source'], record['relation_id'])
    if selected.selected_review_id != record['id'] or selected.reason != 'current_review_rejected':
        raise TargetError('review_timestamp_not_newest')
    # Lifecycle-only withdrawals must preserve the newly recorded J context.
    after_context = review_context(list(state.values()), value['source'], record['relation_id'])
    if (after_context.relation_sha256 != context.relation_sha256
            or after_context.source.context_sha256 != context.source.context_sha256
            or after_context.target.context_sha256 != context.target.context_sha256):
        raise TargetError('review_withdrawal_context_changed')
    approved = tuple(sorted(set(history) | {a['id'] for a in artifacts if a['maturity'] == 'approved'}))
    return _NegativeCandidates(_snapshot([state[key] for key in sorted(state)]),
        tuple(sorted(candidates, key=lambda item: item.id)), _snapshot(decisions), approved,
        statuses.diagnostics)


def review_assessment(folded, *, fail_on='error', strict=False):
    assessment = assess_diagnostics(folded.review_diagnostics,
        checked_ids=tuple(a['id'] for a in folded.artifacts), complete=True,
        fail_on=fail_on, strict=strict).as_dict()
    return {**assessment, 'validation_scope': 'supplied_relation_review_status_only'}
