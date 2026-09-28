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
_COMMANDS = _DIRECT | _PROPOSAL | _HUMAN_REVIEW | {'proposal apply'}


def select_route(command_id, actor, identity, dry_run, as_proposal):
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
