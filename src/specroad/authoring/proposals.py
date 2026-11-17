"""Route complete native authoring plans to an isolated Proposal draft.

The host supplies allocated identities and trusted live services. Proposal
metadata never supplies authority, gates, a reviewer or executable adapters.
"""
from dataclasses import replace
from ..changes import ChangePlan, TargetModel, TargetPolicy, assess_change_target, prepare_authoring_request
from ..changes.core import prepare_change_plan
from ..changes._target_materialization import materialize_target
from ..changes.target import prepare_change_target
from ..changes.target_model import _default_scope
from ..proposals.authoring import prepare_proposal
from ..proposals.basis import build_proposal_basis
from ..proposals.context import ProposalContext
from ..proposals.validation import validate_proposal
from ..proposals._create_control import COMMAND, GATE
from ..proposals._review_checks import _initial_inputs
from ..proposals.values import require
from ..qualification.services import native_services
from ..validation import ModelGate
from ..validation.values import HOOK_NAMES
from .plans import _execution_inputs, _operations

POLICY = TargetPolicy(COMMAND, '1', (GATE,))


def prepare_authoring_proposal(plan, model, *, command_id, proposal_fields,
                                gates=(), strict=False):
    """Same native authoring target, changed publication kind and fixed scope.

    Returns an owned Proposal; this pure preparation performs no file writes.
    Actor, operation defaults and complete result payloads come from the plan.
    """
    require(type(plan) is ChangePlan and type(model) is TargetModel,
            'typed_authoring_proposal_inputs_required')
    plan = ChangePlan(plan.source_bytes); model = model.snapshot(); value = plan.data
    _operations(command_id, value['operations'])
    prepare_authoring_request(command_id=command_id.replace('.', ' '), actor=value['actor'],
        request_id=value['request_id'], operations=value['operations'], as_proposal=True, dry_run=True)
    require(type(proposal_fields) is dict and set(proposal_fields) <= {
        'identity', 'title', 'rationale', 'changes', 'model_provenance'}
        and {'identity', 'title', 'rationale', 'changes'} <= set(proposal_fields),
        'proposal_explicit_metadata_required')
    _, policy, selected = _execution_inputs(model, command_id, value['operations'],
        value['actor'], value['planned_at'], gates)
    checked = assess_change_target(plan, model, policy=policy, gates=selected, strict=strict)
    checked.require_valid()
    target = materialize_target(model, checked.publication_documents)
    inner = {k: v for k, v in value.items() if k != 'change_plan_sha256'}
    inner['base'] = build_proposal_basis(model).data
    inner['expected_result'] = {'model_root_sha256': build_proposal_basis(target).data['model_root_sha256']}
    proposal = prepare_proposal(change_plan=prepare_change_plan(inner), **proposal_fields)
    validate_proposal(ProposalContext(proposal.original, model))
    return proposal


def publication_gates(model, proposal, *, services=None):
    """Requalify the complete actual outer target on every native writer gate."""
    from ..qualification.project import validate_project
    services = native_services(services)
    original = proposal.original
    files = {**model.source_files, original.path: original.source_bytes}
    expected = {d.path: d.content for d in model.documents}
    expected[original.path] = original.source_bytes
    def provider(target, value):
        if value.binding.proposal_id == original.binding.proposal_id:
            require(value.source_bytes == original.source_bytes,
                    'proposal_create_record_changed', exit_code=6)
            return _initial_inputs(target, value, replace(services, proposal_inputs=None))
        return _initial_inputs(target, value, services)
    actual_services = replace(services, proposal_inputs=provider)
    def check(context):
        require({d.path: d.content for d in context.documents} == expected,
                'proposal_create_outer_target_changed', exit_code=6)
        validate_project(files, services=actual_services)
        return context.result()
    def dependencies(context):
        return context.dependency_result({key: list(context.all_ids) for key in context.subjects})
    return tuple(ModelGate(name, 'native-proposal-create-v1', dependencies, check,
        model._sources_sha256) for name in (
            *(name for name in HOOK_NAMES if name not in ('profile_lint', 'language_policy')),
            GATE, 'extension:target-resources'))


def publish_authoring_proposal(plan, model, *, command_id, proposal_fields,
        transaction_id, authority, gates=(), strict=False, package_files=(), services=None):
    """Publish only the prepared draft using the existing native transaction."""
    from .execution import _apply_saved_plan
    from ..changes import PublicationAuthority
    require(type(authority) is PublicationAuthority, 'proposal_host_authority_required', exit_code=7)
    require(type(plan) is ChangePlan and type(model) is TargetModel,
            'typed_authoring_proposal_inputs_required')
    from ..changes.request_ids import AuthoringError
    from ..changes._journal_codec import _transaction
    if type(strict) is not bool or type(gates) not in (list, tuple):
        raise AuthoringError('explicit_authoring_execution_options_required')
    gates = tuple(gates)
    _transaction(transaction_id)
    plan = ChangePlan(plan.source_bytes)
    value = plan.data
    _operations(command_id, value['operations'])
    prepare_authoring_request(command_id=command_id.replace('.', ' '), actor=value['actor'],
        operations=value['operations'], request_id=value['request_id'], as_proposal=True)
    from ._proposal_replay import replay_proposal
    replay = replay_proposal(plan, model, command_id=command_id, proposal_fields=proposal_fields)
    if replay is not None:
        return replay
    proposal = prepare_authoring_proposal(plan, model, command_id=command_id,
        proposal_fields=proposal_fields, gates=gates, strict=strict)
    selected = publication_gates(model, proposal, services=services)
    value = plan.data
    checked = prepare_change_target(model, [{'op': 'proposal_create', 'record': proposal.data}],
        change_plan_id=value['change_plan_id'], request_id=value['request_id'],
        actor=value['actor'], planned_at=value['planned_at'], scope_descriptor=_default_scope(),
        metadata_policy_version=value['metadata_policy_version'], policy=POLICY,
        gates=selected, strict=strict)
    checked.require_valid()
    result = _apply_saved_plan(checked.plan, model, command_id=COMMAND,
        transaction_id=transaction_id, authority=authority, gates=selected, strict=strict,
        package_files=package_files, bound_policy=POLICY)
    return {**result, 'proposal': proposal.data,
        'proposal_path': proposal.original.path, 'embedded_plan': proposal.data['change_plan'],
        'direct_plan_sha256': plan.sha256, 'publication_kind': 'proposal_draft',
        'review_validity': {'current_approval': False, 'human_decision_required': True}}
