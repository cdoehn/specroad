"""The real reference backend, before language decision and report projection.

These owned in-memory rankings are not serialized detector observations or
Evidence. The later decision policy consumes them without rereading a project
or replacing the original strings. Importing the adapter loads no dependency.
"""
from dataclasses import dataclass
import math
import platform
import sys
import unicodedata

from ._model_session import ModelSession
from ._reference_candidates import CANDIDATES, CANDIDATES_SHA256
from ._reference_model import MODEL_SHA256
from ._values import AnalyzerError, require
from .registry import builtin_descriptor
from .requests import AnalyzerRequest


@dataclass(frozen=True)
class ReferenceEngine:
    adapter_version: str
    library_versions: tuple
    model_sha256: str
    candidates: tuple
    candidates_sha256: str
    python_implementation: str
    python_version: str
    unicode_version: str


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


def _engine(descriptor):
    # Only reached after the explicitly requested, hash-checked model load.
    import numpy
    import py3langid
    require(py3langid.__version__ == '0.4.0', 'analyzer_library_version', exit_code=5)
    return ReferenceEngine(descriptor['adapter_version'],
        (('numpy', numpy.__version__), ('py3langid', py3langid.__version__)),
        MODEL_SHA256, CANDIDATES, CANDIDATES_SHA256, sys.implementation.name,
        platform.python_version(), unicodedata.unidata_version)


def _scores(model, text):
    require(tuple(model.labels) == CANDIDATES and model._norm_probs is True
            and model.min_confidence is None, 'analyzer_reference_model_state', exit_code=5)
    try:
        rows = model.rank(text)
    except (ValueError, ArithmeticError) as error:
        raise AnalyzerError('invalid_backend_output', exit_code=5) from error
    require(type(rows) is list and len(rows) == len(CANDIDATES),
            'invalid_backend_output', exit_code=5)
    scores = []
    for row in rows:
        require(type(row) in (list, tuple) and len(row) == 2,
                'invalid_backend_output', exit_code=5)
        label, score = row
        require(type(label) is str and label in CANDIDATES
                and type(score) in (int, float) and 0 <= score <= 1
                and math.isfinite(score), 'invalid_backend_output', exit_code=5)
        scores.append((label, float(score)))
    require(len({label for label, _ in scores}) == len(CANDIDATES),
            'invalid_backend_output', exit_code=5)
    return tuple(sorted(scores, key=lambda row: (-row[1], row[0])))


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
