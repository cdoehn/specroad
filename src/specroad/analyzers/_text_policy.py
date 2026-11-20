"""Versioned ASCII-edge length policy; never rewrites an original string."""
from ._values import require
from .registry import builtin_descriptor
from .requests import AnalyzerRequest


TEXT_POLICY_VERSION = 'ascii-edge-codepoints-v1'


POLICY_FIELDS = frozenset(('adapter', 'adapter_version', 'mismatch', 'undetermined',
    'compatible_coarse', 'unverifiable', 'min_text_codepoints', 'min_score', 'min_margin'))


def validate_minimum(value):
    require(type(value) is int and 1 <= value <= 10000,
            'analyzer_min_text_codepoints', exit_code=2)
    return value


def text_length(text):
    require(type(text) is str, 'analyzer_text_subject_required', exit_code=2)
    return len(text.strip('\t\n\v\f\r '))


def request_policy(request):
    require(type(request) is AnalyzerRequest, 'analyzer_request_required', exit_code=2)
    data = request.data
    known = builtin_descriptor().data
    entries = [entry for entry in data['analyzers'] if entry['descriptor'] == known]
    require(len(entries) == 1 and 'language_detection' in entries[0]['capabilities'],
            'analyzer_reference_not_requested', exit_code=2)
    settings = data['settings'][known['analyzer_id']]
    require(set(settings) == {'language_detection'},
            'analyzer_reference_settings_unsupported', exit_code=2)
    policy = settings['language_detection']
    require(type(policy) is dict and set(policy) == POLICY_FIELDS,
            'analyzer_materialized_language_policy_required', exit_code=2)
    require(policy['adapter'] == known['analyzer_id']
            and policy['adapter_version'] == known['adapter_version'],
            'analyzer_language_adapter_mismatch', exit_code=2)
    validate_minimum(policy['min_text_codepoints'])
    from .language_policy import validate_policy
    validate_policy(policy)
    return data, entries[0], policy
