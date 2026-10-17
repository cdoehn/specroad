"""Native contains/include admission shared by composition and cycle evidence."""
from hashlib import sha256

from ..graph._graph_traversal import _cycle_witness
from ..graph.hierarchies import contains_position_key
from ..graph.references import RelationReferences
from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_sha256
from .blocks import ContentBlock


def _edge_data(edge, index, pointers):
    source = index[edge.source.id]
    include = edge.relation.type == 'references'
    return {'kind': 'include' if include else 'contains',
        'source_id': edge.source.id, 'target_id': edge.target.id,
        'relation_id': edge.relation.identity.id, 'path': source.path,
        'pointer': pointers[edge.relation.identity.id],
        'source_sha256': sha256(source.source_bytes).hexdigest(),
        'relation_sha256': canonical_json_sha256(edge.relation.data),
        'relation': edge.relation.data,
        'include_mode': source.data['payload']['mode'] if include else None}


def _include_graph(documents, cycle_error_type):
    records = tuple(SourceRelations(d.content, path=d.path) for d in documents)
    index = {record.identity.id: record for record in records}
    references = RelationReferences(records)
    include_ids = set()
    for record in records:
        value = record.data
        if value['artifact_type'] == 'content_block' and value['block_kind'] == 'include_document':
            block = ContentBlock(record.source_bytes, path=record.path)
            include_ids.add(block.data['id'])
    pointers = {relation.identity.id: '/relations/' + str(i)
                for record in records for i, relation in enumerate(record.relations)}
    edges = tuple(edge for edge in references.relations if edge.relation.type == 'contains'
                  or (edge.source.id in include_ids and edge.relation.type == 'references'))
    cycle = _cycle_witness(edges)
    if cycle is not None:
        raise cycle_error_type(cycle, index, pointers)
    outgoing = {}
    for edge in edges: outgoing.setdefault(edge.source.id, []).append(edge)
    for identifier, children in outgoing.items():
        if identifier not in include_ids: children.sort(key=contains_position_key)
    return index, pointers, edges, outgoing
