"""Fixed normative command routing; independent of CLI/UI and analyzers."""
from .request_ids import AuthoringError

_DIRECT = frozenset({'change apply', 'format', 'artifact create', 'artifact update',
    'relation add', 'relation remove', 'lifecycle transition', 'document create',
    'section add', 'section move', 'section remove', 'block add', 'block update',
    'block remove', 'view create', 'evidence record', 'evidence import',
    'baseline create', 'import apply', 'migrate apply', 'merge apply'})
_PROPOSAL = frozenset({'proposal create', 'proposal change add', 'proposal change update',
    'proposal change remove', 'proposal change move', 'proposal review start'})
_HUMAN_REVIEW = frozenset({'proposal review', 'relation review'})
from ..model.plan_command_ids import COMMANDS as _PLAN_COMMANDS
_DIRECT = _DIRECT | {command.replace('.', ' ') for command in _PLAN_COMMANDS}
_COMMANDS = _DIRECT | _PROPOSAL | _HUMAN_REVIEW | {'proposal apply'}


def select_route(command_id, actor, identity, dry_run, as_proposal):
    # A Proposal preview cannot turn a nonhuman statement into a human review.
    if command_id == 'proposal review' and actor.actor_type != 'human':
        raise AuthoringError('human_review_required', pointer='/actor', exit_code=7)
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
    return route


def validate_proposal_operations(command_id, operations):
    if any(op['op'] == 'proposal_change' for op in operations):
        from ..proposals._change_control import change_mode
        change_mode(operations)
        if command_id != 'proposal change ' + operations[0]['action']:
            raise AuthoringError('proposal_change_specialist_required', exit_code=7)
    if any(op['op'] == 'proposal_create' for op in operations):
        from ..proposals._create_control import creation_mode
        if command_id != 'proposal create':
            raise AuthoringError('proposal_create_specialist_required', exit_code=7)
        creation_mode(operations)
    if any(op['op'] == 'proposal_control' for op in operations):
        if command_id not in ('proposal review start', 'proposal review', 'proposal apply'):
            raise AuthoringError('proposal_control_specialist_required', exit_code=7)
        if command_id == 'proposal review start':
            from ..proposals._review_control import review_start_mode, reports
            review_start_mode(operations)
            reports(operations[0])
        if command_id == 'proposal review':
            from ..proposals._decision_control import review_mode
            from ..proposals._decision_evidence import operation_proof
            review_mode(operations)
            operation_proof(operations[0])
    if operations and command_id == 'proposal apply':
        from ..proposals._apply_control import apply_mode, operation_proof
        from ..proposals.values import require
        require(apply_mode(operations), 'proposal_apply_evidence_required')
        operation_proof(operations[-1])
