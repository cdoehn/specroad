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
    validation_scope: str

    def __init__(self, sources, *, rule_id):
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
            references = RelationReferences(records)
            index = RelationIndex(references)
        except ModelError as error:
            raise SrxError("graph_model_invalid", rule_id=rule_id,
                           expected="resolved canonical relations", actual=error.reason,
                           subject="context", pointer="/graph") from None
        object.__setattr__(self, "_index", index)
        object.__setattr__(self, "_artifacts", MappingProxyType({
            record.identity.id: JsonSnapshot(record.data, rule_id=rule_id, subject="context")
            for record in records}))
        object.__setattr__(self, "validation_scope", "loaded_model_only")

    @property
    def artifact_ids(self):
        return tuple(sorted(self._artifacts))

    def artifact(self, identifier, *, rule_id):
        if type(identifier) is not str or identifier not in self._artifacts:
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

    def neighbours(self, identifier, direction, types, *, meter=None):
        # Stored type selectors also match their computed incoming views.
        views = self._index.for_artifact(identifier, direction=direction)
        if meter is not None:
            meter.add("graph_steps", len(views))
        return tuple(view for view in views if types == "*" or
                     view.type in types or view.stored.relation.type in types)

    def candidate_roots(self, roots, identifier, *, rule_id, meter=None):
        result = dict(roots)
        result["artifact"] = self.artifact(identifier, rule_id=rule_id)
        views = self._index.for_artifact(identifier, direction="both")
        if meter is not None:
            meter.add("graph_steps", len(views))
        result["relations"] = [
            {"relation_id": view.relation_id, "type": view.type,
             "source": view.source.id, "target": view.target.id,
             "target_type": view.target.artifact_type, "inverse": view.inverse}
            for view in views]
        return result


def require_graph(graph, *, rule_id, at):
    if type(graph) is not LoadedGraph:
        raise SrxError("loaded_graph_required", rule_id=rule_id, pointer=at,
                       expected="explicit LoadedGraph", actual="missing_graph", subject="context")
    return graph
