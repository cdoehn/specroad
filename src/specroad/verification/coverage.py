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


def _gaps(rows):
    """Independent overlapping sets; an unevaluated run is never a missing run."""
    applicable = [row for row in rows if row['applicability']['status'] != 'excluded']
    checks = [check for row in applicable for check in row['checks']]
    missing, stale, incomplete = [], [], []
    for check in checks:
        key = {name: check[name] for name in ('subject_artifact_id', 'contract_id', 'test_id', 'check_id')}
        for run in check['active_runs']:
            if not run['evidence']:
                missing.append({**key, 'run_id': run['run_id']})
            for observation in run['evidence']:
                item = {**key, 'run_id': run['run_id'], 'evidence_id': observation['evidence_id']}
                if observation['freshness'] == 'stale':
                    stale.append(item)
                if observation['freshness'] not in ('current', 'stale') or observation['result'] not in ('passed', 'failed'):
                    incomplete.append(item)
    missing_ids = {item['subject_artifact_id'] for item in missing}
    stale_ids = {item['subject_artifact_id'] for item in stale}
    result = {
        'requirements_without_contract': [r['requirement_id'] for r in applicable if not r['checks']],
        'requirements_without_test_reference': [r['requirement_id'] for r in applicable
            if not any(c['test_id'] is not None for c in r['checks'])],
        'requirements_with_unselected_checks': [r['requirement_id'] for r in applicable
            if any(not c['run_selection_evaluated'] for c in r['checks'])],
        'requirements_without_evidence': [r['requirement_id'] for r in applicable if r['checks']
            and all(c['run_selection_evaluated'] for c in r['checks'])
            and not any(run['evidence'] for c in r['checks'] for run in c['active_runs'])],
        'requirements_with_missing_runs': [r['requirement_id'] for r in applicable if r['requirement_id'] in missing_ids],
        'requirements_with_stale_evidence': [r['requirement_id'] for r in applicable if r['requirement_id'] in stale_ids],
        'checks_without_test_reference': [{k: c[k] for k in
            ('subject_artifact_id', 'contract_id', 'test_id', 'check_id', 'dimension')}
            for c in checks if c['test_id'] is None],
        'unselected_checks': [{k: c[k] for k in
            ('subject_artifact_id', 'contract_id', 'test_id', 'check_id', 'dimension')}
            for c in checks if not c['run_selection_evaluated']],
        'missing_runs': missing, 'stale_evidence': stale, 'incomplete_evidence': incomplete}
    return {**result, 'counts': {name: len(items) for name, items in result.items()}}


def assess_verification_coverage(model, verification=None, *, currentness=None):
    """Use exactly one computed selection for all independent coverage axes.

    Dimensions are the declared slot values, never guessed from test names.
    Evidence counts are per required-key observation, not unique executions.
    A check's evidence result never replaces its Subject's higher priorities.
    """
    if currentness is not None:
        from .currentness_input import checked_currentness_model
        _, observed = checked_currentness_model(model, currentness, verification=verification)
        report = {**observed['observation']['coverage'], 'currentness': observed}
        result = object.__new__(VerificationCoverage)
        object.__setattr__(result, '_encoded', canonical_json_bytes(report))
        return result
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
    gaps = _gaps(rows)
    report = {'format_version': 'verification-coverage-v1',
        'validation_scope': ('supplied_scope_requirement_coverage' if bound['explicit_scope']
                             else 'supplied_whole_project_requirement_coverage'),
        'project_id': bound['project_id'], 'input_sha256': bound['input_sha256'],
        'summary': verification.summary, 'requirements': rows, 'totals': _requirement_totals(rows),
        'selection_status': ('missing' if bound['evaluation'] is None else
                             'selected' if selection['run_selection_evaluated'] else 'incomplete'),
        'input_binding_status': aggregation['input_binding']['binding_status'], 'gaps': gaps,
        'by_release': ([] if bound['release_selection'] is None else [{
            **bound['release_selection'], 'totals': _requirement_totals(rows), 'gaps': gaps}]),
        'evidence_dispositions': aggregation['replacement_assessment']['assessment']['evidence_dispositions'],
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
