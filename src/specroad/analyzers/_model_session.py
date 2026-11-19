"""One lazy, process-local model owner for an explicit worker invocation.

Importing this module does not import an optional dependency. A failed load is
also remembered; one request cannot repeatedly initialize the same model.
"""
from ._values import AnalyzerError, require
from . import _reference_model

MODEL_SHA256 = _reference_model.MODEL_SHA256
load_reference_model = _reference_model.load_reference_model


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
