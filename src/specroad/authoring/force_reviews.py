"""Explicit relation-review facts; never manufacture a human reviewer."""
from ..model.audit import new_artifact_audit, actor as read_actor
from ..model.audit_values import UtcTimestamp
from ..model.versions import SCHEMA_VERSION
from ..changes.review_record import review_context, review_time
from ..changes.force_domain_gates import record_denial
from ..changes.write_guard_values import require
from ..model.errors import ModelError


def record(sources, data, actor, time, decisions):
    artifacts = [rows[0][1] for rows in sources.records.values() if len(rows) == 1]
    context = review_context(artifacts, data['source'], data['relation_id'])
    require(data['decision'] in ('confirmed', 'rejected'), 'force_review_decision_required', exit_code=2)
    require(type(data['reason']) is str and bool(data['reason'].strip()), 'force_review_reason_required', exit_code=2)
    identity = sources.allocate('relation_review')
    from .force_compile import _guard
    _guard(decisions, sources.artifact(data['source'])[1], data, 'relation.review')
    decisions.decide(actor['actor_type'] == 'human', gate_id='actor:reviewer',
        diagnostic_code='CORE_SECURITY', subject=identity.id, operation='relation.review',
        observed_binding=actor, requested_binding=data['decision'], effect='record_explicit_actor_without_human_claim')
    # The native time rule is actual data construction, not an invented old observation.
    time = review_time(artifacts, context, time)
    value = dict(schema_version=SCHEMA_VERSION, artifact_type='relation_review',
        id=identity.id, id_scheme=identity.id_scheme, title='Relation review ' + context.relation_id,
        maturity='approved', review_state='recorded', relations=[], extensions={},
        **new_artifact_audit(actor=read_actor(actor), planned_at=UtcTimestamp(time)).as_fields(),
        relation_id=context.relation_id, relation_content_sha256=context.relation_sha256,
        context_hash_algorithm=context.source.algorithm, reviewer=actor, decision=data['decision'],
        reason=data['reason'], reviewed_at=time)
    for name, endpoint in (('source', context.source), ('target', context.target)):
        value.update({name + '_id': endpoint.artifact_id, name + '_revision': endpoint.revision,
            name + '_artifact_sha256': endpoint.artifact_sha256, name + '_context_sha256': endpoint.context_sha256})
    if 'comment' in data: value['comment'] = data['comment']
    withdrawals = []
    if data['decision'] == 'rejected':
        from ..changes.negative_reviews import required_review_withdrawals
        try:
            withdrawals = required_review_withdrawals(artifacts, data['source'], data['relation_id'],
                profile=None if sources.model is None else sources.model.profile)
        except ModelError as error:
            record_denial(decisions, error, operation='relation.review', subject=data['source'], requested=data)
    return dict(op='relation_review_record', source=data['source'], target=context.target.artifact_id,
        record=value, approval_withdrawals=withdrawals,
        **{k: data[k] for k in ('expected_revision', 'expected_sha256') if k in data})
