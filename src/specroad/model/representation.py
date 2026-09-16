"""Read-only representation candidates, not a Change Plan or write permission."""

from dataclasses import dataclass
from hashlib import sha256
import json

from .canonical import canonical_json_sha256
from .errors import ModelError
from .paths import project_path
from ..storage.json_syntax import parse_json_object


def normal_json_bytes(raw: bytes) -> bytes:
    """Render one strict JSON object without changing any JSON value.

    Human normal form: Unicode codepoint key order at every object level,
    two-space indentation and final LF. This is deliberately NOT JCS. String
    contents (including CR/LF, whitespace and NFC/NFD) are never normalized.
    """
    if type(raw) is not bytes:
        raise ModelError("bytes_required")
    value = parse_json_object(raw)
    before = canonical_json_sha256(value)
    try:
        rendered = (json.dumps(value, ensure_ascii=False, allow_nan=False,
                               sort_keys=True, indent=2) + "\n").encode("utf-8")
    except (UnicodeError, ValueError, TypeError, RecursionError) as error:
        raise ModelError("unsupported_json_representation") from error
    if canonical_json_sha256(parse_json_object(rendered)) != before:
        raise ModelError("representation_value_changed")
    return rendered


@dataclass(frozen=True, init=False)
class NormalizationCandidate:
    """Byte-bound, value-preserving proposal. Constructing it performs no I/O.

    This full-value hash is not a project/model-root projection. A later
    transaction must revalidate eligibility, source bytes and the project.
    """

    path: str
    source_bytes: bytes
    normalized_bytes: bytes
    expected_byte_sha256: str
    result_byte_sha256: str
    value_sha256: str

    def __init__(self, path: str, source_bytes: bytes):
        path = project_path(path)
        try:
            normalized = normal_json_bytes(source_bytes)
        except ModelError as error:
            error.path = path
            raise
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "source_bytes", source_bytes)
        object.__setattr__(self, "normalized_bytes", normalized)
        object.__setattr__(self, "expected_byte_sha256", sha256(source_bytes).hexdigest())
        object.__setattr__(self, "result_byte_sha256", sha256(normalized).hexdigest())
        object.__setattr__(self, "value_sha256", canonical_json_sha256(parse_json_object(source_bytes)))

    @property
    def change_required(self) -> bool:
        return self.source_bytes != self.normalized_bytes

    @property
    def source_data(self) -> dict:
        return parse_json_object(self.source_bytes, path=self.path)

    @property
    def normalized_data(self) -> dict:
        return parse_json_object(self.normalized_bytes, path=self.path)
