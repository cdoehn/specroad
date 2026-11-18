"""Closed, deterministic reduction of an already prepared content edit.

Allocated Change IDs are bound inputs, never allocated again during a gate.
The reducer owns no host authority and cannot publish the embedded plan.
"""
from ..changes._metadata_policy import bind_policy
from ..changes._patch_values import _snapshot
from ..changes.lifecycle import prepare_change_lifecycle
from ..changes.metadata_values import MetadataArtifact
from ..model.audit_values import Actor, Revision, UtcTimestamp
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.identity_values import artifact_identity
from ..storage.json_syntax import parse_json_object
from .authoring import Proposal
from .change_ids import change_id
from .context import ProposalContext
from .revisions import ProposalRevision, require_authoring_status
from .validation import validate_proposal
from .values import ProposalOriginal, require
from ._review_control import ControlCandidates
from ._change_sequence import changed_sequence

GATE = 'extension:proposal-change'
ACTIONS = ('add', 'update', 'remove', 'move')


def change_record(operation):
    require(type(operation) is dict and set(operation) == {
        'op', 'target', 'expected_revision', 'expected_sha256', 'action',
        'changed_change_ids', 'record'} and operation['op'] == 'proposal_change',
        'proposal_change_operation_required')
    require(operation['action'] in ACTIONS, 'proposal_change_action_invalid')
    record = operation['record']
    identity = artifact_identity(record)
    proposal = Proposal(canonical_json_bytes(record), path=identity.path)
    require(operation['target'] == record['id'], 'proposal_change_target_mismatch')
    ids = operation['changed_change_ids']
    require(type(ids) is list and len(ids) <= 1, 'proposal_changed_ids_invalid')
    for identity in ids:
        change_id(identity)
    return proposal


def change_mode(operations):
    selected = any(op['op'] == 'proposal_change' for op in operations)
    if selected:
        require(len(operations) == 1, 'proposal_change_isolated_operation_required')
        change_record(operations[0])
    return selected



def reduce_change(original, operation, *, actor, planned_at):
    require(operation['target'] == original.data['id']
        and operation['expected_revision'] == original.data['revision']
        and operation['expected_sha256'] == canonical_json_sha256(original.data),
        'proposal_revision_conflict', exit_code=6)
    require_authoring_status(original.data)
    before = Proposal(original.source_bytes, path=original.path)
    sequence = changed_sequence(before, operation)
    value = original.data
    value.update(changes=sequence.changes, change_plan=sequence.change_plan.data)
    revision = ProposalRevision(original, value,
        expected_revision=Revision(operation['expected_revision']),
        actor=Actor(**actor), planned_at=UtcTimestamp(planned_at))
    require(canonical_json_bytes(revision.after.data) == canonical_json_bytes(operation['record']),
            'proposal_change_record_mismatch', exit_code=6)
    return revision


def prepare_change_candidates(model, operations, *, metadata_policy_version,
                              actor, planned_at, preconditions=()):
    require(change_mode(operations), 'proposal_change_operation_required')
    operation = operations[0]
    metadata = bind_policy(metadata_policy_version, actor, planned_at)
    base = prepare_change_lifecycle(model.artifacts, [], **metadata,
        preconditions=preconditions, source_files=model.source_files, **model.reservations)
    documents = {parse_json_object(d.content)['id']: d for d in model.documents}
    require(operation['target'] in documents, 'proposal_change_target_missing')
    document = documents[operation['target']]
    original = ProposalOriginal(document.content, path=document.path)
    revision = reduce_change(original, operation, actor=metadata['actor'], planned_at=planned_at)
    validate_proposal(ProposalContext(revision.after, model))
    final = revision.after.data
    candidate = MetadataArtifact(final['id'], _snapshot(final), canonical_json_sha256(original.data),
        canonical_json_sha256(final), (0,), 'updated' if revision.changed else 'unchanged',
        original.source_bytes)
    return ControlCandidates(_snapshot(sorted([final if a['id'] == final['id'] else a
        for a in base.artifacts], key=lambda a: a['id'])), (candidate,), tuple(base.previously_approved_ids))


def bind_change_authoring(plan):
    from ..changes.authoring import prepare_authoring_request
    from ..changes.authoring_values import AuthoringRequest
    value = plan.data
    require(change_mode(value['operations']), 'proposal_change_operation_required')
    request = prepare_authoring_request(command_id='proposal change ' + value['operations'][0]['action'],
        actor=value['actor'], operations=value['operations'], request_id=value['request_id'])
    return AuthoringRequest._create({**request.data, 'plan_sha256': plan.sha256,
        'base_model_root_sha256': value['base']['model_root_sha256'],
        'scope_descriptor': value['base']['scope_descriptor']})
