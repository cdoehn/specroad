"""One lazy, process-local model owner for an explicit worker invocation.

Importing this module does not import an optional dependency. A failed load is
also remembered; one request cannot repeatedly initialize the same model.
"""
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
import stat

from ._values import AnalyzerError, require

MODEL_SHA256 = 'f4f4a2c3465ca1f081541037f9cac23021d68151c2f709c55ae5eedfca522963'


def _model_bytes(path):
    """A supplied model must be a regular file, never a pipe or linked blob."""
    require(stat.S_ISREG(path.lstat().st_mode), 'analyzer_model_file', exit_code=5)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
                         | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode),
                'analyzer_model_file', exit_code=5)
        return stream.read()


def load_reference_model():
    """Load only the supplied model bytes, without invoking the upstream CLI."""
    try:
        import py3langid
        from py3langid.langid import LanguageIdentifier
        from py3langid.modelio import load_model
        require(py3langid.__version__ == '0.4.0', 'analyzer_library_version', exit_code=5)
        path = Path(py3langid.__file__).resolve(strict=True).parent / 'data/model.npz.xz'
        raw = _model_bytes(path)
        require(sha256(raw).hexdigest() == MODEL_SHA256, 'analyzer_model_hash', exit_code=5)
        # Decode the bytes that were checked, not a second read of the filename.
        ptc, pc, classes, nextmove, row, output = load_model(BytesIO(raw))
        return LanguageIdentifier(ptc, pc, classes, nextmove, output,
                                  tk_row=row, norm_probs=True)
    except (ImportError, OSError, ValueError) as error:
        raise AnalyzerError('analyzer_model_unavailable', exit_code=5) from error


class ModelSession:
    """A single lazy model, released before another invocation can own one."""

    def __init__(self):
        self._model = None
        self._attempted = False
        self._error = None
        self._closed = False

    def model(self):
        require(not self._closed, 'analyzer_model_session_closed', exit_code=5)
        if not self._attempted:
            self._attempted = True
            try:
                self._model = load_reference_model()
            except AnalyzerError as error:
                self._error = error
        if self._error is not None:
            raise self._error
        return self._model

    def close(self):
        self._model = None
        self._error = None
        self._closed = True

    def __enter__(self):
        require(not self._closed, 'analyzer_model_session_closed', exit_code=5)
        return self

    def __exit__(self, *_):
        self.close()
