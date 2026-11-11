"""Current review evidence binds complete native checks, never human authority."""
from base64 import b64decode, b64encode
from binascii import Error as Base64Error
from hashlib import sha256

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..storage.json_syntax import parse_json_object
from .context import ProposalContext
from .history import assess_proposal, native_check
from ._review_checks import _initial_inputs
from .values import require

VERSION = 'proposal-review-assessment-v1'


def effective_actors(history):
    effective = set()
    for row in history['reviews']:
        if not row['binding_current']:
            continue
        actor = row['actor_id']
        if row['decision'] in ('rejected', 'withdrawn'):
            effective.discard(actor)
        elif row['human']:
            if row['decision_current']:
                effective.add(actor)
            else:
                effective.discard(actor)
    return sorted(effective)


def assessment(snapshot, original, services):
    context = ProposalContext(original, snapshot.model)
    history = assess_proposal(original, _initial_inputs(snapshot.model, original, services),
                              snapshot.model, services=services)
    require(history['current_basis_matches'], 'proposal_current_basis_stale', exit_code=6)
    proof = dict(format_version=VERSION, binding=original.binding.data,
        proposal_sha256=original.sha256, context_sha256=context.sha256,
        history=history, effective_human_actor_ids=effective_actors(history),
        native_check=parse_json_object(native_check(context, services=services)))
    proof['result_sha256'] = canonical_json_sha256(proof)
    return canonical_json_bytes(proof)


def decode(encoded):
    try:
        raw = b64decode(encoded, validate=True)
        require(b64encode(raw).decode('ascii') == encoded, 'proposal_result_encoding_invalid')
    except (ValueError, TypeError, Base64Error) as error:
        from .errors import ProposalError
        raise ProposalError('proposal_result_encoding_invalid') from error
    value = parse_json_object(raw)
    require(set(value) == {'format_version', 'binding', 'proposal_sha256', 'context_sha256',
        'history', 'effective_human_actor_ids', 'native_check', 'result_sha256'}
        and value['format_version'] == VERSION, 'proposal_review_assessment_schema_invalid')
    require(raw == canonical_json_bytes(value), 'proposal_result_bytes_not_canonical')
    require(value['result_sha256'] == canonical_json_sha256(
        {k: v for k, v in value.items() if k != 'result_sha256'}), 'proposal_result_hash_mismatch')
    history, native = value['history'], value['native_check']
    require(type(history) is dict and set(history) == {'proposal_id', 'original_sha256',
        'observed_status', 'historical_valid', 'current_basis_matches', 'current_approval',
        'effective_human_approvals', 'minimum_human_approvals', 'reviews', 'write_authorized',
        'apply_performed'}, 'proposal_review_assessment_schema_invalid')
    require(history['historical_valid'] is True and history['current_basis_matches'] is True
        and history['observed_status'] == 'in_review' and history['current_approval'] is False
        and history['write_authorized'] is False and history['apply_performed'] is False
        and type(history['minimum_human_approvals']) is int and history['minimum_human_approvals'] >= 1
        and type(history['effective_human_approvals']) is int and history['effective_human_approvals'] >= 0
        and type(history['reviews']) is list, 'proposal_review_assessment_invalid')
    for row in history['reviews']:
        require(type(row) is dict and set(row) == {'review_index', 'actor_id', 'decision',
            'binding_current', 'decision_current', 'human'} and type(row['review_index']) is int
            and row['review_index'] >= 0 and type(row['actor_id']) is str and bool(row['actor_id'])
            and row['decision'] in ('approved', 'rejected', 'withdrawn')
            and all(type(row[k]) is bool for k in ('binding_current', 'decision_current', 'human')),
            'proposal_review_assessment_invalid')
    require(value['effective_human_actor_ids'] == effective_actors(history)
        and len(value['effective_human_actor_ids']) == history['effective_human_approvals'],
        'proposal_review_quorum_mismatch')
    require(type(native) is dict and set(native) == {'context_sha256', 'binding', 'base_manifest',
        'target_manifest', 'target_sources_sha256', 'qualification', 'write_authorized'}
        and native['context_sha256'] == value['context_sha256'] and native['binding'] == value['binding']
        and native['qualification'] == 'complete_native_model_and_plan_checks'
        and native['write_authorized'] is False
        and history['proposal_id'] == value['binding'].get('proposal_id')
        and history['original_sha256'] == value['proposal_sha256'], 'proposal_review_assessment_invalid')
    return raw, value


def operation_proof(operation):
    proof = operation.get('review_decision')
    require(type(proof) is dict and set(proof) == {'format_version', 'decision', 'comment',
        'assessment_bytes_base64'} and proof['format_version'] == 'proposal-review-decision-v1'
        and proof['decision'] in ('approved', 'rejected')
        and (proof['comment'] is None or type(proof['comment']) is str),
        'proposal_review_decision_required')
    return decode(proof['assessment_bytes_base64'])


def outcome(operation, actor):
    require(actor['actor_type'] == 'human', 'human_review_required', exit_code=7)
    raw, report = operation_proof(operation)
    actors = set(report['effective_human_actor_ids'])
    decision = operation['review_decision']['decision']
    if decision == 'approved':
        actors.add(actor['actor_id'])
        status = 'approved' if len(actors) >= report['history']['minimum_human_approvals'] else 'in_review'
    else:
        actors.discard(actor['actor_id'])
        status = 'rejected'
    events = [] if status == 'in_review' else [dict(
        from_='in_review', to=status, reason='human_review', result_sha256=sha256(raw).hexdigest())]
    for event in events:
        event['from'] = event.pop('from_')
    return status, len(actors), events


def operation(original, raw, decision, comment, actor):
    value = dict(op='proposal_control', target=original.data['id'],
        expected_revision=original.data['revision'], expected_sha256=canonical_json_sha256(original.data),
        **{k: v for k, v in original.binding.data.items() if k != 'proposal_id'}, events=[],
        review_decision=dict(format_version='proposal-review-decision-v1', decision=decision,
            comment=comment, assessment_bytes_base64=b64encode(raw).decode('ascii')))
    value['events'] = outcome(value, actor)[2]
    return value
