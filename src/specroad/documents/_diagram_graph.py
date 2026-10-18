"""Native graph admission, traversal and bound data for diagram projections.

This module knows the selected model scope, never Mermaid/DOT source syntax.
Its result is owned by the public DiagramData factory after canonical encoding.
"""
from collections import deque
from hashlib import sha256

from .._metadata import __version__, MODEL_SCHEMA_VERSION
from ..graph.relations import SourceRelations
from ..graph.relation_types import CORE_RELATION_TYPES
from ..graph.scope_descriptors import ScopeDescriptor
from ..graph.scope_inputs import ScopeSeedInputs
from ..graph.scope_seeds import resolve_scope_seeds
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from ..srx import LoadedGraph


def diagram_graph_data(model, diagram_kind, *, start_id, direction, max_depth,
                       max_nodes, max_edges, artifact_ids, relation_types, error_type):
    """Resolve the existing graph contract with the caller's public error class."""
    from ..changes.target_model import TargetModel, _default_scope
    if type(model) is not TargetModel:
        raise ModelError('document_target_model_required')
    if type(diagram_kind) is not str or diagram_kind not in ('trace', 'architecture', 'release'):
        raise error_type('diagram_kind_not_supported', pointer='/diagram_kind', exit_code=2)
    if type(start_id) is not str:
        raise error_type('diagram_start_id_required', pointer='/start_id', exit_code=2)
    if type(direction) is not str or direction not in ('incoming', 'outgoing', 'both'):
        raise error_type('diagram_direction_required', pointer='/direction', exit_code=2)
    for name, value, minimum in (('max_depth', max_depth, 0), ('max_nodes', max_nodes, 1),
                                  ('max_edges', max_edges, 0)):
        if type(value) is not int or value < minimum:
            raise error_type('diagram_limit_required', pointer='/' + name, exit_code=2)
    for name, values, reason in (
            ('artifact_ids', artifact_ids, 'diagram_artifact_selection_invalid'),
            ('relation_types', relation_types, 'diagram_relation_types_invalid')):
        if values is not None and (type(values) not in (list, tuple)
                or any(type(value) is not str for value in values)
                or len(set(values)) != len(values)):
            raise error_type(reason, pointer='/' + name, exit_code=2)
    artifact_ids = None if artifact_ids is None else tuple(sorted(artifact_ids))
    if relation_types is not None:
        if not set(relation_types) <= set(CORE_RELATION_TYPES):
            raise error_type('diagram_relation_types_invalid', pointer='/relation_types', exit_code=2)
        relation_types = tuple(sorted(relation_types))
    model = model.snapshot()
    records = tuple(SourceRelations(d.content, path=d.path) for d in model.documents)
    by_id = {r.identity.id: r for r in records}
    if start_id not in by_id:
        raise error_type('diagram_start_not_found', pointer='/start_id')
    if diagram_kind == 'architecture':
        eligible = {r.identity.id for r in records
                    if r.identity.artifact_type in ('component', 'interface')}
        scope = {'kind': 'architecture_relations'}
    elif diagram_kind == 'release':
        if by_id[start_id].identity.artifact_type != 'release':
            raise error_type('diagram_release_start_required', pointer='/start_id')
        descriptor = ScopeDescriptor({**_default_scope(), 'scope_kind': 'release',
                                      'selector': {'release_id': start_id}})
        seeds = resolve_scope_seeds(descriptor, ScopeSeedInputs(model.configuration, records))
        eligible = set(seeds.artifact_ids)
        scope = {'kind': 'release_seed_relations', 'descriptor': descriptor.data,
                 'seed_inputs_sha256': seeds.inputs_sha256}
    else:
        eligible = set(by_id)
        scope = {'kind': 'supplied_project_relations'}
    if artifact_ids is not None:
        if not set(artifact_ids) <= set(by_id):
            raise error_type('diagram_artifact_not_found', pointer='/artifact_ids')
        if not set(artifact_ids) <= eligible:
            raise error_type('diagram_artifact_outside_scope', pointer='/artifact_ids')
        eligible = set(artifact_ids)
    if start_id not in eligible:
        raise error_type('diagram_start_outside_scope', pointer='/start_id')
    graph = LoadedGraph(records, rule_id='document-diagram', artifact_ids=sorted(eligible))
    distances, edges = {start_id: 0}, {}
    pending = deque([start_id])
    while pending:
        current = pending.popleft()
        distance = distances[current]
        if distance == max_depth:
            continue
        for view in graph.neighbours(current, direction,
                                     '*' if relation_types is None else relation_types):
            target = view.target.id
            if target not in distances:
                if len(distances) == max_nodes:
                    raise error_type('diagram_node_limit_exceeded', pointer='/max_nodes')
                distances[target] = distance + 1
                pending.append(target)
            if view.relation_id not in edges:
                if len(edges) == max_edges:
                    raise error_type('diagram_edge_limit_exceeded', pointer='/max_edges')
                stored = view.stored
                edges[view.relation_id] = {
                    'relation_id': view.relation_id,
                    'diagram_id': 'e_' + view.relation_id.encode('utf-8').hex(),
                    'source': stored.source.id, 'target': stored.target.id,
                    'type': stored.relation.type, 'stored_relation': stored.relation.data,
                    'relation_sha256': canonical_json_sha256(stored.relation.data)}
    nodes = []
    for identifier in sorted(distances):
        record = by_id[identifier]
        value = record.data
        nodes.append({'artifact_id': identifier, 'artifact_type': record.identity.artifact_type,
            'diagram_id': 'n_' + identifier.encode('utf-8').hex(), 'title': value['title'],
            'revision': value['revision'], 'distance': distances[identifier],
            'source_sha256': sha256(record.source_bytes).hexdigest(),
            'record_sha256': canonical_json_sha256(value)})
    data = {'format_version': 1, 'kind': 'diagram-data-v1', 'diagram_kind': diagram_kind,
        'generated': True, 'normative': False, 'tool_version': __version__,
        'schema_version': MODEL_SCHEMA_VERSION, 'profiles': list(model.profile.profile_chain),
        'project_id': model.binding.project_id,
        'model_root_sha256': model.manifest(model.artifacts, _default_scope()).sha256,
        'input_sha256': model._sources_sha256,
        'selection': {'start_id': start_id, 'direction': direction, 'max_depth': max_depth,
            'max_nodes': max_nodes, 'max_edges': max_edges, 'scope': scope,
            'eligible_ids_sha256': canonical_json_sha256(sorted(eligible))},
        'nodes': nodes, 'edges': [edges[key] for key in sorted(edges)],
        'node_count': len(nodes), 'edge_count': len(edges),
        'validation_scope': 'supplied_snapshot_relation_projection',
        'project_files_verified': False, 'full_validation_passed': False,
        'rendering_performed': False, 'write_authorized': False, 'approval_granted': False}
    if artifact_ids is not None:
        data['selection']['artifact_ids'] = list(artifact_ids)
    if relation_types is not None:
        data['selection']['relation_types'] = list(relation_types)
    return data
