"""Materialized language actions, separate from execution and language proof."""
from dataclasses import dataclass

from ._values import decode, encoded, require
from ._report_values import ENGINE_FACTS, exact_coverage
from ._text_policy import POLICY_FIELDS, TEXT_POLICY_VERSION, validate_minimum
from ._score_values import parse_threshold
from .language_comparison import compare_decisions
from .registry import builtin_descriptor
from .reports import create_report, subject_result

__all__ = ('ACTION_FIELDS', 'materialize_policy', 'validate_policy', 'report_outcome',
           'execution_outcome', 'report_engine', 'LanguageAssessment', 'assess_language')


ACTION_FIELDS = ('mismatch', 'undetermined', 'compatible_coarse', 'unverifiable')


def materialize_policy(overrides=None):
    policy = dict(adapter='specroad.py3langid', adapter_version='1.0.0', mismatch='warning',
        undetermined='info', compatible_coarse='info', unverifiable='info',
        min_text_codepoints=20, min_score='0.900000000000', min_margin='0.100000000000')
    require(overrides is None or type(overrides) is dict, 'analyzer_policy_object_required', exit_code=2)
    policy.update({} if overrides is None else overrides)
    validate_policy(policy)
    return decode(encoded(policy))


def validate_policy(policy):
    require(type(policy) is dict and set(policy) == POLICY_FIELDS,
            'analyzer_materialized_language_policy_required', exit_code=2)
    require(policy['adapter'] == 'specroad.py3langid' and policy['adapter_version'] == '1.0.0',
            'analyzer_language_adapter_mismatch', exit_code=2)
    for name in ACTION_FIELDS:
        require(type(policy[name]) is str and policy[name] in ('ignore', 'info', 'warning', 'error'),
                'analyzer_language_action', '/settings/language_detection/' + name, exit_code=2)
    validate_minimum(policy['min_text_codepoints'])
    parse_threshold(policy['min_score'], 'min_score')
    parse_threshold(policy['min_margin'], 'min_margin')


def report_outcome(values, *, fail_on='error'):
    """A completed observation is neither a language confirmation nor approval."""
    require(type(fail_on) is str and fail_on in ('warning', 'error'),
            'analyzer_fail_threshold', exit_code=2)
    complete = bool(values) and all(v['run_status'] == 'complete' for v in values)
    failed = any(f['severity'] == 'error' or fail_on == 'warning' and f['severity'] == 'warning'
                 for value in values for f in value['findings'])
    known = builtin_descriptor().data
    def compatible(subject):
        payload = subject['payload'].get('specroad.language_detection')
        comparison = payload.get('comparison') if type(payload) is dict else None
        decision = payload.get('decision') if type(payload) is dict else None
        return (subject['status'] == 'done' and type(comparison) is dict
                and type(decision) is dict and decision.get('status') == 'detected'
                and decision.get('reason') is None
                and comparison.get('comparison_version') == 'language-comparison-v1'
                and comparison.get('declared_language') == subject['declared_language']
                and comparison.get('detected_language') == decision.get('language')
                and type(decision.get('language')) is str
                and comparison.get('language_resolution') == 'primary_language'
                and comparison.get('region_checked') is False
                and comparison.get('script_checked') is False
                and comparison.get('status') == 'compatible')
    confirmed = complete and all(v['analyzer']['descriptor'] == known and bool(v['subjects'])
        and all(compatible(s) for s in v['subjects']) for v in values)
    return dict(execution_complete=complete, all_languages_confirmed=confirmed,
                findings_failed=failed, gate_passed=complete and not failed,
                exit_code=5 if not complete else 1 if failed else 0)


def execution_outcome(reports, *, fail_on='error'):
    return report_outcome([report.data for report in reports], fail_on=fail_on)


def report_engine(engine):
    """Only measured facts; missing numeric inventory stays explicitly unknown."""
    value = dict(adapter_version='1.0.0',
        **{name: {'value': None, 'reason': 'engine_not_loaded'} for name in ENGINE_FACTS})
    if engine is not None:
        facts = dict(library_versions=dict(engine.library_versions), model_sha256=engine.model_sha256,
            candidates=list(engine.candidates), candidates_sha256=engine.candidates_sha256,
            preprocessing_version=TEXT_POLICY_VERSION, unicode_version=engine.unicode_version)
        value['adapter_version'] = engine.adapter_version
        for key, item in facts.items():
            value[key] = dict(value=item, reason=None)
        for key in ('runtime_fingerprint', 'numpy_fingerprint'):
            value[key] = dict(value=None, reason='numeric_inventory_unavailable')
    return value


@dataclass(frozen=True)
class LanguageAssessment:
    report: object
    fail_on: str

    @property
    def data(self):
        return execution_outcome((self.report,), fail_on=self.fail_on)


def assess_language(request, decisions, *, registry, fail_on='error', run_id=None):
    """Bind original decisions, registry and actions into a complete T.4 report."""
    from ._text_policy import request_policy
    data, _, policy = request_policy(request)
    validate_policy(policy)
    require(type(fail_on) is str and fail_on in ('warning', 'error'),
            'analyzer_fail_threshold', exit_code=2)
    compared = compare_decisions(request, decisions, registry=registry)
    originals = {s['subject_key']: s for s in data['subjects']}
    subjects, findings = [], []
    for selected in compared.subjects:
        decision, comparison = selected.decision, selected.comparison
        status = {'detected': 'done', 'undetermined': 'undetermined',
                  'failed': 'failed', 'unavailable': 'open'}[decision.status]
        action = comparison.status if comparison is not None else decision.status
        severity = policy.get(action, 'ignore')
        refs = []
        if severity != 'ignore':
            identity = 'language:' + selected.subject_key
            refs.append(identity)
            findings.append(dict(finding_id=identity, code='specroad.language.' + action,
                severity=severity, subject_keys=[selected.subject_key],
                message='Language observation: ' + action,
                rationale='Materialized language policy; no region, script or approval claim.',
                details={'specroad.language_observation': dict(kind='json', value=decision.data)}))
        subjects.append(subject_result(originals[selected.subject_key], status=status,
            payload={'specroad.language_detection': dict(decision=decision.data,
                comparison=None if comparison is None else comparison.data)}, findings=refs))
    coverage = exact_coverage(subjects)
    run_status = ('failed' if coverage['failed'] else
        'unavailable' if coverage['open'] and coverage['open'] == coverage['expected'] else
        'partial' if coverage['open'] else 'complete')
    report = create_report(request, analyzer_id='specroad.py3langid', engine=report_engine(decisions.engine),
        subjects=subjects, findings=findings, run_status=run_status, run_id=run_id)
    execution_outcome((report,), fail_on=fail_on)
    return LanguageAssessment(report, fail_on)
