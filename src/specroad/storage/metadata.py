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


def resolve_artifact_reference(reference, artifacts, *, id_prefix):
    """Resolve a canonical id in a supplied project inventory, never a label.

    This pure helper does not scan a project, infer history or grant write access.
    It validates the entire supplied inventory before returning detached data.
    Duplicate labels are harmless; duplicate actual identities are an error.
    """
    from ..model.paths import artifact_path
    if type(reference) is not str or not reference:
        raise ModelError("artifact_reference_required")
    if isinstance(artifacts, (str, bytes, dict)):
        raise ModelError("artifact_inventory_required")
    try:
        artifacts = tuple(artifacts)
    except TypeError as error:
        raise ModelError("artifact_inventory_required") from error
    seen = {}
    labels = set()
    for artifact in artifacts:
        raw = serialize_common_artifact(artifact)
        # This binds both actual type and configured project prefix.
        artifact_path(artifact["artifact_type"], artifact["id"], id_prefix)
        identity = artifact["id"]
        if identity in seen:
            raise ModelError("duplicate_artifact_id")
        seen[identity] = raw
        if "display_id" in artifact:
            labels.add(artifact["display_id"])
    if reference in seen:
        return parse_json_object(seen[reference])
    if reference in labels:
        raise ModelError("display_id_is_not_identity")
    raise ModelError("artifact_not_found")
