"""Deterministic requirement, kind and declared-dimension coverage observations."""
from dataclasses import dataclass
from hashlib import sha256

from ..model.canonical import canonical_json_bytes
from ..storage.json_syntax import parse_json_object
from ._required_keys import _key
from .read_input import checked_model_input


@dataclass(frozen=True, init=False)
class VerificationCoverage:
    """Owned coverage of supplied inputs, not an execution or release proof."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use assess_verification_coverage')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Coverage is not readiness or approval')


def _counts(values):
    counts = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _check_totals(checks):
    runs = [run for check in checks for run in check['active_runs']]
    evidence = [item for run in runs for item in run['evidence']]
    return {'required_checks': len(checks), 'active_runs': len(runs),
        'evidence_observations': len(evidence),
        'check_results': _counts(check['evidence_result'] for check in checks),
        'run_results': _counts(run['run_result'] for run in runs),
        'evidence_results': _counts(item['result'] for item in evidence),
        'evidence_freshness': _counts(item['freshness'] for item in evidence)}


def _requirement_totals(rows):
    return {'requirements': len(rows),
        'requirement_ids': [row['requirement_id'] for row in rows],
        'verification_results': _counts(row['verification_result'] for row in rows),
        **_check_totals([check for row in rows for check in row['checks']])}


def assess_verification_coverage(model, verification):
    """Use exactly one computed selection for all independent coverage axes.

    Dimensions are the declared slot values, never guessed from test names.
    Evidence counts are per required-key observation, not unique executions.
    A check's evidence result never replaces its Subject's higher priorities.
    """
    model, bound = checked_model_input(model, verification)
    documents = {parse_json_object(d.content)['id']: parse_json_object(d.content)
                 for d in model.documents}
    aggregation = bound['aggregation']
    selection = aggregation['replacement_assessment']['assessment']['selection']
    required = selection['coverage']['required_set']['required_checks']
    rows = []
    for subject in aggregation['subjects']:
        record = documents[subject['subject_artifact_id']]
        if record['artifact_type'] != 'requirement':
            continue
        observed = {_key(check): check for check in subject['checks']}
        checks = []
        for key in required:
            if key['subject_artifact_id'] != record['id']:
                continue
            detail = observed.get(_key(key))
            checks.append({**key, **(detail if detail is not None else {
                'active_runs': [], 'evidence_result': 'incomplete',
                'reasons': selection['coverage']['reasons']}),
                'run_selection_evaluated': detail is not None})
        rows.append({'requirement_id': record['id'], 'requirement_kind': record['requirement_kind'],
            'verification_plan_status': subject['verification_plan_status'],
            'verification_result': subject['verification_result'], 'reasons': subject['reasons'],
            'applicability': subject['applicability'], 'checks': checks,
            'totals': _check_totals(checks)})
    kinds = sorted({row['requirement_kind'] for row in rows}, key=lambda s: s.encode('utf-8'))
    dimensions = sorted({check['dimension'] for row in rows for check in row['checks']},
                        key=lambda s: s.encode('utf-8'))
    by_dimension = []
    for dimension in dimensions:
        selected = [row for row in rows if any(c['dimension'] == dimension for c in row['checks'])]
        checks = [check for row in selected for check in row['checks'] if check['dimension'] == dimension]
        by_dimension.append({'dimension': dimension,
            'requirement_ids': [row['requirement_id'] for row in selected],
            'verification_results': _counts(row['verification_result'] for row in selected),
            'checks': checks, 'totals': _check_totals(checks)})
    report = {'format_version': 'verification-coverage-v1',
        'validation_scope': 'supplied_whole_project_requirement_coverage',
        'project_id': bound['project_id'], 'input_sha256': bound['input_sha256'],
        'summary': verification.summary, 'requirements': rows, 'totals': _requirement_totals(rows),
        'by_kind': [{'requirement_kind': kind,
            **_requirement_totals([row for row in rows if row['requirement_kind'] == kind])}
            for kind in kinds], 'by_dimension': by_dimension,
        'aggregation': aggregation, 'diagnostics': aggregation['diagnostics'],
        'input_bytes_verified': aggregation['input_bytes_verified'],
        'input_roles_checked': aggregation['input_roles_checked'],
        'project_files_verified': False, 'project_required_checks_complete': False,
        'full_verification_evaluated': False, 'external_run_verified': False,
        'release_readiness_evaluated': False, 'test_code_executed': False,
        'write_authorized': False, 'approval_granted': False}
    result = object.__new__(VerificationCoverage)
    object.__setattr__(result, '_encoded', canonical_json_bytes(report))
    return result
