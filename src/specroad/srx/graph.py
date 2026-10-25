"""Explicit immutable loaded model for SRX; never a file or callback resolver."""

from dataclasses import dataclass
from types import MappingProxyType
from ..graph.relations import SourceRelations
from ..graph.references import RelationReferences
from ..graph.indices import RelationIndex
from ..model.errors import ModelError
from ._json_values import JsonSnapshot, json_type
from .comparisons import compare
from .errors import SrxError
from ..runtime.control_points import PhaseBoundary, complete_steps


@dataclass(frozen=True, init=False)
class LoadedGraph:
    """Complete adjacency of all explicitly supplied records, not a project proof.

    Partial per-artifact relation views and caller-built indices are not inputs.
    Target resolution and both index directions are rebuilt by the graph Core.
    The caller is responsible for supplying the intended complete model scope.
    No filesystem access, cache fallback, model discovery, or mutable resolver.
    """
    _artifacts: object
    _index: RelationIndex
    _visible_ids: frozenset
    validation_scope: str

    def __init__(self, sources, *, rule_id, artifact_ids=None, partial=None):
        from .validation import _rule_id
        rule_id = _rule_id(rule_id)
        if type(sources) not in (list, tuple):
            raise SrxError("loaded_sources_required", rule_id=rule_id,
                           expected="list or tuple of SourceRelations", actual=json_type(sources),
                           subject="context", pointer="/graph")
        records = []
        for source in sources:
            if type(source) is not SourceRelations:
                raise SrxError("loaded_source_required", rule_id=rule_id,
                               expected="SourceRelations", actual="non_source",
                               subject="context", pointer="/graph")
            # Do not retain a caller's record containers or cached projections.
            try:
                records.append(SourceRelations(source.source_bytes))
            except ModelError as error:
                raise SrxError("graph_model_invalid", rule_id=rule_id,
                               expected="valid source records", actual=error.reason,
                               subject="context", pointer="/graph") from None
        try:
            if partial is None:
                references = RelationReferences(records)
                index = RelationIndex(references)
                boundary_ids = frozenset()
            else:
                from ..bundles._partial_graph import PartialGraph
                from ..bundles._partial_read import PartialReadSnapshot
                if (type(partial) is not PartialReadSnapshot or len(records) != len(partial.records) or
                        {r.identity.id: r.source_bytes for r in records} !=
                        {r.identity.id: r.source_bytes for r in partial.records}):
                    raise ModelError('partial_graph_sources_mismatch')
                index = PartialGraph(partial)
                boundary_ids = index.boundary_ids
        except ModelError as error:
            raise SrxError("graph_model_invalid", rule_id=rule_id,
                           expected="resolved canonical relations", actual=error.reason,
                           subject="context", pointer="/graph") from None
        object.__setattr__(self, "_index", index)
        object.__setattr__(self, '_boundary_ids', boundary_ids)
        object.__setattr__(self, "_artifacts", MappingProxyType({
            record.identity.id: JsonSnapshot(record.data, rule_id=rule_id, subject="context")
            for record in records}))
        known = set(self._artifacts)
        if artifact_ids is not None and (type(artifact_ids) not in (list, tuple)
                or any(type(name) is not str for name in artifact_ids)
                or len(set(artifact_ids)) != len(artifact_ids) or not set(artifact_ids) <= known):
            raise SrxError('graph_selection_invalid', rule_id=rule_id, subject='context',
                           pointer='/graph', expected='distinct loaded IDs', actual='invalid_selection')
        object.__setattr__(self, '_visible_ids', frozenset(known if artifact_ids is None else artifact_ids))
        object.__setattr__(self, "validation_scope", "loaded_model_only" if artifact_ids is None
                           else 'selected_loaded_model_only')
        if partial is not None:
            object.__setattr__(self, 'validation_scope', 'partial_bundle_artifacts')

    @property
    def artifact_ids(self):
        return tuple(sorted(self._visible_ids))

    def artifact(self, identifier, *, rule_id):
        if type(identifier) is not str or identifier not in self._visible_ids:
            raise SrxError("graph_artifact_missing", rule_id=rule_id,
                           expected="loaded artifact ID", actual="unknown_id",
                           subject="context", pointer="/artifact/id")
        return self._artifacts[identifier].data

    def checked_start(self, roots, *, rule_id, at):
        data = roots["artifact"]
        identifier = data.get("id")
        actual = self.artifact(identifier, rule_id=rule_id)
        if not compare("eq", data, actual, rule_id=rule_id, pointer=at):
            raise SrxError("graph_artifact_mismatch", rule_id=rule_id,
                           expected="same loaded artifact values", actual="different_values",
                           subject="context", pointer="/artifact")
        return identifier

    def neighbours(self, identifier, direction, types, *, meter=None, pointer="/expression"):
        return complete_steps(self.neighbours_steps(identifier, direction, types, meter=meter, pointer=pointer))

    def neighbours_steps(self, identifier, direction, types, *, meter=None, pointer="/expression", controls=None,
                         include_boundaries=False):
        # The legacy deterministic work charge remains unchanged. Operational
        # controls follow the actual per-edge processing below, not this batch.
        if controls is not None:
            yield PhaseBoundary('graph_views', 'start')
        views = self._index.for_artifact(identifier, direction=direction)
        if identifier not in self._visible_ids:
            raise ModelError('graph_artifact_outside_selection')
        if controls is not None:
            yield PhaseBoundary('graph_views', 'end')
        if meter is not None:
            meter.add("graph_steps", len(views), pointer=pointer)
        selected = []
        for view in views:
            if (view.target.id in self._visible_ids or
                    (include_boundaries and view.relation_id in self._boundary_ids)) and (types == "*" or view.type in types
                                                        or view.stored.relation.type in types):
                selected.append(view)
            if controls is not None:
                point = controls.advance('graph_steps')
                if point is not None:
                    yield point
        return tuple(selected)

    def candidate_roots(self, roots, identifier, *, rule_id, meter=None, pointer="/expression"):
        return complete_steps(self.candidate_roots_steps(roots, identifier, rule_id=rule_id,
                                                        meter=meter, pointer=pointer))

    def candidate_roots_steps(self, roots, identifier, *, rule_id, meter=None,
                              pointer="/expression", controls=None):
        result = dict(roots)
        result["artifact"] = self.artifact(identifier, rule_id=rule_id)
        if controls is not None:
            yield PhaseBoundary('graph_views', 'start')
        views = self._index.for_artifact(identifier, direction="both")
        if controls is not None:
            yield PhaseBoundary('graph_views', 'end')
        if meter is not None:
            meter.add("graph_steps", len(views), pointer=pointer)
        result["relations"] = []
        for view in views:
            if view.target.id in self._visible_ids or view.relation_id in self._boundary_ids:
                result["relations"].append(
                    {"relation_id": view.relation_id, "type": view.type,
                     "source": view.source.id, "target": view.target.id,
                     "target_type": view.target.artifact_type, "inverse": view.inverse})
            if controls is not None:
                point = controls.advance('graph_steps')
                if point is not None:
                    yield point
        return result


def require_graph(graph, *, rule_id, at):
    if type(graph) is not LoadedGraph:
        raise SrxError("loaded_graph_required", rule_id=rule_id, pointer=at,
                       expected="explicit LoadedGraph", actual="missing_graph", subject="context")
    return graph
