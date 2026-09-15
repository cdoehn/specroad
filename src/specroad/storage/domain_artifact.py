"""Owned, byte-preserving domain records. No authoring or approval side effects."""

from dataclasses import dataclass

from ..model.domain_schemas import VALIDATION_SCOPE, validate_domain_fields
from ..model.errors import ModelError
from .artifact_common import read_common_artifact
from .json_reader import parse_json_object


@dataclass(frozen=True, init=False)
class DomainArtifact:
    source_bytes: bytes
    artifact_type: str
    id: str
    path: str | None
    validation_scope: str

    def __init__(self, raw, *, expected_type=None, path=None):
        if type(raw) is not bytes:
            raise ModelError("bytes_required", path=path)
        value = parse_json_object(raw, path=path)
        try:
            validate_domain_fields(value, expected_type=expected_type)
        except ModelError as error:
            error.path = path
            raise
        object.__setattr__(self, "source_bytes", raw)
        object.__setattr__(self, "artifact_type", value["artifact_type"])
        object.__setattr__(self, "id", value["id"])
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "validation_scope", VALIDATION_SCOPE)

    @property
    def data(self):
        """A fresh detached value, not a mutation handle to the original record."""
        return parse_json_object(self.source_bytes, path=self.path)


def read_domain_artifact(source, path, *, expected_type=None):
    """Read one bound artifact, retaining the existing root/type/path protection."""
    common = read_common_artifact(source, path, expected_type=expected_type)
    resource = DomainArtifact(common.source_bytes, expected_type=expected_type, path=path)
    source.check_current()
    return resource
