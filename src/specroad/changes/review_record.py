"""Pure context binding, timestamp ordering and confirmed-review construction.

These values carry no publication authority and perform no file mutations.
"""
from ..graph.relations import SourceRelations
from ..graph.review_context_values import RelationReviewContext
from ..model.audit import actor as read_actor, new_artifact_audit
from ..model.audit_values import UtcTimestamp
from ..model.canonical import canonical_json_bytes
from ..model.versions import SCHEMA_VERSION
from ._common import _artifact, _text
from .metadata_time import next_update_time
from .target_values import TargetError


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
