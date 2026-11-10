"""Closed review-start evidence and deterministic native control reduction.

Stored hashes bind original bytes. Only the live review-start adapter can
supply its fresh full checks and publication authority; this reducer cannot.
"""
from base64 import b64decode, b64encode
from binascii import Error as Base64Error
from dataclasses import dataclass
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


TRANSITIONS = (('draft', 'validated', 'native_validation'),
               ('validated', 'checked', 'native_check'),
               ('checked', 'in_review', 'review_start'))
EVIDENCE_VERSION = 'proposal-review-start-evidence-v1'
CONTROL_VERSION = 'proposal-control-v1'
GATE = 'extension:proposal-review-start'
COMMAND = 'proposal.review.start'


def decode_report(encoded, kind):
    try:
        raw = b64decode(encoded, validate=True)
        require(b64encode(raw).decode('ascii') == encoded, 'proposal_result_encoding_invalid')
    except (ValueError, TypeError, Base64Error) as error:
        from .errors import ProposalError
        raise ProposalError('proposal_result_encoding_invalid') from error
    report = parse_json_object(raw)
    from ..cli.result_schemas import validate_result_document
    validate_result_document(kind, report)
    require(raw == canonical_json_bytes(report), 'proposal_result_bytes_not_canonical')
    require(report['result_sha256'] == canonical_json_sha256(
        {k: v for k, v in report.items() if k != 'result_sha256'}), 'proposal_result_hash_mismatch')
    require(report['passed'] is True and report['observed_status'] == 'draft'
            and not report['approval_granted'] and not report['write_authorized'],
            'proposal_review_start_check_failed')
    if kind == 'proposal-check-v1':
        require(report['full_semantic_validation'] is True
                and report['workspace'] == dict(retained=False, path=None, cleanup='removed')
                and report['eligible_transition'] is None,
                'proposal_review_start_check_incomplete')
    else:
        require(report['eligible_transition'] == 'validated', 'proposal_validation_transition_invalid')
    return raw, report


def review_start_mode(operations):
    selected = any(op['op'] == 'proposal_control' for op in operations)
    if selected:
        require(len(operations) == 1 and 'review_start' in operations[0],
                'proposal_review_start_isolated_operation_required')
    return selected


def reports(operation):
    proof = operation.get('review_start')
    require(type(proof) is dict and set(proof) == {
        'format_version', 'validation_bytes_base64', 'check_bytes_base64'}
        and proof['format_version'] == EVIDENCE_VERSION, 'proposal_review_start_evidence_required')
    return (decode_report(proof['validation_bytes_base64'], 'proposal-validation-v1'),
            decode_report(proof['check_bytes_base64'], 'proposal-check-v1'))


def control_rows(original, operation, *, actor, planned_at, context=None):
    observed = reports(operation)
    require(original.data['proposal_status'] == 'draft', 'proposal_review_start_requires_draft')
    require(operation['target'] == original.binding.proposal_id
        and type(operation['expected_revision']) is int
        and operation['expected_revision'] == original.data['revision']
        and operation['expected_sha256'] == canonical_json_sha256(original.data),
        'proposal_revision_conflict', exit_code=6)
    require(all(operation[k] == v for k, v in original.binding.data.items() if k != 'proposal_id'),
            'proposal_control_binding_mismatch', exit_code=6)
    for raw, report in observed:
        require(report['binding'] == original.binding.data and report['proposal_sha256'] == original.sha256,
                'proposal_control_result_binding_mismatch', exit_code=6)
        if context is not None:
            require(report['context_sha256'] == context.sha256,
                    'proposal_control_context_mismatch', exit_code=6)
    require(observed[0][1]['context_sha256'] == observed[1][1]['context_sha256']
            and observed[0][1]['revision'] == original.data['revision'],
            'proposal_control_context_mismatch', exit_code=6)
    events, rows = [], []
    for index, (before, after, reason) in enumerate(TRANSITIONS):
        raw = observed[0 if index == 0 else 1][0]
        event = dict(from_=before, to=after, reason=reason, result_sha256=sha256(raw).hexdigest())
        event['from'] = event.pop('from_')
        events.append(event)
        rows.append(dict(format_version=CONTROL_VERSION, binding=original.binding.data,
            actor=actor, occurred_at=planned_at, observed_revision=original.data['revision'],
            result_bytes_base64=b64encode(raw).decode('ascii'), **event))
    require(operation['events'] == events, 'proposal_control_events_mismatch')
    return rows


@dataclass(frozen=True)
class ControlCandidates:
    _model: object
    candidates: tuple
    _history: tuple

    @property
    def artifacts(self): return self._model.data
    @property
    def metadata_applied(self): return True
    @property
    def decisions(self): return []
    @property
    def previously_approved_ids(self): return list(self._history)


