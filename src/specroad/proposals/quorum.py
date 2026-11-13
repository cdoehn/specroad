"""Pure Proposal quorum policy, shared by history and new decisions; no UI."""
from .values import require


def approvals(findings):
    selected = {}
    for row in findings:
        if not row['binding_current']:
            continue
        key = row['actor_id']
        if row['decision'] in ('rejected', 'withdrawn'):
            selected.pop(key, None)
        elif row['human']:
            selected[key] = row['decision_current']
    return selected


def effective_actors(findings):
    return sorted(actor for actor, current in approvals(findings).items() if current)


def decision_outcome(actors, actor_id, decision, minimum):
    selected = set(actors)
    if decision == 'approved':
        selected.add(actor_id)
        status = 'approved' if len(selected) >= minimum else 'in_review'
    else:
        selected.discard(actor_id)
        status = 'rejected'
    return status, len(selected)


def decision_state(status, decision):
    allowed = ('in_review',) if decision == 'approved' else (
        ('in_review', 'approved') if decision == 'withdrawn' else ('draft', 'in_review', 'approved'))
    require(status in allowed, 'proposal_review_state_invalid')


def review_outcome(history, actor_id, decision):
    """Derive a new decision from retained ordered findings, never erase a row."""
    actors = effective_actors(history['reviews'])
    if decision == 'withdrawn':
        require(actor_id in approvals(history['reviews']), 'proposal_own_approval_required', exit_code=7)
        status = 'rejected' if history['observed_status'] == 'approved' else 'in_review'
        return status, len(set(actors) - {actor_id})
    return decision_outcome(actors, actor_id, decision, history['minimum_human_approvals'])
