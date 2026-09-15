"""Lossless metadata projection and pure serialization, never a write authority.

Serialization here is JSON value round-tripping, not the later canonical/JCS
writer, a revision update, an approval check or filesystem publication.
"""

import json
from dataclasses import dataclass

from ..model.artifact_schemas import validate_common_fields
from ..model.errors import ModelError
from ..model.metadata import METADATA_FIELDS
from .artifact_common import CommonArtifact
from .json_syntax import parse_json_object


def serialize_common_artifact(value):
    """Produce UTF-8 bytes without dropping metadata or writing any files."""
    validate_common_fields(value)
    try:
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False,
                         separators=(",", ":")).encode("utf-8")
        # Pass through the same strict syntax/number contract as file readers.
        parse_json_object(raw)
        return raw
    except RecursionError as error:
        raise ModelError("unsupported_json_nesting") from error


@dataclass(frozen=True, init=False)
class ArtifactMetadata:
    """An immutable byte-owned projection. Every data access is detached."""
    _encoded: bytes

    def __init__(self, artifact):
        validate_common_fields(artifact)
        value = {name: artifact[name] for name in METADATA_FIELDS if name in artifact}
        object.__setattr__(self, "_encoded", json.dumps(value, ensure_ascii=False,
                           allow_nan=False, separators=(",", ":")).encode("utf-8"))

    @classmethod
    def from_bytes(cls, raw):
        resource = CommonArtifact(raw)
        return cls(parse_json_object(resource.source_bytes))

    @property
    def data(self):
        return parse_json_object(self._encoded)
