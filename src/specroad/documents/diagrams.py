"""Bound diagram projections and source bytes over an owned native graph.

No project discovery, file publication, renderer, browser or template execution.
The initial source profile labels nodes with validated artifact identities;
original titles remain data in the separate machine-readable projection.
"""
from collections import deque
from dataclasses import dataclass
from hashlib import sha256
import json

from .._metadata import __version__, MODEL_SCHEMA_VERSION
from ..graph.relations import SourceRelations
from ..graph.scope_descriptors import ScopeDescriptor
from ..graph.scope_inputs import ScopeSeedInputs
from ..graph.scope_seeds import resolve_scope_seeds
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..srx import LoadedGraph
from ..storage.json_syntax import parse_json_object


class DiagramError(ModelError):
    def __init__(self, reason, *, path=None, pointer='', exit_code=3):
        super().__init__(reason, path=path, pointer=pointer)
        self.exit_code = exit_code


@dataclass(frozen=True, init=False)
class DiagramData:
    """Detached selected identities and original source bindings, not approval."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use resolve_diagram with an owned TargetModel')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Diagram data is not project or release approval')


def resolve_diagram(model, diagram_kind, *, start_id, direction, max_depth,
                    max_nodes, max_edges):
    """Project traversed stored edges within an explicitly bounded native scope.

    Trace admits the supplied project graph. Architecture admits components and
    interfaces only. Release admits the native release seed set. Nodes at the
    requested depth are included without expansion. Count overflow is an error,
    never truncation. Traversal direction does not reverse normative edges.
    """
    from ..changes.target_model import TargetModel, _default_scope
    if type(model) is not TargetModel:
        raise ModelError('document_target_model_required')
    if type(diagram_kind) is not str or diagram_kind not in ('trace', 'architecture', 'release'):
        raise DiagramError('diagram_kind_not_supported', pointer='/diagram_kind', exit_code=2)
    if type(start_id) is not str:
        raise DiagramError('diagram_start_id_required', pointer='/start_id', exit_code=2)
    if type(direction) is not str or direction not in ('incoming', 'outgoing', 'both'):
        raise DiagramError('diagram_direction_required', pointer='/direction', exit_code=2)
    for name, value, minimum in (('max_depth', max_depth, 0), ('max_nodes', max_nodes, 1),
                                  ('max_edges', max_edges, 0)):
        if type(value) is not int or value < minimum:
            raise DiagramError('diagram_limit_required', pointer='/' + name, exit_code=2)
    model = model.snapshot()
    records = tuple(SourceRelations(d.content, path=d.path) for d in model.documents)
    by_id = {r.identity.id: r for r in records}
    if start_id not in by_id:
        raise DiagramError('diagram_start_not_found', pointer='/start_id')
    if diagram_kind == 'architecture':
        eligible = {r.identity.id for r in records
                    if r.identity.artifact_type in ('component', 'interface')}
        scope = {'kind': 'architecture_relations'}
    elif diagram_kind == 'release':
        if by_id[start_id].identity.artifact_type != 'release':
            raise DiagramError('diagram_release_start_required', pointer='/start_id')
        descriptor = ScopeDescriptor({**_default_scope(), 'scope_kind': 'release',
                                      'selector': {'release_id': start_id}})
        seeds = resolve_scope_seeds(descriptor, ScopeSeedInputs(model.configuration, records))
        eligible = set(seeds.artifact_ids)
        scope = {'kind': 'release_seed_relations', 'descriptor': descriptor.data,
                 'seed_inputs_sha256': seeds.inputs_sha256}
    else:
        eligible = set(by_id)
        scope = {'kind': 'supplied_project_relations'}
    if start_id not in eligible:
        raise DiagramError('diagram_start_outside_scope', pointer='/start_id')
    graph = LoadedGraph(records, rule_id='document-diagram', artifact_ids=sorted(eligible))
    distances, edges = {start_id: 0}, {}
    pending = deque([start_id])
    while pending:
        current = pending.popleft()
        distance = distances[current]
        if distance == max_depth:
            continue
        for view in graph.neighbours(current, direction, '*'):
            target = view.target.id
            if target not in distances:
                if len(distances) == max_nodes:
                    raise DiagramError('diagram_node_limit_exceeded', pointer='/max_nodes')
                distances[target] = distance + 1
                pending.append(target)
            if view.relation_id not in edges:
                if len(edges) == max_edges:
                    raise DiagramError('diagram_edge_limit_exceeded', pointer='/max_edges')
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
    result = object.__new__(DiagramData)
    object.__setattr__(result, '_encoded', canonical_json_bytes(data))
    return result


def render_diagram(model, diagram_kind, *, start_id, direction, max_depth,
                   max_nodes, max_edges, output_format='mermaid'):
    """Return deterministic UTF-8 source; never invoke a graphical renderer.

    Source profiles are mermaid-flowchart-ids-v1 and graphviz-dot-ids-v1.
    Only validated identities and Core relation kinds enter source labels.
    Other artifact content is retained in DiagramData, never interpolated here.
    """
    if type(output_format) is not str or output_format not in ('mermaid', 'dot'):
        raise DiagramError('diagram_format_not_supported', pointer='/output_format', exit_code=2)
    resolved = resolve_diagram(model, diagram_kind, start_id=start_id, direction=direction,
        max_depth=max_depth, max_nodes=max_nodes, max_edges=max_edges)
    data = resolved.data
    nodes = {node['artifact_id']: node['diagram_id'] for node in data['nodes']}
    if output_format == 'mermaid':
        lines = ['%% GENERATED — DO NOT EDIT', '%% diagram_data_sha256: ' + resolved.sha256,
                 'flowchart LR']
        for node in data['nodes']:
            lines.append('  ' + node['diagram_id'] + '["' + node['artifact_id'] + '"]')
        for edge in data['edges']:
            lines.append('  ' + nodes[edge['source']] + ' ' + edge['diagram_id'] +
                         '@-->|"' + edge['type'] + '"| ' + nodes[edge['target']])
    else:
        lines = ['// GENERATED — DO NOT EDIT', '// diagram_data_sha256: ' + resolved.sha256,
                 'digraph specroad {']
        for node in data['nodes']:
            lines.append('  ' + node['diagram_id'] + ' [label=' + json.dumps(node['artifact_id']) + '];')
        for edge in data['edges']:
            lines.append('  ' + nodes[edge['source']] + ' -> ' + nodes[edge['target']] +
                         ' [id=' + json.dumps(edge['diagram_id']) +
                         ', label=' + json.dumps(edge['type']) + '];')
        lines.append('}')
    return ('\n'.join(lines) + '\n').encode('utf-8')
