"""Generic request bindings for the explicitly invoked reference backend.

Owned in-memory rankings are not serialized observations or Evidence. Later
policies consume them without rereading a project or replacing original text.
"""
from dataclasses import dataclass

from ._model_session import ModelSession
from ._reference_backend import ReferenceEngine as ReferenceEngine, _engine, _scores
from ._values import require
from .registry import builtin_descriptor
from .requests import AnalyzerRequest


@dataclass(frozen=True)
class SubjectRanking:
    subject_key: str
    value_sha256: str
    scores: tuple


@dataclass(frozen=True)
class ReferenceRanking:
    request_id: str
    snapshot_sha256: str
    descriptor_sha256: str
    engine: ReferenceEngine
    subjects: tuple


def rank_request(request):
    """Rank complete strings independently with one owned original model.

    Only the exact shipped descriptor and empty reference settings are supported
    at this stage. Project policy cannot restrict the candidate universe. Raw
    normalized scores stay internal; quantization, abstention and language
    comparison belong to their separately planned decision steps.
    """
    require(type(request) is AnalyzerRequest, 'analyzer_request_required', exit_code=2)
    data = request.data
    known = builtin_descriptor().data
    entries = [entry for entry in data['analyzers'] if entry['descriptor'] == known]
    require(len(entries) == 1, 'analyzer_reference_not_requested', exit_code=2)
    require(data['settings'][known['analyzer_id']] == {},
            'analyzer_reference_settings_unsupported', exit_code=2)
    subjects = sorted(data['subjects'], key=lambda subject: subject['subject_key'])
    require(all(type(subject['value']) is str for subject in subjects),
            'analyzer_text_subject_required', exit_code=2)
    with ModelSession() as session:
        model = session.model()
        engine = _engine(known)
        rankings = tuple(SubjectRanking(subject['subject_key'], subject['value_sha256'],
            _scores(model, subject['value'])) for subject in subjects)
    return ReferenceRanking(data['request_id'], data['snapshot_sha256'],
                            entries[0]['descriptor_sha256'], engine, rankings)
