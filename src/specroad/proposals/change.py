"""Publish an owned ProposalEdit through the existing native transaction."""

from ..changes import TargetModel, TargetPolicy, PublicationAuthority, prepare_authoring_request
from ..changes._journal_codec import _transaction
from ..changes.normal_access import require_normal_access
from ..changes.target import prepare_change_target
from ..changes.target_model import _default_scope
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..qualification.services import native_services
from ..storage.project import ProjectSource
from ._change_control import ACTIONS, GATE, reduce_change
from ._change_qualification import _gates
from .editing import ProposalEdit
from .values import require



def publish_proposal_change(edit, model, *, change_plan_id, planned_at,
                            transaction_id, authority=None, services=None):
    """Publish only the prepared content revision; no implicit decision or apply.

    Historical replay uses actual receipt/completion originals before current
    target qualification. A dry-run writes nothing; a no-op still rechecks the
    live host and produces neither a revision nor a success receipt.
    """
    require(type(edit) is ProposalEdit and type(model) is TargetModel,
            'typed_proposal_change_inputs_required')
    model = model.snapshot()
    services = native_services(services)
    request = edit.request.data
    command = request['command_id']
    require(command in tuple('proposal change ' + action for action in ACTIONS),
            'proposal_change_action_invalid')
    require(canonical_json_bytes(request['operations']) ==
            canonical_json_bytes(edit.revision.after.data['change_plan']['operations']),
            'proposal_change_request_mismatch', exit_code=6)
    before = edit.revision.before
    operation = dict(op='proposal_change', target=before.data['id'],
        expected_revision=before.data['revision'], expected_sha256=canonical_json_sha256(before.data),
        action=command.split()[-1], changed_change_ids=list(edit.changed_change_ids),
        record=edit.revision.after.data)
    revision = reduce_change(before, operation, actor=request['actor'], planned_at=planned_at)
    authoring = prepare_authoring_request(command_id=command, actor=request['actor'],
        operations=[operation], request_id=request['request_id'], dry_run=request['dry_run'])
    _transaction(transaction_id)
    if not request['dry_run']:
        require(type(authority) is PublicationAuthority, 'proposal_host_authority_required', exit_code=7)
    require_normal_access(model.binding.source_root, expected_project_id=model.binding.project_id)
    source = ProjectSource(model.binding.source_root, expected_project_id=model.binding.project_id)
    require(source.boundary._root_identity == model.binding.root_identity,
            'authoring_project_changed', exit_code=6)
    if not request['dry_run']:
        from ..authoring.execution import _replay
        replay = _replay(source, authoring, command.replace(' ', '.'))
        if replay is not None:
            return {**replay, 'proposal': revision.after.data,
                'changed_change_ids': list(edit.changed_change_ids),
                'publication_kind': 'proposal_content_revision', 'current_target_verified': False}
    require(any(d.path == before.path and d.content == before.source_bytes for d in model.documents),
            'proposal_original_bytes_changed', exit_code=6)
    from ..changes._publication_observation import _root
    _root(model)
    from ..authoring._inspection_snapshot import InspectionSnapshot
    observed = InspectionSnapshot(model.binding.source_root, None, include_archive_objects=True)
    require(observed.model._sources_sha256 == model._sources_sha256,
            'proposal_change_basis_changed', exit_code=6)
    selected = _gates(model, revision, services)
    policy = TargetPolicy(command.replace(' ', '.'), '1', (GATE,))
    checked = prepare_change_target(model, [operation], change_plan_id=change_plan_id,
        request_id=request['request_id'], actor=request['actor'], planned_at=planned_at,
        scope_descriptor=_default_scope(), metadata_policy_version='change-metadata-v1',
        policy=policy, gates=selected)
    checked.require_valid()
    observed.verify_current()
    if request['dry_run']:
        result = dict(dry_run=True, write_state='not_committed', replayed=False,
            no_change=not revision.changed, completion=None, approval_granted=False,
            plan_sha256=checked.plan.sha256)
    else:
        from ..authoring.execution import _apply_saved_plan
        result = _apply_saved_plan(checked.plan, model, command_id=policy.command_id,
            transaction_id=transaction_id, authority=authority, gates=selected, bound_policy=policy)
    return {**result, 'proposal': revision.after.data,
        'changed_change_ids': list(edit.changed_change_ids),
        'publication_kind': 'proposal_content_revision'}
