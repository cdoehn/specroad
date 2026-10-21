"""Resolve replacement dependencies without producing an aggregate result.

The caller supplies validated topology, native run observations and complete
old-set bindings. This stage only resolves terminal closure and binding issues;
it neither changes the supplied values nor interprets them as verification success.
"""
from .evaluation import _replacement_order


def resolve_replacement_graph(graph, runs, observations):
    """Return terminal closure, transitive issues and original terminal results."""
    terminals, issues, terminal_checks = {}, {}, {}
    for run_id in _replacement_order(graph):
        if run_id not in graph:
            terminals[run_id] = {run_id}
            observed = runs.get(run_id, {}).get('evidence', [])
            reasons = []
            if not observed:
                reasons.append('replacement_run_missing')
            else:
                if any(e['freshness'] != 'current' for e in observed):
                    reasons.append('replacement_run_not_current')
                if any(e['result'] not in ('passed', 'failed') for e in observed):
                    reasons.append('replacement_run_incomplete')
            issues[run_id] = {(run_id, reason) for reason in reasons}
            terminal_checks[run_id] = {'run_id': run_id,
                'presence': 'present' if observed else 'missing',
                'current_complete': not reasons, 'reasons': reasons,
                'evidence': [{field: item[field] for field in
                    ('evidence_id', 'artifact_sha256', 'source_sha256', 'freshness', 'result')}
                    for item in observed]}
        else:
            terminals[run_id] = set().union(*(terminals[child] for child in graph[run_id]))
            issues[run_id] = set().union(*(issues[child] for child in graph[run_id]))
            if not observations[run_id]['evidence_set_matches']:
                issues[run_id].add((run_id, 'replaced_evidence_set_changed'))
            # Excluded records cannot satisfy an absent required candidate,
            # including an intermediate run in a replacement chain.
            if not observations[run_id]['old_run_observed']:
                issues[run_id].add((run_id, 'replaced_run_missing'))
    return terminals, issues, terminal_checks
