"""Owned container input values; no implicit resolver or source acquisition."""
from dataclasses import dataclass
from types import MappingProxyType
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from ..graph.relation_values import SourceRelations
from ..graph.references import RelationReferences
from ..storage.domain_artifact import DomainArtifact
from ..storage.record_artifact import RecordArtifact

class ContainerLanguageError(ModelError):
    """Invalid or incomplete model selection, not a linguistic finding."""


@dataclass(frozen=True, init=False)
class ContainerModel:
    """An explicitly supplied, source-bound model. No project completeness claim."""
    _records: object
    sha256: str

    def __init__(self, sources):
        if type(sources) not in (list, tuple):
            raise ContainerLanguageError("container_sources_required")
        records = []
        for raw in sources:
            if type(raw) is not bytes:
                raise ContainerLanguageError("container_source_bytes_required")
            record = SourceRelations(raw)
            kind = record.identity.artifact_type
            if kind == "requirement":
                DomainArtifact(raw, expected_type=kind)
            elif kind in {"document", "section", "content_block", "view", "configuration"}:
                RecordArtifact(raw, expected_type=kind)
            records.append(record)
        RelationReferences(records)
        ordered = sorted(records, key=lambda r: r.identity.id)
        object.__setattr__(self, "_records", MappingProxyType({r.identity.id: r for r in ordered}))
        object.__setattr__(self, "sha256", canonical_json_sha256([r.data for r in ordered]))

    def values(self):
        """Return caller-owned values, never mutation handles into this model."""
        return {key: value.data for key, value in self._records.items()}



def _digest(value, reason):
    if type(value) is not str or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ContainerLanguageError(reason)
    return value


def _ids(values, *, duplicates=False):
    if type(values) not in (list, tuple) or any(type(x) is not str or not x for x in values):
        raise ContainerLanguageError("resolved_identity_list_required")
    if not duplicates and len(set(values)) != len(values):
        raise ContainerLanguageError("duplicate_resolved_identity")
    return tuple(values)


@dataclass(frozen=True)
class ResolvedRequirementScope:
    """Supplied applicability result, not evaluated or authenticated here.

    IDs may include historical requirements; project filtering is independent.
    The configuration hash binds the exact supplied configuration artifact.
    """
    model_sha256: str
    configuration_id: str
    configuration_sha256: str
    requirement_ids: tuple
    complete: bool = True

    def __post_init__(self):
        _digest(self.model_sha256, "invalid_scope_model_hash")
        _digest(self.configuration_sha256, "invalid_scope_configuration_hash")
        if type(self.configuration_id) is not str or not self.configuration_id:
            raise ContainerLanguageError("scope_configuration_id_required")
        if self.complete is not True:
            raise ContainerLanguageError("incomplete_requirement_scope")
        object.__setattr__(self, "requirement_ids", _ids(self.requirement_ids))


@dataclass(frozen=True)
class QueryRows:
    """A complete resolved display selection bound to one block occurrence.

    Rows preserve order and duplication. This does not execute SRX, authenticate
    an external resolver, or infer artifact IDs from text or rendered cells.
    """
    model_sha256: str
    block_id: str
    occurrence_path: tuple
    artifact_ids: tuple
    configuration_sha256: str | None = None
    complete: bool = True

    def __post_init__(self):
        _digest(self.model_sha256, "invalid_query_model_hash")
        if type(self.block_id) is not str or not self.block_id:
            raise ContainerLanguageError("query_block_id_required")
        object.__setattr__(self, "occurrence_path", _ids(self.occurrence_path))
        object.__setattr__(self, "artifact_ids", _ids(self.artifact_ids, duplicates=True))
        if self.configuration_sha256 is not None:
            _digest(self.configuration_sha256, "invalid_query_configuration_hash")
        if self.complete is not True:
            raise ContainerLanguageError("incomplete_query_rows")


def _model(model):
    if type(model) is not ContainerModel:
        raise ContainerLanguageError("container_model_required")
    return model.values()


