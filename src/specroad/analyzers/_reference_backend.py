"""Private original-library ranking behind the generic request boundary.

No AnalyzerRequest, worker wire format or project policy is interpreted here.
Imports remain passive; only the explicit caller owns and loads the model.
"""
from dataclasses import dataclass
import math
import platform
import sys
import unicodedata

from ._reference_candidates import CANDIDATES, CANDIDATES_SHA256
from ._reference_model import MODEL_SHA256
from ._values import AnalyzerError, require


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


def _engine(descriptor):
    # Only reached after the explicitly requested, hash-checked model load.
    try:
        import numpy
        import py3langid
        versions = (('numpy', numpy.__version__), ('py3langid', py3langid.__version__))
    except (ImportError, AttributeError) as error:
        raise AnalyzerError('analyzer_model_unavailable', exit_code=5) from error
    require(all(type(version) is str and version for _, version in versions),
            'analyzer_library_version', exit_code=5)
    require(py3langid.__version__ == '0.4.0', 'analyzer_library_version', exit_code=5)
    return ReferenceEngine(descriptor['adapter_version'],
        versions,
        MODEL_SHA256, CANDIDATES, CANDIDATES_SHA256, sys.implementation.name,
        platform.python_version(), unicodedata.unidata_version)


def _scores(model, text):
    try:
        valid = (tuple(model.labels) == CANDIDATES and model._norm_probs is True
                 and model.min_confidence is None)
    except (AttributeError, TypeError) as error:
        raise AnalyzerError('analyzer_reference_model_state', exit_code=5) from error
    require(valid, 'analyzer_reference_model_state', exit_code=5)
    try:
        rows = model.rank(text)
    except (AttributeError, TypeError, ValueError, ArithmeticError) as error:
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
