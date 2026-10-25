"""Member-only validation inputs with narrowly typed context references."""
from ..graph.relations import SourceRelations
from ._model_checks import _field_targets, _field_target_error


def partial_foreign_edges(records, partial):
    from ..bundles._partial_graph import PartialGraph
    from ..bundles.boundary_context import read_boundary_context
    graph = PartialGraph(partial)
    relations = {e.relation.identity.id: e for e in partial.references.local_relations}
    for views in graph.outside.values():
        relations.update((v.relation_id, v.stored) for v in views)
    members = {r.identity.id: r for r in records}
    configuration = {r.identity.id: r for d in partial.payload_model.documents
        if (r := SourceRelations(d.content, path=d.path)).identity.artifact_type == 'configuration'}
    proof = read_boundary_context(partial.container, partial.payload_model)
    edges = []
    for record in records:
        context = (configuration if record.identity.artifact_type == 'configuration' else
                   proof if record.identity.artifact_type == 'relation_review' else {})
        for target, pointer, kind in _field_targets(record, relations):
            error = _field_target_error(target, kind, {**members, **context}, record.path, pointer)
            if error is not None:
                raise error
            if target in members:
                edges.append((record.identity.id, target))
    return edges
