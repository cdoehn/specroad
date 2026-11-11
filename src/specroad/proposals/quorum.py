"""Pure Proposal quorum policy, shared by history and new decisions; no UI."""


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
