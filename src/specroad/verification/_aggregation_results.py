"""Pure priorities over validated, selected observations.

The adapter owns input validation, human waiver verification and report encoding.
These decisions neither resolve inputs nor access files, clocks or presentation.
"""
from ._required_keys import _key


def _aggregate_run(run):
    """Retain every blocking observation while applying the run priorities."""
    evidence = run['evidence']
    blockers = []
    for item in evidence:
        issues = list(item['reasons'])
        if item['unsupported_subject_ids']:
            issues.append('subject_context_unsupported')
        if item['freshness'] == 'stale':
            issues.append('required_evidence_stale')
        elif item['freshness'] != 'current':
            issues.append('evidence_context_incomplete')
        if item['result'] not in ('passed', 'failed'):
            issues.append('evidence_result_incomplete')
        elif item['freshness'] == 'current' and item['result'] == 'failed':
            issues.append('current_required_evidence_failed')
        if issues:
            blockers.append({'evidence_id': item['evidence_id'],
                'freshness': item['freshness'], 'result': item['result'],
                'reasons': sorted(set(issues))})
    if any(e['freshness'] == 'current' and e['result'] == 'failed' for e in evidence):
        result, reason = 'failed', 'current_required_evidence_failed'
    elif not evidence:
        result, reason = 'incomplete', 'required_run_missing'
    elif any(e['unsupported_subject_ids'] or e['freshness'] not in ('current', 'stale') or
             e['result'] not in ('passed', 'failed') for e in evidence):
        result, reason = 'incomplete', 'required_run_incomplete'
    elif all(e['freshness'] == 'stale' for e in evidence):
        result, reason = 'stale', 'required_evidence_stale'
    elif any(e['freshness'] == 'stale' for e in evidence):
        result, reason = 'incomplete', 'required_run_mixed_freshness'
    elif all(e['freshness'] == 'current' and e['result'] == 'passed' for e in evidence):
        result, reason = 'passed', 'all_required_evidence_passed'
    else:
        result, reason = 'incomplete', 'required_run_incomplete'
    return {**run, 'run_result': result, 'reason': reason,
            'blocking_observations': blockers}


def aggregate_checks(assessed, replaced):
    """Assess active runs per required key without deciding Subject status."""
    observed = {_key(check): check for check in assessed['checks']}
    checks = []
    for selected in replaced['checks']:
        runs = {row['run_id']: row for row in observed[_key(selected)]['runs']}
        active = [_aggregate_run(runs[run_id]) for run_id in selected['active_run_ids']]
        # This per-key value describes selected Evidence, not the input binding,
        # plan or waiver. The Subject below still applies all higher priorities.
        if any(run['run_result'] == 'failed' for run in active):
            outcome, reasons = 'failed', ['current_required_evidence_failed']
        elif not active:
            outcome, reasons = 'incomplete', ['required_run_missing']
        elif any(run['run_result'] == 'incomplete' for run in active):
            outcome = 'incomplete'
            reasons = sorted({run['reason'] for run in active if run['run_result'] == 'incomplete'})
        elif all(run['run_result'] == 'stale' for run in active):
            outcome, reasons = 'stale', ['required_evidence_stale']
        elif all(run['run_result'] == 'passed' for run in active):
            outcome, reasons = 'passed', ['all_required_evidence_passed']
        else:
            outcome, reasons = 'incomplete', ['required_check_mixed_freshness']
        checks.append({**selected, 'active_runs': active,
                       'evidence_result': outcome, 'reasons': reasons})
    return checks


def subject_result(*, applicability, waiver, plan_status, bound, coverage,
                   broken, selected, runs):
    """Apply section 10.5 without changing the validated bindings or Evidence."""
    if applicability['status'] == 'excluded':
        result, reasons = 'not_applicable', ['configuration_excluded']
    elif waiver is not None and waiver['waiver_result'] == 'waived':
        result, reasons = 'waived', ['valid_waiver']
    elif plan_status == 'not_planned':
        result, reasons = 'not_evaluated', ['verification_not_planned']
    elif bound['binding_status'] != 'ready':
        result, reasons = 'incomplete', list(bound['reasons'])
    elif coverage['coverage_status'] != 'ready':
        result, reasons = 'incomplete', list(coverage['reasons'])
    elif broken:
        result, reasons = 'incomplete', ['replacement_binding_changed']
    elif any(run['run_result'] == 'failed' for run in runs):
        result, reasons = 'failed', ['current_required_evidence_failed']
    elif plan_status == 'running':
        result, reasons = 'running', ['verification_running']
    elif not selected or not runs:
        result, reasons = 'incomplete', ['verification_contract_missing']
    elif any(run['run_result'] == 'incomplete' for run in runs):
        result = 'incomplete'
        reasons = sorted({run['reason'] for run in runs if run['run_result'] == 'incomplete'})
    elif any(check['active_runs'] and all(run['run_result'] == 'stale'
             for run in check['active_runs']) for check in selected):
        result, reasons = 'stale', ['required_evidence_stale']
    elif all(run['run_result'] == 'passed' for run in runs):
        result, reasons = 'passed', ['all_required_evidence_passed']
    else:
        result = 'incomplete'
        reasons = sorted({reason for check in selected for reason in check['reasons']
                          if check['evidence_result'] == 'incomplete'})
    return result, reasons
