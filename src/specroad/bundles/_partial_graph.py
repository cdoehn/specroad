"""Two views of verified partial bytes: observed edges and local traversal.

An outside endpoint remains an identity, never a loaded artifact. The local
index is a derived graph projection; original member bytes remain untouched.
"""
from ..graph._boundary_contract import require_boundary_match
from ..graph.indices import RelationIndex, _view_key
from ..graph.references import RelationReferences
from ..graph.relation_views import RelationView
from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_bytes


class PartialGraph:
    def __init__(self, snapshot):
        from ._partial_read import PartialReadSnapshot
        if type(snapshot) is not PartialReadSnapshot:
            raise TypeError('A verified partial observation is required')
        members = {r.identity.id for r in snapshot.records}
        local = []
        for record in snapshot.records:
            value = record.data
            value['relations'] = [r for r in value['relations'] if r['target'] in members]
            local.append(SourceRelations(canonical_json_bytes(value), path=record.path))
        self.local = RelationIndex(RelationReferences(tuple(local)))
        self.references = self.local.references
        relations = {r.identity.id: r for record in snapshot.records for r in record.relations}
        outside = {}
        for boundary in snapshot.references.boundary_references:
            value = boundary.data
            view = RelationView(require_boundary_match(value, relations[value['relation_id']]))
            outside.setdefault(view.source.id, []).append(view)
        self.outside = {key: tuple(sorted(values, key=_view_key)) for key, values in outside.items()}
        self.boundary_ids = frozenset(v.relation_id for values in self.outside.values() for v in values)

    def for_artifact(self, artifact_id, *, direction='both'):
        views = self.local.for_artifact(artifact_id, direction=direction)
        if direction != 'incoming':
            views = tuple(sorted((*views, *self.outside.get(artifact_id, ())), key=_view_key))
        return views
