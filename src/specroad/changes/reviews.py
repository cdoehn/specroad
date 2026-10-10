"""Dedicated confirmed-review planning; generic record mutation stays closed.

Explicit source guards, human actor, exact endpoint observations and regular
creation metadata are rechecked for saved plans as well as direct authoring.
Negative assessment/withdrawals and general history selection remain separate
services. No function here grants publication authority or mutates a file.
"""
from dataclasses import dataclass

from ..graph.relations import SourceRelations
from ..graph.review_context_values import RelationReviewContext
from ..model.audit import actor as read_actor, new_artifact_audit
from ..model.audit_values import UtcTimestamp
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.identity_values import artifact_identity
from ..model.versions import SCHEMA_VERSION
from ..validation import ModelGate
from ._common import _artifact, _text
from ._fold_inputs import (_inventory, _relation_inventory, _preflight, _files,
                          _check_expected, _owned_sequence)
from ._metadata_policy import bind_policy
from ._patch_values import _snapshot
from .metadata_time import next_update_time
from .metadata_values import MetadataArtifact
from .target_values import TargetError
from .values import ChangeOperation


def review_mode(operations):
    selected = [op['op'] == 'relation_review_record' for op in operations]
    if any(selected) and (len(operations) != 1 or not all(selected)):
        raise TargetError('review_requires_one_isolated_operation', pointer='/operations')
    return any(selected)


def review_context(artifacts, source_id, relation_id):
    state = {a['id']: a for a in artifacts}
    if source_id not in state:
        raise TargetError('review_source_missing', pointer='/source')
    source = SourceRelations(canonical_json_bytes(state[source_id]))
    matches = [r for r in source.relations if r.identity.id == relation_id]
    if len(matches) != 1:
        raise TargetError('review_relation_missing', pointer='/relation_id')
    relation = matches[0]
    if relation.target not in state:
        raise TargetError('review_target_missing', pointer='/target')
    target = SourceRelations(canonical_json_bytes(state[relation.target]))
    return RelationReviewContext(relation, source, target)


def review_time(artifacts, context, planned_at):
    """Bind a new decision after every previous review of the same J context."""
    UtcTimestamp(planned_at)
    for value in artifacts:
        if (value['artifact_type'] == 'relation_review'
                and value['relation_id'] == context.relation_id
                and value['relation_content_sha256'] == context.relation_sha256
                and value['source_context_sha256'] == context.source.context_sha256
                and value['target_context_sha256'] == context.target.context_sha256):
            # Older passive records retained their creation timestamp only.
            planned_at = next_update_time(planned_at, value.get('reviewed_at', value['created_at']))
    return planned_at


def prepare_review_record(context, identity, *, actor, planned_at, decision, reason, comment=None):
    if type(context) is not RelationReviewContext:
        raise TargetError('typed_review_context_required')
    bound_actor = read_actor(actor)
    if bound_actor.actor_type != 'human':
        raise TargetError('human_review_planner_required', pointer='/actor')
    if decision != 'confirmed':
        raise TargetError('review_outcome_requires_specialized_service', pointer='/decision')
    _text(reason, '/reason')
    if comment is not None:
        _text(comment, '/comment')
    if identity.artifact_type != 'relation_review' or identity.id_scheme != 'random128-v1':
        raise TargetError('new_review_identity_required', pointer='/id')
    value = {'schema_version': SCHEMA_VERSION, 'artifact_type': 'relation_review',
        'id': identity.id, 'id_scheme': identity.id_scheme,
        'title': 'Relation review ' + context.relation_id,
        'maturity': 'approved', 'review_state': 'recorded', 'relations': [], 'extensions': {},
        **new_artifact_audit(actor=bound_actor, planned_at=UtcTimestamp(planned_at)).as_fields(),
        'relation_id': context.relation_id, 'relation_content_sha256': context.relation_sha256,
        'context_hash_algorithm': context.source.algorithm,
        'reviewer': bound_actor.as_fields(), 'decision': decision, 'reason': reason,
        'reviewed_at': planned_at}
    for name, endpoint in (('source', context.source), ('target', context.target)):
        value.update({name + '_id': endpoint.artifact_id, name + '_revision': endpoint.revision,
            name + '_artifact_sha256': endpoint.artifact_sha256,
            name + '_context_sha256': endpoint.context_sha256})
    if comment is not None:
        value['comment'] = comment
    _artifact(value, '/record', 'relation_review')
    return value


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
        reserved_relation_ids=(), previously_approved_ids=()):
    """One immutable creation; never expose a generic special-record reducer."""
    ops = [ChangeOperation(v).data for v in _owned_sequence(operations, '/operations')]
    if not review_mode(ops):
        raise TargetError('review_operation_required')
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
