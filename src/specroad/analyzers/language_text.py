"""Complete original strings behind an explicit, materialized length policy.

Prepared rankings are internal values, not final reports or language matches.
The backend alone may normalize its working copy. No project file is written.
"""
from dataclasses import dataclass

from ._model_session import ModelSession
from ._reference_backend import ReferenceEngine, _engine, _scores
from ._values import AnalyzerError, require
from ._text_policy import (TEXT_POLICY_VERSION, POLICY_FIELDS as POLICY_FIELDS,
    request_policy as request_policy, text_length, validate_minimum as validate_minimum)


__all__ = ('PreparedSubject', 'PreparedLanguage', 'prepare_request', 'request_policy',
           'text_length', 'validate_minimum', 'TEXT_POLICY_VERSION', 'POLICY_FIELDS')

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