def prepare_control_candidates(model, operations, *, metadata_policy_version,
                               actor, planned_at, preconditions=()):
    require(review_start_mode(operations), 'proposal_review_start_operation_required')
    operation = ChangeOperation(operations[0]).data
    metadata = bind_policy(metadata_policy_version, actor, planned_at)
    base = prepare_change_lifecycle(model.artifacts, [], **metadata,
        preconditions=preconditions, source_files=model.source_files, **model.reservations)
    originals = {parse_json_object(d.content)['id']: d for d in model.documents}
    require(operation['target'] in originals, 'proposal_control_target_missing')
    document = originals[operation['target']]
    original = ProposalOriginal(document.content, path=document.path)
    rows = control_rows(original, operation, actor=metadata['actor'], planned_at=planned_at,
                        context=ProposalContext(original, model))
    value = original.data
    value.update(proposal_status='in_review', maturity='in_review',
                 control_history=[*value['control_history'], *rows])
    revision = ProposalRevision(original, value, expected_revision=Revision(operation['expected_revision']),
        actor=Actor(**metadata['actor']), planned_at=UtcTimestamp(planned_at))
    final = revision.after.data
    candidate = MetadataArtifact(final['id'], _snapshot(final), canonical_json_sha256(original.data),
                                 canonical_json_sha256(final), (0,), 'updated', original.source_bytes)
    return ControlCandidates(_snapshot(sorted([final if a['id'] == final['id'] else a
        for a in base.artifacts], key=lambda a: a['id'])), (candidate,), tuple(base.previously_approved_ids))


def bind_control_authoring(plan):
    from ..changes.authoring import prepare_authoring_request
    from ..changes.authoring_values import AuthoringRequest
    value = plan.data
    require(value['metadata_policy_version'] == 'change-metadata-v1'
            and review_start_mode(value['operations']), 'proposal_review_start_plan_required')
    reports(value['operations'][0])
    request = prepare_authoring_request(command_id='proposal review start', actor=value['actor'],
        operations=value['operations'], request_id=value['request_id'])
    return AuthoringRequest._create({**request.data, 'plan_sha256': plan.sha256,
        'base_model_root_sha256': value['base']['model_root_sha256'],
        'scope_descriptor': value['base']['scope_descriptor']})


def read_review_start_observations(original, start, context):
    """Decode three stored originals; the host still owes provenance verification.

    Neither these rows nor their hashes reconstruct the original project. The
    explicit historical context remains mandatory; old row formats stay separate.
    """
    from .observations import ProposalControlObservation
    require(type(original) is ProposalOriginal and type(context) is ProposalContext,
            'proposal_native_original_context_required')
    require(type(start) is int and start >= 0, 'proposal_observation_index_invalid')
    require(original.data['revision'] == context.original.data['revision'] + 1,
            'proposal_control_original_revision_mismatch')
    rows = original.data['control_history'][start:start + 3]
    require(len(rows) == 3, 'proposal_review_start_rows_incomplete')
    fields = {'format_version', 'binding', 'actor', 'occurred_at', 'observed_revision',
              'from', 'to', 'reason', 'result_sha256', 'result_bytes_base64'}
    result = []
    for index, ((before, after, reason), row) in enumerate(zip(TRANSITIONS, rows)):
        require(set(row) == fields and row['format_version'] == CONTROL_VERSION,
                'proposal_control_row_schema_invalid')
        require(type(row['observed_revision']) is int and type(row['actor']) is dict
            and set(row['actor']) == {'actor_type', 'actor_id'}, 'proposal_control_row_schema_invalid')
        raw, report = decode_report(row['result_bytes_base64'],
            'proposal-validation-v1' if index == 0 else 'proposal-check-v1')
        require(row['binding'] == context.original.binding.data == original.binding.data
            and row['observed_revision'] == context.original.data['revision']
            and report['proposal_sha256'] == context.original.sha256
            and report['binding'] == row['binding'] and report['context_sha256'] == context.sha256,
            'proposal_control_context_mismatch', exit_code=6)
        require((row['from'], row['to'], row['reason']) == (before, after, reason)
            and row['result_sha256'] == sha256(raw).hexdigest(), 'proposal_control_events_mismatch')
        require(row['actor'] == rows[0]['actor'] and row['occurred_at'] == rows[0]['occurred_at'],
                'proposal_control_metadata_mismatch')
        result.append(ProposalControlObservation(original, start + index, context,
            Actor(**row['actor']), UtcTimestamp(row['occurred_at']), before, after, reason, raw))
    require(rows[1]['result_bytes_base64'] == rows[2]['result_bytes_base64'],
            'proposal_review_start_check_bytes_changed', exit_code=6)
    return tuple(result)


def _operation(original, validation, check):
    return dict(op='proposal_control', target=original.data['id'],
        expected_revision=original.data['revision'], expected_sha256=canonical_json_sha256(original.data),
        **{k: v for k, v in original.binding.data.items() if k != 'proposal_id'},
        events=[{'from': before, 'to': after, 'reason': reason,
                 'result_sha256': sha256(validation if index == 0 else check).hexdigest()}
                for index, (before, after, reason) in enumerate(TRANSITIONS)],
        review_start=dict(format_version=EVIDENCE_VERSION,
            validation_bytes_base64=b64encode(validation).decode('ascii'),
            check_bytes_base64=b64encode(check).decode('ascii')))
