"""Complete original strings behind an explicit, materialized length policy.

Prepared rankings are internal values, not final reports or language matches.
The backend alone may normalize its working copy. No project file is written.
"""
from dataclasses import dataclass

from ._model_session import ModelSession
from ._reference_backend import ReferenceEngine, _engine, _scores
from ._values import AnalyzerError, require
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
    return data, entries[0], policy


@dataclass(frozen=True)
class PreparedSubject:
    subject_key: str
    value_sha256: str
    status: str
    reason: str | None
    scores: tuple


@dataclass(frozen=True)
class PreparedLanguage:
    request_id: str
    snapshot_sha256: str
    descriptor_sha256: str
    preprocessing_version: str
    min_text_codepoints: int
    engine: ReferenceEngine | None
    subjects: tuple


def prepare_request(request):
    """Abstain on short strings before any optional dependency is loaded."""
    data, entry, policy = request_policy(request)
    subjects = sorted(data['subjects'], key=lambda subject: subject['subject_key'])
    require(all(type(subject['value']) is str for subject in subjects),
            'analyzer_text_subject_required', exit_code=2)
    minimum = policy['min_text_codepoints']
    prepared, engine, unavailable = [], None, None
    with ModelSession() as session:
        for subject in subjects:
            if text_length(subject['value']) < minimum:
                status, reason, scores = 'undetermined', 'insufficient_text', ()
            else:
                if engine is None and unavailable is None:
                    try:
                        session.model()
                        engine = _engine(entry['descriptor'])
                    except AnalyzerError as error:
                        unavailable = error.reason
                if unavailable is not None:
                    status, reason, scores = 'unavailable', unavailable, ()
                else:
                    try:
                        scores = _scores(session.model(), subject['value'])
                        status, reason = 'ranked', None
                    except AnalyzerError as error:
                        scores = ()
                        if error.reason == 'invalid_backend_output':
                            status, reason = 'failed', 'invalid_backend_output'
                        else:
                            unavailable = error.reason
                            status, reason = 'unavailable', unavailable
            prepared.append(PreparedSubject(subject['subject_key'], subject['value_sha256'],
                                            status, reason, scores))
    return PreparedLanguage(data['request_id'], data['snapshot_sha256'],
        entry['descriptor_sha256'], TEXT_POLICY_VERSION, minimum, engine, tuple(prepared))
