"""Complete current-project relation queries, with or without adjacency.

An optional in-memory index is only a hint. Every query observes all current
artifact source bytes and membership; stale/partial hints never truncate data.
No persistent cache, atomic snapshot, full closure or write grant is implied.
"""
from dataclasses import dataclass

from ..graph.indices import RelationIndex
from ..graph.references import RelationReferences
from ..graph.relation_views import RelationViews
from ..graph.relations import SourceRelations
from ..model.errors import ModelError
from ._relation_snapshot import (
    RelationSourceBinding, _RelationSnapshot, _capture_sources, _check_snapshot_current,
)


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


def _provider(snapshot, index, strategy):
    """The same query interface, independent of whether adjacency is available."""
    if strategy == "scan":
        references = RelationReferences(snapshot.records)
        return RelationViews(references), references
    if type(index) is ProjectRelationIndex and index._snapshot == snapshot:
        selected = index
    else:
        selected = ProjectRelationIndex(snapshot)
    return selected.adjacency, selected.adjacency.references


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
    provider, references = _provider(snapshot, index, strategy)
    views = provider.for_artifact(artifact_id, direction=direction)
    artifact = next(record for record in snapshot.records if record.identity.id == artifact_id)
    result = ProjectRelationViews(artifact, views, snapshot.binding,
                                  len(references.sources), len(references.relations))
    _check_snapshot_current(source, snapshot)
    return result
