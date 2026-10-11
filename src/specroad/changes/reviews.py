"""Dedicated review dispatch; generic record mutation stays closed.

Explicit source guards, human actor, exact endpoint observations and regular
creation metadata are rechecked for saved plans as well as direct authoring.
Negative assessment/withdrawals use their separate bound service. No function
here grants publication authority or mutates a file.
"""
from dataclasses import dataclass

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.identity_values import artifact_identity
from ..validation import ModelGate
from ._fold_inputs import (_inventory, _relation_inventory, _preflight, _files,
                          _check_expected, _owned_sequence)
from ._metadata_policy import bind_policy
from ._patch_values import _snapshot
from .metadata_values import MetadataArtifact
from .review_record import review_context, review_time, prepare_review_record
from .target_values import TargetError
from .values import ChangeOperation


def review_mode(operations):
    selected = [op['op'] == 'relation_review_record' for op in operations]
    if any(selected) and (len(operations) != 1 or not all(selected)):
        raise TargetError('review_requires_one_isolated_operation', pointer='/operations')
    return any(selected)


@dataclass(frozen=True)
class _ReviewCandidates:
    _model: object
    candidates: tuple
    _history: tuple

    @property
    def artifacts(self): return self._model.data
    @property
    def metadata_applied(self): return True
    @property
    def decisions(self): return []  # Recording a review grants no artifact approval.
    @property
    def previously_approved_ids(self): return list(self._history)


def prepare_review_candidates(artifacts, operations, *, metadata_policy_version, actor,
        planned_at, preconditions=(), source_files=None, reserved_artifact_ids=(),
        reserved_relation_ids=(), previously_approved_ids=(), profile=None):
    """Dispatch one review operation to its bound positive or negative fold."""
    ops = [ChangeOperation(v).data for v in _owned_sequence(operations, '/operations')]
    if not review_mode(ops):
        raise TargetError('review_operation_required')
    if ops[0]['record']['decision'] == 'rejected':
        from .negative_reviews import prepare_negative_review_candidates
        return prepare_negative_review_candidates(artifacts, ops,
            metadata_policy_version=metadata_policy_version, actor=actor,
            planned_at=planned_at, profile=profile, preconditions=preconditions,
            source_files=source_files, reserved_artifact_ids=reserved_artifact_ids,
            reserved_relation_ids=reserved_relation_ids, previously_approved_ids=previously_approved_ids)
    metadata = bind_policy(metadata_policy_version, actor, planned_at)
    history = _owned_sequence(previously_approved_ids, '/previously_approved_ids')
    reserved = _owned_sequence(reserved_artifact_ids, '/reserved_artifact_ids')
    state, seen, prefixes = _inventory(artifacts, [*reserved, *history])
    _relation_inventory(state, reserved_relation_ids)
    _preflight(state, preconditions, _files(source_files))
    value = ops[0]
    record = value['record']
    if value['approval_withdrawals']:
        raise TargetError('review_withdrawals_require_specialized_service')
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
    expected = prepare_review_record(context, identity, actor=metadata['actor'],
        planned_at=planned_at, decision=record['decision'], reason=record.get('reason'),
        comment=record.get('comment'))
    if canonical_json_bytes(record) != canonical_json_bytes(expected):
        raise TargetError('review_record_binding_mismatch', pointer='/record')
    state[identity.id] = expected
    candidate = MetadataArtifact(identity.id, _snapshot(expected), None,
        canonical_json_sha256(expected), (0,), 'created')
    approved = tuple(sorted(set(history) | {a['id'] for a in artifacts if a['maturity'] == 'approved'}))
    return _ReviewCandidates(_snapshot([state[key] for key in sorted(state)]), (candidate,), approved)


def prepare_review_gates(model, operation, *, actor, planned_at):
    """Bound evidence for the newly recorded confirmed review only.

    Other lifecycle/currentness subjects remain unsupported. These narrowly
    scoped gates do not silently certify old reviews or artifact approvals.
    """
    owned = model.snapshot()
    operation = ChangeOperation(operation.data)
    metadata = bind_policy('change-metadata-v1', actor, planned_at)
    identity = operation.data['record']['id']
    resources = canonical_json_sha256({'model_sources_sha256': owned._sources_sha256,
        'operation': operation.data, 'metadata': metadata})

    def dependencies(context):
        return context.dependency_result({key: list(context.all_ids) for key in context.subjects})

    def check(context):
        if context.subjects != (identity,):
            return context.result([{'reason': 'review_subjects_require_specialized_service', 'severity': 'error'}])
        folded = prepare_review_candidates(owned.artifacts, [operation.data], **metadata,
            source_files=owned.source_files, **owned.reservations)
        expected = {a['id']: a for a in folded.artifacts}
        actual = {key: context.artifact(key) for key in context.all_ids}
        if canonical_json_sha256(expected) != canonical_json_sha256(actual):
            return context.result([{'reason': 'review_target_mismatch', 'severity': 'error'}])
        return context.result()

    return tuple(ModelGate(name, 'bound-confirmed-review-v1', dependencies, check, resources)
                 for name in ('lifecycle', 'review_currentness'))
