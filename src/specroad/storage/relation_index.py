"""Full current-artifact relation reads with byte and membership rechecks.

The selection limits returned views, never the source files inspected. No
persistent cache is read/written. A completed observation is not an atomic
snapshot, a scope closure, a lifecycle approval or a reusable write permission.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..graph.indices import RelationIndex
from ..graph.references import RelationReferences
from ..graph.relation_views import RelationViews
from ..graph.relations import SourceRelations
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


@dataclass(frozen=True, init=False)
class ProjectRelationIndex:
    """An immutable prior observation. Query through read_project_relation_views
    to revalidate current bytes/membership rather than trust an old observation.
    """
    _snapshot: _RelationSnapshot
    adjacency: RelationIndex

    def __init__(self, snapshot):
        if type(snapshot) is not _RelationSnapshot:
            raise ModelError("project_relation_snapshot_required")
        adjacency = RelationIndex(RelationReferences(snapshot.records))
        object.__setattr__(self, "_snapshot", snapshot)
        object.__setattr__(self, "adjacency", adjacency)

    @property
    def binding(self):
        return self._snapshot.binding

    @property
    def source_count(self):
        return len(self._snapshot.records)

    @property
    def relation_count(self):
        return len(self.adjacency.references.relations)


@dataclass(frozen=True)
class ProjectRelationViews:
    artifact: SourceRelations
    views: tuple
    binding: RelationSourceBinding
    source_count: int
    relation_count: int

    @property
    def coverage_scope(self):
        return "current_project_artifacts"

    @property
    def validation_scope(self):
        return "relation_references_and_canonical_storage_only"

    @property
    def atomic_snapshot(self):
        return False


def build_project_relation_index(source):
    """Inspect the complete current artifact source set, or raise without writes."""
    snapshot = _capture_sources(source)
    result = ProjectRelationIndex(snapshot)
    _check_snapshot_current(source, snapshot)
    return result


def read_project_relation_views(source, artifact_id, *, direction="both", index=None, strategy="indexed"):
    """Read fresh source membership/bytes even when reusing a prior index.

    An index is only an optimization hint, never a completeness assertion.
    A stale, foreign or supplied-set-only hint is rebuilt from current sources.
    An unreadable/invalid source raises rather than falling back to old data.
    ``scan`` is the index-independent reference path over the same fresh inputs.
    No persistent cache format, cache side effect or mtime shortcut is introduced.
    """
    if type(strategy) is not str or strategy not in ("indexed", "scan"):
        raise ModelError("invalid_relation_index_strategy")
    if index is not None and type(index) not in (ProjectRelationIndex, RelationIndex):
        raise ModelError("invalid_relation_index_hint")
    snapshot = _capture_sources(source)
    if strategy == "scan":
        references = RelationReferences(snapshot.records)
        views = RelationViews(references).for_artifact(artifact_id, direction=direction)
        source_count, relation_count = len(references.sources), len(references.relations)
    else:
        if type(index) is ProjectRelationIndex and index._snapshot == snapshot:
            selected = index
        else:
            selected = ProjectRelationIndex(snapshot)
        views = selected.adjacency.for_artifact(artifact_id, direction=direction)
        source_count, relation_count = selected.source_count, selected.relation_count
    artifact = next(record for record in snapshot.records if record.identity.id == artifact_id)
    result = ProjectRelationViews(artifact, views, snapshot.binding, source_count, relation_count)
    _check_snapshot_current(source, snapshot)
    return result
