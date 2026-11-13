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
NEGATIVE_VERSION = 'proposal-review-assessment-v2'


def decision_state(status, decision):
    allowed = ('in_review',) if decision == 'approved' else (
        ('in_review', 'approved') if decision == 'withdrawn' else ('draft', 'in_review', 'approved'))
    require(status in allowed, 'proposal_review_state_invalid')


def assessment_version(original, decision):
    return (NEGATIVE_VERSION if decision == 'withdrawn' or
            original.data['proposal_status'] != 'in_review' else VERSION)



def effective_actors(history):
    from .quorum import effective_actors as selected
    return selected(history['reviews'])


def assessment(snapshot, original, services, *, version=VERSION):
    require(version in (VERSION, NEGATIVE_VERSION), 'proposal_review_assessment_schema_invalid')
    context = ProposalContext(original, snapshot.model)
    history = assess_proposal(original, _initial_inputs(snapshot.model, original, services),
                              snapshot.model, services=services)
    require(history['current_basis_matches'], 'proposal_current_basis_stale', exit_code=6)
    proof = dict(format_version=version, binding=original.binding.data,
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
        and value['format_version'] in (VERSION, NEGATIVE_VERSION), 'proposal_review_assessment_schema_invalid')
    require(raw == canonical_json_bytes(value), 'proposal_result_bytes_not_canonical')
    require(value['result_sha256'] == canonical_json_sha256(
        {k: v for k, v in value.items() if k != 'result_sha256'}), 'proposal_result_hash_mismatch')
    from .values import ProposalBinding
    require(type(value['binding']) is dict and set(value['binding']) == {
        'proposal_id', 'content_revision', 'content_sha256', 'base_model_root_sha256',
        'change_plan_sha256'}, 'proposal_review_assessment_schema_invalid')
    ProposalBinding(**value['binding'])
    require(all(type(value[key]) is str and len(value[key]) == 64
        and all(c in '0123456789abcdef' for c in value[key])
        for key in ('proposal_sha256', 'context_sha256', 'result_sha256')),
        'proposal_review_assessment_schema_invalid')
    history, native = value['history'], value['native_check']
    require(type(history) is dict and set(history) == {'proposal_id', 'original_sha256',
        'observed_status', 'historical_valid', 'current_basis_matches', 'current_approval',
        'effective_human_approvals', 'minimum_human_approvals', 'reviews', 'write_authorized',
        'apply_performed'}, 'proposal_review_assessment_schema_invalid')
    require(history['historical_valid'] is True and history['current_basis_matches'] is True
        and history['observed_status'] in (('in_review',) if value['format_version'] == VERSION
            else ('draft', 'in_review', 'approved'))
        and type(history['current_approval']) is bool
        and history['write_authorized'] is False and history['apply_performed'] is False
        and type(history['minimum_human_approvals']) is int and history['minimum_human_approvals'] >= 1
        and type(history['effective_human_approvals']) is int and history['effective_human_approvals'] >= 0
        and type(history['reviews']) is list, 'proposal_review_assessment_invalid')
    require(history['current_approval'] == (history['observed_status'] == 'approved')
        and (not history['current_approval'] or
             history['effective_human_approvals'] >= history['minimum_human_approvals']),
        'proposal_review_assessment_invalid')
    for row in history['reviews']:
        require(type(row) is dict and set(row) == {'review_index', 'actor_id', 'decision',
            'binding_current', 'decision_current', 'human'} and type(row['review_index']) is int
            and row['review_index'] >= 0 and type(row['actor_id']) is str and bool(row['actor_id'])
            and row['decision'] in ('approved', 'rejected', 'withdrawn')
            and all(type(row[k]) is bool for k in ('binding_current', 'decision_current', 'human')),
            'proposal_review_assessment_invalid')
    require([row['review_index'] for row in history['reviews']] == list(range(len(history['reviews']))),
            'proposal_review_assessment_history_incomplete')
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
        'assessment_bytes_base64'} and proof['format_version'] in (
            'proposal-review-decision-v1', 'proposal-review-decision-v2')
        and proof['decision'] in (('approved', 'rejected') if proof['format_version'] ==
            'proposal-review-decision-v1' else ('rejected', 'withdrawn'))
        and (proof['comment'] is None or type(proof['comment']) is str),
        'proposal_review_decision_required')
    raw, report = decode(proof['assessment_bytes_base64'])
    expected = VERSION if proof['format_version'] == 'proposal-review-decision-v1' else NEGATIVE_VERSION
    require(report['format_version'] == expected, 'proposal_review_versions_mixed')
    decision_state(report['history']['observed_status'], proof['decision'])
    if expected == NEGATIVE_VERSION:
        require(proof['decision'] == 'withdrawn' or report['history']['observed_status'] != 'in_review',
                'proposal_review_versions_mixed')
    if proof['decision'] == 'withdrawn':
        require(type(proof['comment']) is str and bool(proof['comment'].strip()),
                'proposal_withdrawal_reason_required', exit_code=2)
    return raw, report


def outcome(operation, actor):
    require(actor['actor_type'] == 'human', 'human_review_required', exit_code=7)
    raw, report = operation_proof(operation)
    from .quorum import decision_outcome, approvals
    decision = operation['review_decision']['decision']
    before = report['history']['observed_status']
    if decision == 'withdrawn':
        require(actor['actor_id'] in approvals(report['history']['reviews']),
                'proposal_own_approval_required', exit_code=7)
        remaining = set(report['effective_human_actor_ids']) - {actor['actor_id']}
        status = 'rejected' if before == 'approved' else 'in_review'
        count = len(remaining)
    else:
        status, count = decision_outcome(report['effective_human_actor_ids'], actor['actor_id'],
            decision, report['history']['minimum_human_approvals'])
    events = [] if status == before else [dict(
        from_=before, to=status, reason='human_withdrawal' if decision == 'withdrawn' else 'human_review',
        result_sha256=sha256(raw).hexdigest())]
    for event in events:
        event['from'] = event.pop('from_')
    return status, count, events


def operation(original, raw, decision, comment, actor):
    _, report = decode(b64encode(raw).decode('ascii'))
    version = 'proposal-review-decision-v1' if report['format_version'] == VERSION else 'proposal-review-decision-v2'
    value = dict(op='proposal_control', target=original.data['id'],
        expected_revision=original.data['revision'], expected_sha256=canonical_json_sha256(original.data),
        **{k: v for k, v in original.binding.data.items() if k != 'proposal_id'}, events=[],
        review_decision=dict(format_version=version, decision=decision,
            comment=comment, assessment_bytes_base64=b64encode(raw).decode('ascii')))
    value['events'] = outcome(value, actor)[2]
    return value
