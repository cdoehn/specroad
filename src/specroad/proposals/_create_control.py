"""Closed initial-draft reducer; never an approval or a generic record writer."""
from ..changes._metadata_policy import bind_policy
from ..changes._patch_values import _snapshot
from ..changes.lifecycle import prepare_change_lifecycle
from ..changes.metadata_values import MetadataArtifact
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.identity_values import artifact_identity
from .authoring import Proposal
from .context import ProposalContext
from .validation import validate_proposal
from ._review_control import ControlCandidates
from .values import require

COMMAND = 'proposal.create'
GATE = 'extension:proposal-create'


def creation_record(operation):
    require(type(operation) is dict and set(operation) == {'op', 'record'}
            and operation['op'] == 'proposal_create', 'proposal_create_operation_required')
    value = operation['record']
    identity = artifact_identity(value)
    proposal = Proposal(canonical_json_bytes(value), path=identity.path)
    require(value['revision'] == value['content_revision'] == 1
            and value['proposal_status'] == value['maturity'] == 'draft'
            and not value['reviews'] and not value['control_history']
            and not value['relations'] and not value['extensions'],
            'proposal_create_initial_draft_required')
    return proposal


def creation_mode(operations):
    selected = any(op['op'] == 'proposal_create' for op in operations)
    if selected:
        require(len(operations) == 1, 'proposal_create_isolated_operation_required')
        creation_record(operations[0])
    return selected


def prepare_create_candidates(model, operations, *, metadata_policy_version,
                              actor, planned_at, preconditions=()):
    require(creation_mode(operations), 'proposal_create_operation_required')
    metadata = bind_policy(metadata_policy_version, actor, planned_at)
    base = prepare_change_lifecycle(model.artifacts, [], **metadata,
        preconditions=preconditions, source_files=model.source_files, **model.reservations)
    proposal = creation_record(operations[0]); record = proposal.data
    require(record['created_by'] == record['updated_by'] == metadata['actor']
        and record['created_at'] == record['updated_at'] == planned_at
        and record['change_plan']['actor'] == metadata['actor']
        and record['change_plan']['planned_at'] == planned_at,
        'proposal_create_metadata_mismatch')
    require(record['id'] not in {a['id'] for a in base.artifacts}
        and record['id'] not in model.reservations['reserved_artifact_ids']
        and record['id'] not in base.previously_approved_ids
        and artifact_identity(record).id_prefix == model.configuration.id_prefix,
        'proposal_create_identity_conflict', exit_code=6)
    validate_proposal(ProposalContext(proposal.original, model))
    candidate = MetadataArtifact(record['id'], _snapshot(record), None,
                                 canonical_json_sha256(record), (0,), 'created')
    return ControlCandidates(_snapshot(sorted([*base.artifacts, record], key=lambda a: a['id'])),
                             (candidate,), tuple(base.previously_approved_ids))


def bind_create_authoring(plan):
    from ..changes.authoring import prepare_authoring_request
    from ..changes.authoring_values import AuthoringRequest
    value = plan.data
    require(creation_mode(value['operations']), 'proposal_create_operation_required')
    record = value['operations'][0]['record']
    require(record['change_plan']['request_id'] == value['request_id'],
            'proposal_create_request_mismatch', exit_code=6)
    request = prepare_authoring_request(command_id='proposal create', actor=value['actor'],
        operations=value['operations'], request_id=value['request_id'])
    return AuthoringRequest._create({**request.data, 'plan_sha256': plan.sha256,
        'base_model_root_sha256': value['base']['model_root_sha256'],
        'scope_descriptor': value['base']['scope_descriptor']})
