"""Byte-preserving requirement reads through existing safe project boundaries."""
from dataclasses import dataclass

from ..model.requirement import requirement_meaning, VALIDATION_SCOPE
from .domain_artifact import DomainArtifact, read_domain_artifact


@dataclass(frozen=True, init=False)
class RequirementArtifact:
    _record: DomainArtifact
    validation_scope: str

    def __init__(self, raw, *, path=None):
        record = DomainArtifact(raw, expected_type="requirement", path=path)
        object.__setattr__(self, "_record", record)
        object.__setattr__(self, "validation_scope", VALIDATION_SCOPE)

    @property
    def source_bytes(self):
        return self._record.source_bytes

    @property
    def data(self):
        return self._record.data

    @property
    def meaning(self):
        return requirement_meaning(self.data)


def read_requirement(source, path):
    """No defaults for stored records, no metadata restamping or implicit writes."""
    record = read_domain_artifact(source, path, expected_type="requirement")
    result = RequirementArtifact(record.source_bytes, path=path)
    source.check_current()
    return result
