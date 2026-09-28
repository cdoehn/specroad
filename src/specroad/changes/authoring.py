"""Pure single-user authoring policy, not authentication or a receipt store.

Caller-declared actors remain audit/policy input. Only trusted application code
selects the command. A proposal route never authorizes direct target writes.
"""
from .values import ChangePlan, ChangeOperation
from ..model.audit import actor as parse_actor
from ..model.audit_values import Actor
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError

from .authoring_values import AUTHORING_VERSION, AuthoringRequest
from ._authoring_policy import _COMMANDS, select_route
from .request_ids import AuthoringError, NormativeRequestId, normalize_request_id


def normalize_authoring_actor(value):
    try:
        if type(value) is Actor:
            return Actor(value.actor_type, value.actor_id)
        return parse_actor(value)
    except ModelError as error:
        raise AuthoringError(error.reason, pointer='/actor' + error.pointer) from error


def prepare_authoring_request(*, command_id, actor, operations, request_id=None,
                              dry_run=False, as_proposal=False):
    """Validate declared actor/ID and route a specific normative operation list.

    Dry-runs are non-publishing previews: no AI/CI request-ID requirement and
    no writer authorization. Proposal exceptions only select the specialist
    workflow; approval validity is never inferred from command names.
    """
    if type(command_id) is not str or command_id not in _COMMANDS:
        raise AuthoringError('unknown_normative_command', pointer='/command_id')
    if type(dry_run) is not bool or type(as_proposal) is not bool:
        raise AuthoringError('explicit_boolean_options_required')
    actor = normalize_authoring_actor(actor)
    identity = normalize_request_id(request_id)
    route = select_route(command_id, actor, identity, dry_run, as_proposal)
    if type(operations) not in (list, tuple):
        raise AuthoringError('explicit_operation_sequence_required', pointer='/operations')
    owned = [ChangeOperation(op).data for op in operations]
    return AuthoringRequest._create({
        'format_version': AUTHORING_VERSION, 'namespace': 'normative_write',
        'command_id': command_id, 'actor': actor.as_fields(),
        'request_id': None if identity is None else identity.value,
        'operations': owned, 'operation_sequence_sha256': canonical_json_sha256(owned),
        'dry_run': dry_run, 'as_proposal': as_proposal, 'route': route,
        'request_id_required': not dry_run and actor.actor_type in ('ai', 'ci'),
        'actor_authenticated': False, 'write_authorized': False,
        'specialist_required': route not in ('preview', 'direct'),
        'receipt_checked': False, 'idempotency_guaranteed': False})


def bind_plan_authoring(plan, *, dry_run=False, as_proposal=False):
    """Bind the exact saved plan, not a separately relabelled actor or request."""
    if type(plan) is not ChangePlan:
        raise AuthoringError('typed_plan_required')
    # Re-read bytes rather than trusting mutable objects supplied by a caller.
    plan = ChangePlan(plan.source_bytes)
    data = plan.data
    request = prepare_authoring_request(command_id='change apply', actor=data['actor'],
        operations=data['operations'], request_id=data['request_id'],
        dry_run=dry_run, as_proposal=as_proposal)
    return AuthoringRequest._create({**request.data, 'plan_sha256': plan.sha256,
        'base_model_root_sha256': data['base']['model_root_sha256'],
        'scope_descriptor': data['base']['scope_descriptor']})


def require_direct_authoring(plan, *, as_proposal=False):
    """Reject specialist routes before any generic transaction can be opened."""
    request = bind_plan_authoring(plan, as_proposal=as_proposal)
    if request.data['route'] != 'direct':
        raise AuthoringError('proposal_workflow_required', exit_code=7)
    return request
