"""Current source observations and their local byte/membership bindings.

Private storage helpers. Every read fails on observed changes rather than
publishing a partial index. The second scan is not a transaction lock.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..model.errors import ModelError
from ..model.hashes import canonical_json_sha256
from ..model.paths import PathClass
from .project import ProjectSource
from .relations import read_source_relations
from .resource_discovery import current_json_paths


@dataclass(frozen=True)
class RelationSourceBinding:
    project_id: str
    source_root: str
    root_identity: tuple
    configuration_sha256: str
    resources: tuple

    @property
    def sha256(self):
        """Local byte observation binding, deliberately NOT a model root."""
        return canonical_json_sha256({
            "binding_version": 1, "scope": "current_project_artifacts",
            "project_id": self.project_id, "source_root": self.source_root,
            "root_identity": [str(part) for part in self.root_identity],
            "configuration_sha256": self.configuration_sha256,
            "resources": [{"path": path, "sha256": digest} for path, digest in self.resources],
        })


@dataclass(frozen=True)
class _RelationSnapshot:
    binding: RelationSourceBinding
    records: tuple


def _artifact_paths(source):
    # The existing safe enumerator covers configured normative trees. Only
    # artifact records can store these graph edges; profiles/rules are separate.
    return tuple(path for path in current_json_paths(source)
                 if source.classify(path) is PathClass.ARTIFACT)


def _require_source(source):
    if not isinstance(source, ProjectSource):
        raise TypeError("A bound ProjectSource is required")
    source.check_current()


def _check_snapshot_current(source, snapshot):
    _require_source(source)
    if (str(source.boundary.root) != snapshot.binding.source_root
            or source.boundary._root_identity != snapshot.binding.root_identity
            or source.configuration.project_id != snapshot.binding.project_id
            or sha256(source.configuration_bytes).hexdigest() != snapshot.binding.configuration_sha256):
        raise ModelError("relation_index_project_mismatch")
    paths = tuple(record.path for record in snapshot.records)
    if _artifact_paths(source) != paths:
        raise ModelError("relation_index_membership_changed")
    for record in snapshot.records:
        if source.read_normative(record.path) != record.source_bytes:
            raise ModelError("relation_index_source_changed", path=record.path)
    if _artifact_paths(source) != paths:
        raise ModelError("relation_index_membership_changed")
    source.check_current()


def _capture_sources(source):
    _require_source(source)
    names = _artifact_paths(source)
    records = tuple(read_source_relations(source, path) for path in names)
    binding = RelationSourceBinding(
        source.configuration.project_id, str(source.boundary.root),
        source.boundary._root_identity, sha256(source.configuration_bytes).hexdigest(),
        tuple((record.path, sha256(record.source_bytes).hexdigest()) for record in records))
    result = _RelationSnapshot(binding, records)
    _check_snapshot_current(source, result)
    return result


