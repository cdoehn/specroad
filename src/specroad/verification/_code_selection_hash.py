"""H.2 decoding and selection hashing, independent of window traversal."""
from hashlib import sha256

from ..model.errors import ModelError


def normalized_text(source_bytes, encoding):
    """Decode strictly and normalize only CRLF/CR, without selecting lines."""
    try:
        text = source_bytes.decode(encoding, errors='strict')
    except UnicodeError as error:
        raise ModelError('code_reference_decode_failed', pointer='/encoding') from error
    except (LookupError, ValueError) as error:
        raise ModelError('code_reference_encoding_unavailable', pointer='/encoding') from error
    return text.replace('\r\n', '\n').replace('\r', '\n')


def selection_utf8(text):
    """Encode exactly the caller's selected text, retaining the error contract."""
    try:
        return text.encode('utf-8')
    except UnicodeError as error:
        raise ModelError('code_reference_decode_failed', pointer='/encoding') from error


def selection_digest(content):
    """Hash the supplied bytes/view without choosing or normalizing a window."""
    return sha256(content).hexdigest()
