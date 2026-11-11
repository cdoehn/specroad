"""Deterministic review row reduction with no reusable approval or write grant."""
from base64 import b64encode
from hashlib import sha256

from ..changes._metadata_policy import bind_policy
from ..changes._patch_values import _snapshot
from ..changes.lifecycle import prepare_change_lifecycle
from ..changes.metadata_values import MetadataArtifact
from ..changes.values import ChangeOperation
from ..model.audit_values import Actor, Revision, UtcTimestamp
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..storage.json_syntax import parse_json_object
from .context import ProposalContext
from .revisions import ProposalRevision
from .values import ProposalOriginal, require
from ._review_control import ControlCandidates, CONTROL_VERSION
from ._decision_evidence import operation_proof, outcome

COMMAND = 'proposal.review'
GATE = 'extension:proposal-review'
ROW_VERSION = 'proposal-review-v1'


def review_mode(operations):
    selected = any(op['op'] == 'proposal_control' and 'review_decision' in op for op in operations)
    if selected:
        require(len(operations) == 1 and 'review_start' not in operations[0],
                'proposal_review_isolated_operation_required')
    return selected


def rows(original, operation, *, actor, planned_at, context):
    require(review_mode([operation]), 'proposal_review_decision_required')
    raw, report = operation_proof(operation)
    require(original.data['proposal_status'] == 'in_review', 'proposal_review_requires_in_review')
    require(operation['target'] == original.binding.proposal_id
        and type(operation['expected_revision']) is int
        and operation['expected_revision'] == original.data['revision']
        and operation['expected_sha256'] == canonical_json_sha256(original.data),
        'proposal_revision_conflict', exit_code=6)
    require(all(operation[k] == v for k, v in original.binding.data.items() if k != 'proposal_id')
        and report['binding'] == original.binding.data and report['proposal_sha256'] == original.sha256
        and report['context_sha256'] == context.sha256
        and report['history']['minimum_human_approvals'] == context.minimum_approvals,
        'proposal_control_context_mismatch', exit_code=6)
    status, count, events = outcome(operation, actor)
    require(operation['events'] == events, 'proposal_control_events_mismatch')
    shared = dict(binding=original.binding.data, observed_revision=original.data['revision'],
        result_sha256=sha256(raw).hexdigest(), result_bytes_base64=b64encode(raw).decode('ascii'))
    review = dict(shared, format_version=ROW_VERSION, reviewer=actor, reviewed_at=planned_at,
        decision=operation['review_decision']['decision'], comment=operation['review_decision']['comment'])
    controls = [dict(shared, format_version=CONTROL_VERSION, actor=actor, occurred_at=planned_at,
                     **{k: v for k, v in event.items() if k != 'result_sha256'}) for event in events]
    return review, controls, status


def prepare_review_candidates(model, operations, *, metadata_policy_version, actor, planned_at, preconditions=()):
    require(review_mode(operations), 'proposal_review_decision_required')
    operation = ChangeOperation(operations[0]).data
    metadata = bind_policy(metadata_policy_version, actor, planned_at)
    require(metadata['actor']['actor_type'] == 'human', 'human_review_required', exit_code=7)
    base = prepare_change_lifecycle(model.artifacts, [], **metadata, preconditions=preconditions,
                                   source_files=model.source_files, **model.reservations)
    originals = {parse_json_object(d.content)['id']: d for d in model.documents}
    require(operation['target'] in originals, 'proposal_control_target_missing')
    document = originals[operation['target']]
    original = ProposalOriginal(document.content, path=document.path)
    review, controls, status = rows(original, operation, actor=metadata['actor'], planned_at=planned_at,
                                   context=ProposalContext(original, model))
    value = original.data
    value.update(proposal_status=status, maturity=status, reviews=[*value.get('reviews', []), review],
                 control_history=[*value['control_history'], *controls])
    revision = ProposalRevision(original, value, expected_revision=Revision(operation['expected_revision']),
        actor=Actor(**metadata['actor']), planned_at=UtcTimestamp(planned_at))
    final = revision.after.data
    candidate = MetadataArtifact(final['id'], _snapshot(final), canonical_json_sha256(original.data),
                                 canonical_json_sha256(final), (0,), 'updated', original.source_bytes)
    return ControlCandidates(_snapshot(sorted([final if a['id'] == final['id'] else a
        for a in base.artifacts], key=lambda a: a['id'])), (candidate,), tuple(base.previously_approved_ids))


def bind_review_authoring(plan):
    from ..changes.authoring import prepare_authoring_request
    from ..changes.authoring_values import AuthoringRequest
    value = plan.data
    require(value['metadata_policy_version'] == 'change-metadata-v1' and review_mode(value['operations']),
            'proposal_review_plan_required')
    operation_proof(value['operations'][0])
    request = prepare_authoring_request(command_id='proposal review', actor=value['actor'],
        operations=value['operations'], request_id=value['request_id'])
    return AuthoringRequest._create({**request.data, 'plan_sha256': plan.sha256,
        'base_model_root_sha256': value['base']['model_root_sha256'],
        'scope_descriptor': value['base']['scope_descriptor']})


def read_review_observations(original, context):
    """Decode one new decision; the host must still verify actual provenance."""
    from .observations import ProposalReviewObservation, ProposalControlObservation
    from ._decision_evidence import operation
    require(type(original) is ProposalOriginal and type(context) is ProposalContext,
            'proposal_native_original_context_required')
    before = context.original
    values = original.data.get('reviews', [])
    index = len(before.data.get('reviews', []))
    require(original.data['revision'] == before.data['revision'] + 1 and len(values) == index + 1,
            'proposal_review_original_revision_mismatch')
    row = values[index]
    fields = {'format_version', 'binding', 'reviewer', 'reviewed_at', 'observed_revision', 'decision',
              'comment', 'result_sha256', 'result_bytes_base64'}
    require(set(row) == fields and row['format_version'] == ROW_VERSION
        and type(row['reviewer']) is dict and set(row['reviewer']) == {'actor_type', 'actor_id'}
        and type(row['observed_revision']) is int, 'proposal_review_row_schema_invalid')
    from ._decision_evidence import decode
    raw, report = decode(row['result_bytes_base64'])
    op = operation(before, raw, row['decision'], row['comment'], row['reviewer'])
    expected_review, expected_controls, status = rows(before, op, actor=row['reviewer'],
                                                    planned_at=row['reviewed_at'], context=context)
    require(row == expected_review and original.data['proposal_status'] == status
        and values[:index] == before.data.get('reviews', [])
        and original.data['control_history'] == [*before.data['control_history'], *expected_controls],
        'proposal_review_stored_rows_changed', exit_code=6)
    candidate = before.data
    candidate.update(proposal_status=status, maturity=status,
        reviews=[*candidate.get('reviews', []), expected_review],
        control_history=[*candidate['control_history'], *expected_controls])
    expected = ProposalRevision(before, candidate, expected_revision=Revision(before.data['revision']),
        actor=Actor(**row['reviewer']), planned_at=UtcTimestamp(row['reviewed_at'])).after
    require(original.source_bytes == expected.source_bytes,
            'proposal_review_original_metadata_changed', exit_code=6)
    review = ProposalReviewObservation(original, index, context, Actor(**row['reviewer']),
        UtcTimestamp(row['reviewed_at']), row['decision'], row['observed_revision'])
    controls = tuple(ProposalControlObservation(original, len(before.data['control_history']) + i,
        context, Actor(**row['reviewer']), UtcTimestamp(row['reviewed_at']), event['from'],
        event['to'], event['reason'], raw) for i, event in enumerate(expected_controls))
    return review, controls
