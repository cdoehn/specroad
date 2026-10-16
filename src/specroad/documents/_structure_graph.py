"""Pure document composition from already validated native graph data.

The caller owns scope admission, native field/reference/cycle checks and report
binding. This kernel creates no independent persisted tree or file inventory.
"""
from hashlib import sha256

from ..graph.hierarchies import contains_position_key
from ..model.canonical import canonical_json_sha256


def _document_structure(records, references, values):
    index = {record.identity.id: record for record in records}
    diagnostics = []
    owners, children, documents = [], {}, []
    if not diagnostics:
        pointers = {relation.identity.id: '/relations/' + str(number)
                    for source in records for number, relation in enumerate(source.relations)}
        incoming = {identity: [] for identity, value in values.items()
                    if value['artifact_type'] == 'section'}
        for edge in references.relations:
            if edge.relation.type == 'contains' and edge.target.id in incoming:
                incoming[edge.target.id].append(edge)
        for identity in sorted(incoming):
            edges = incoming[identity]
            if len(edges) != 1:
                diagnostics.append({'reason': 'document_section_parent_cardinality',
                    'path': index[identity].path, 'pointer': '', 'artifact_id': identity,
                    'parent_count': len(edges), 'related_ids': [e.source.id for e in edges],
                    'relation_ids': [e.relation.identity.id for e in edges],
                    'incoming_relations': [{'source_id': e.source.id,
                        'path': index[e.source.id].path, 'pointer': pointers[e.relation.identity.id],
                        'source_sha256': sha256(index[e.source.id].source_bytes).hexdigest(),
                        'relation': e.relation.data,
                        'relation_sha256': canonical_json_sha256(e.relation.data)} for e in edges],
                    'severity': 'error'})
            else:
                edge = edges[0]
                owners.append({'section_id': identity, 'parent_id': edge.source.id,
                               'relation_id': edge.relation.identity.id})
    if not diagnostics:
        by_parent = {identity: [] for identity in sorted(values)
                     if values[identity]['artifact_type'] in ('document', 'section')}
        for edge in references.relations:
            if edge.relation.type == 'contains':
                by_parent[edge.source.id].append(edge)
        for identity, edges in by_parent.items():
            children[identity] = [{'artifact_id': edge.target.id,
                'artifact_type': edge.target.artifact_type,
                'relation_id': edge.relation.identity.id,
                'position': edge.relation.data['position'],
                'relation': edge.relation.data,
                'relation_sha256': canonical_json_sha256(edge.relation.data)}
                for edge in sorted(edges, key=contains_position_key)]
        for identity in sorted(values):
            value = values[identity]
            if value['artifact_type'] != 'document':
                continue
            pending = [(identity, edge, 0) for edge in reversed(children[identity])]
            preorder = []
            while pending:
                parent, edge, depth = pending.pop()
                preorder.append({k: edge[k] for k in
                    ('artifact_id', 'artifact_type', 'relation_id', 'position')}
                    | {'parent_id': parent, 'depth': depth})
                if edge['artifact_type'] == 'section':
                    pending.extend((edge['artifact_id'], child, depth + 1)
                                   for child in reversed(children[edge['artifact_id']]))
            documents.append({'document_id': identity, 'revision': value['revision'],
                'root_section_ids': [edge['artifact_id'] for edge in children[identity]],
                'preorder': preorder})
    return owners, children, documents, diagnostics
