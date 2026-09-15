"""Owned passive records. Reading neither renders content nor executes a check."""

from dataclasses import dataclass

from ..model.record_schemas import validate_record_fields
from ..model.record_contracts import record_contract
from ..model.errors import ModelError
from .artifact_common import read_common_artifact
from .json_reader import parse_json_object


@dataclass(frozen=True, init=False)
class RecordArtifact:
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
            validate_record_fields(value, expected_type=expected_type)
        except ModelError as error:
            error.path = path
            raise
        object.__setattr__(self, "source_bytes", raw)
        object.__setattr__(self, "artifact_type", value["artifact_type"])
        object.__setattr__(self, "id", value["id"])
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "validation_scope", record_contract(value["artifact_type"]).validation_scope)

    @property
    def data(self):
        """Return fresh values without exposing a mutation handle to this record."""
        return parse_json_object(self.source_bytes, path=self.path)


def read_record_artifact(source, path, *, expected_type=None):
    """Read through the same fresh project-root/path/ID boundary as other types."""
    common = read_common_artifact(source, path, expected_type=expected_type)
    record = RecordArtifact(common.source_bytes, expected_type=expected_type, path=path)
    source.check_current()
    return record
