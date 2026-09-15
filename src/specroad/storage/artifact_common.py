"""Read-only common-field projections; no artifact is approved or created here."""

from dataclasses import dataclass

from ..model.artifact_schemas import VALIDATION_SCOPE, artifact_common_schema, validate_common_fields
from ..model.errors import ModelError
from ..model.paths import PathClass, artifact_path
from .json_reader import parse_json_object


@dataclass(frozen=True, init=False)
class CommonArtifact:
    source_bytes: bytes
    artifact_type: str
    id: str
    schema_version: str
    path: str | None
    validation_scope: str

    def __init__(self, raw, *, expected_type=None, path=None):
        value = parse_json_object(raw, path=path)
        try:
            validate_common_fields(value, expected_type=expected_type)
        except ModelError as error:
            error.path = path
            raise
        object.__setattr__(self, "source_bytes", raw)
        object.__setattr__(self, "artifact_type", value["artifact_type"])
        object.__setattr__(self, "id", value["id"])
        object.__setattr__(self, "schema_version", value["schema_version"])
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "validation_scope", VALIDATION_SCOPE)

    @property
    def common_fields(self):
        value = parse_json_object(self.source_bytes, path=self.path)
        names = artifact_common_schema(self.artifact_type)["properties"]
        return {name: item for name, item in value.items() if name in names}


def read_common_artifact(source, path, *, expected_type=None):
    """Bind identity and location, preserving bytes and the original project root.

This deliberately returns a COMMON projection, not a validated model artifact.
Later type/graph/profile checks must consume source_bytes before publication.
"""
    if source.classify(path) is not PathClass.ARTIFACT:
        raise ModelError("resource_path_class_mismatch", path=path)
    resource = CommonArtifact(source.read_normative(path), expected_type=expected_type, path=path)
    target = artifact_path(resource.artifact_type, resource.id, source.configuration.id_prefix)
    if target != path:
        raise ModelError("artifact_path_identity_mismatch", path=path)
    source.check_current()
    return resource
