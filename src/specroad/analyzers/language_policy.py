"""Materialized language actions, separate from execution and language proof."""
from dataclasses import dataclass

from ._values import require
from ._report_values import ENGINE_FACTS, exact_coverage
from ._text_policy import TEXT_POLICY_VERSION
from .language_comparison import compare_decisions
from .reports import create_report, subject_result

__all__ = ('ACTION_FIELDS', 'materialize_policy', 'validate_policy', 'report_outcome',
           'execution_outcome', 'report_engine', 'LanguageAssessment', 'assess_language')


from ._policy_values import (ACTION_FIELDS as ACTION_FIELDS,
    materialize_policy as materialize_policy, validate_policy as validate_policy,
    report_outcome as report_outcome, execution_outcome as execution_outcome)


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
