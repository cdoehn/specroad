"""Shared materialized actions and independent execution/confirmation outcome."""
from ._values import decode, encoded, require
from ._text_policy import POLICY_FIELDS, validate_minimum
from ._score_values import parse_threshold
from .registry import builtin_descriptor


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
