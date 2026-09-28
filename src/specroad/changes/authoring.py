"""Pure single-user authoring policy, not authentication or a receipt store.

Caller-declared actors remain audit/policy input. Only trusted application code
selects the command. A proposal route never authorizes direct target writes.
"""
from dataclasses import dataclass
import re
from .errors import ChangePlanError
from .values import ChangePlan, ChangeOperation
from ..model.audit import actor as parse_actor
from ..model.audit_values import Actor
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object

AUTHORING_VERSION = 'authoring-policy-v1'
REQUEST_PATTERN = r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}'


class AuthoringError(ChangePlanError):
    """Usage or policy rejection before invoking a normative writer."""
    def __init__(self, reason, *, pointer='', exit_code=2):
        super().__init__(reason, pointer=pointer, code='SRV146')
        self.exit_code = exit_code

    def diagnostic(self):
        return {**super().diagnostic(), 'write_state': 'not_committed',
                'authorization_granted': False}


@dataclass(frozen=True)
class NormativeRequestId:
    """Caller-assigned write namespace. No strip/casefold/UUID substitution."""
    value: str

    def __post_init__(self):
        if type(self.value) is not str or re.fullmatch(REQUEST_PATTERN, self.value) is None:
            raise AuthoringError('invalid_normative_request_id', pointer='/request_id')

    @property
    def namespace(self):
        return 'normative_write'


def normalize_request_id(value):
    if value is None:
        return None
    if type(value) is NormativeRequestId:
        return NormativeRequestId(value.value)
    # Foreign typed IDs, including analyzer request objects, are never coerced.
    return NormativeRequestId(value)


def normalize_authoring_actor(value):
    try:
        if type(value) is Actor:
            return Actor(value.actor_type, value.actor_id)
        return parse_actor(value)
    except ModelError as error:
        raise AuthoringError(error.reason, pointer='/actor' + error.pointer) from error


_DIRECT = frozenset({'change apply', 'format', 'artifact create', 'artifact update',
    'relation add', 'relation remove', 'lifecycle transition', 'document create',
    'section add', 'section move', 'section remove', 'block add', 'block update',
    'block remove', 'view create', 'evidence record', 'evidence import',
    'baseline create', 'import apply', 'migrate apply', 'merge apply'})
_PROPOSAL = frozenset({'proposal create', 'proposal change add', 'proposal change update',
    'proposal change remove', 'proposal change move', 'proposal review start'})
_HUMAN_REVIEW = frozenset({'proposal review', 'relation review'})
_COMMANDS = _DIRECT | _PROPOSAL | _HUMAN_REVIEW | {'proposal apply'}


@dataclass(frozen=True, init=False)
class AuthoringRequest:
    """Bound policy routing result, never a bearer capability for a writer."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use prepare_authoring_request or bind_plan_authoring')

    @classmethod
    def _create(cls, data):
        obj = object.__new__(cls)
        object.__setattr__(obj, '_encoded', canonical_json_bytes(data))
        return obj

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return canonical_json_sha256(self.data)

    def __bool__(self):
        raise TypeError('Inspect the route; this object is not a write permission')


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
    if not dry_run and actor.actor_type in ('ai', 'ci') and identity is None:
        raise AuthoringError('normative_request_id_required', pointer='/request_id')
    if not dry_run and command_id in _HUMAN_REVIEW and actor.actor_type != 'human':
        raise AuthoringError('human_review_required', pointer='/actor', exit_code=7)
    if (not dry_run and actor.actor_type == 'ai' and command_id in _DIRECT
            and not as_proposal):
        raise AuthoringError('ai_requires_proposal', pointer='/as_proposal', exit_code=7)
    if command_id not in _DIRECT | {'relation review'} and as_proposal:
        raise AuthoringError('as_proposal_not_applicable', pointer='/as_proposal')
    if dry_run:
        route = 'preview'
    elif as_proposal:
        route = 'proposal_authoring'
    elif command_id in _PROPOSAL:
        route = 'proposal_management'
    elif command_id == 'proposal apply':
        route = 'approved_proposal_apply'
    elif command_id in _HUMAN_REVIEW:
        route = 'human_review'
    else:
        route = 'direct'
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
