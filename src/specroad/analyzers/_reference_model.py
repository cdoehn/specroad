"""Only the shipped, hash-checked model decoder; no CLI or plugin entrypoint."""
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
