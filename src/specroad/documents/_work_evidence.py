"""Source-bound closure checks on retained document observations.

Check coverage and projections, not the completed composition/query/prose
algorithms again. Like other Work evidence, these checks do not authenticate
foreign checkpoints: the trusted initial binding and protected store matter.
"""
from hashlib import sha256

from ..changes.target_model import _default_scope
from ..graph.hierarchies import contains_position_key
from ..graph.references import RelationReferences
from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.domain_schemas import DOMAIN_TYPES
from ..query import NormalizedQuery
from ..query._selection_projection import project_item
from ..query.paging import _scalar_key
from ..srx.pointers import parse_pointer, resolve_tokens
from ..storage.domain_artifact import DomainArtifact
from ..storage.record_artifact import RecordArtifact
from ..work._data_contract import _count, _hash, _object, _parse
from ..work.resume import _require
from ._include_graph import _edge_data
from ._table_projection import TableProjection
from .blocks import ContentBlock
from .tables import TableBlockError


def _same(actual, expected):
    # JSON equality must distinguish booleans from counts and null from absence.
    _require(canonical_json_bytes(actual) == canonical_json_bytes(expected),
             'invalid_document_evidence')


class DocumentEvidence:
    def __init__(self, context, inputs):
        self.context = context
        self.configuration = _parse(inputs['project', 'specroad.json'])
        self.sources = tuple(SourceRelations(inputs['project', p], path=p)
                             for p in context['documents'])
        self.index = {s.identity.id: s for s in self.sources}
        _require(len(self.index) == len(self.sources), 'duplicate_document_source')

    def _scope(self):
        return {'project_id': self.context['project_id'], 'scope_descriptor': _default_scope(),
                'model_root_sha256': self.context['model_root_sha256'],
                'input_sha256': self.context['input_sha256']}

    def _bound(self, identifier, *, typed=False):
        _require(type(identifier) is str and identifier in self.index, 'document_source_required')
        source = self.index[identifier]; value = source.data
        if typed:
            reader = DomainArtifact if source.identity.artifact_type in DOMAIN_TYPES else RecordArtifact
            value = reader(source.source_bytes, path=source.path).data
        return {'artifact_id': identifier, 'artifact_type': value['artifact_type'],
                'revision': value['revision'], 'path': source.path,
                'source_sha256': sha256(source.source_bytes).hexdigest(),
                'record_sha256': canonical_json_sha256(value), 'record': value}

    def composition(self, data):
        _require(type(data) is dict, 'invalid_document_composition')
        _hash(data.get('structure_sha256'))
        _require(type(data.get('occurrences')) is list and bool(data['occurrences']),
                 'unfinished_document_composition')
        # The source edges define required children. A retained prefix, including
        # one which drops a repeated include, cannot close this frontier.
        references = RelationReferences(self.sources)
        include_ids = {s.identity.id for s in self.sources if s.data.get('block_kind') == 'include_document'}
        for identifier in include_ids:
            source = self.index[identifier]
            ContentBlock(source.source_bytes, path=source.path)
        pointers = {r.identity.id: '/relations/' + str(i)
                    for s in self.sources for i, r in enumerate(s.relations)}
        edges = [e for e in references.relations if e.relation.type == 'contains'
                 or (e.source.id in include_ids and e.relation.type == 'references')]
        outgoing = {}
        for edge in edges:
            outgoing.setdefault(edge.source.id, []).append(edge)
        for identifier, children in outgoing.items():
            if identifier not in include_ids:
                children.sort(key=contains_position_key)
        document_id = self.context['document_id']
        root = self._bound(document_id)
        _require(root['artifact_type'] == 'document', 'document_root_required')
        pending = [(document_id, None, None, 0)]; used = set()
        for number, occurrence in enumerate(data['occurrences']):
            _require(bool(pending), 'unexpected_document_occurrence')
            identifier, parent, via, depth = pending.pop()
            bound = self._bound(identifier); used.add(identifier)
            _same(occurrence, {'occurrence_index': number, 'artifact_id': identifier,
                'artifact_type': bound['artifact_type'], 'revision': bound['revision'],
                'parent_occurrence': parent, 'depth': depth, 'via': via})
            pending.extend((e.target.id, number, _edge_data(e, self.index, pointers), depth + 1)
                           for e in reversed(outgoing.get(identifier, ())))
        _require(not pending, 'unfinished_document_composition')
        _same(data, {'format_version': 1, 'kind': 'document-composition-v1', **self._scope(),
            'document_id': document_id, 'document_revision': root['revision'],
            'structure_sha256': data['structure_sha256'],
            'include_edges': [_edge_data(e, self.index, pointers) for e in sorted(edges,
                key=lambda e: (e.source.id, e.target.id, e.relation.identity.id))
                if e.relation.type == 'references'],
            'occurrences': data['occurrences'], 'occurrence_count': len(data['occurrences']),
            'records': {identifier: self._bound(identifier) for identifier in sorted(used)},
            'validation_scope': 'supplied_snapshot_document_composition',
            'document_structure_checked': True, 'include_graph_checked': True, 'include_graph_acyclic': True,
            **{k: False for k in ('project_files_verified', 'full_validation_passed', 'primary_role_checked',
                'payload_semantics_checked', 'rendering_performed', 'write_authorized', 'approval_granted')}})

    def table(self, block, data):
        _require(type(data) is dict and type(data.get('rows')) is list, 'invalid_document_table')
        projection = TableProjection(TableBlockError)
        source = self.index[block.data['id']]; column_source = source; payload = block.payload
        view = None; query = None; configuration_id = None
        if payload.get('source') == 'view':
            position, relation = next((i, r) for i, r in enumerate(source.relations) if r.type == 'references')
            target = self._bound(relation.target, typed=True); column_source = self.index[relation.target]
            query, descriptor = projection._view_query(target['record'], column_source, len(self.sources))
            configuration_id = descriptor.data['configuration_id']
            view = {k: target[k] for k in ('artifact_id', 'revision', 'path', 'source_sha256', 'record_sha256')}
            view.update(reference_id=relation.identity.id, reference_pointer='/relations/' + str(position),
                        scope_descriptor=descriptor.data, scope_descriptor_sha256=descriptor.sha256)
            column_values = payload['columns'] if block.block_kind == 'query' else target['record']['columns']
            if block.block_kind == 'query': column_source = source
        else:
            column_values = payload['columns']
            if block.block_kind == 'query': query = NormalizedQuery.from_data(payload['query'])
        columns = projection._columns(column_values, column_source,
            '/payload/columns' if column_source is source else '/columns', literal=query is None)
        page = data.get('query_result'); binding = None
        if query is None:
            _same(page, None)
            # Literal coverage is known from the bound payload, including empty
            # rows, order, nested values and the last row; no count is trusted.
            _same(data['rows'], projection._literal_rows(payload, columns, source))
        else:
            binding = self._query(query, page, configuration_id)
            _require(len(data['rows']) == len(page['items']), 'unfinished_document_table_page')
            for row, item in zip(data['rows'], page['items']):
                bound = self._bound(item['id'], typed=True)
                cells = [projection._cell(resolve_tokens(bound['record'], column[0],
                    rule_id='document-table', at=column[3]), column, column_source) for column in columns]
                _same(row, {**{k: bound[k] for k in
                    ('artifact_id', 'artifact_type', 'revision', 'source_sha256', 'record_sha256')}, 'cells': cells})
        empty_policy = payload.get('empty_policy')
        _require(bool(data['rows']) or empty_policy != 'error', 'unfinished_document_table_page')
        _same(data, {'format_version': 1, 'kind': 'table-block-data-v1', **self._scope(),
            'block': block.binding, 'view': view, 'columns': column_values, 'rows': data['rows'],
            'row_count': len(data['rows']), 'row_source': 'view' if view is not None else 'query' if query else 'literal',
            'query_binding': binding, 'query_result': page, 'empty_policy': empty_policy,
            'outcome': 'rows' if data['rows'] else empty_policy or 'empty',
            'validation_scope': 'supplied_snapshot_table_projection',
            **{k: False for k in ('project_files_verified', 'full_validation_passed',
                'document_structure_checked', 'rendering_performed', 'write_authorized', 'approval_granted')}})

    def _query(self, query, page, configuration_id):
        _object(page, ('items', 'total', 'offset', 'limit', 'returned', 'truncated'))
        for field in ('total', 'offset', 'limit', 'returned'): _count(page[field])
        _require(type(page['items']) is list and type(page['truncated']) is bool,
                 'invalid_document_query_page')
        declared = query.data
        _require(page['offset'] == declared['offset'] and page['limit'] == declared['limit']
            and page['total'] <= len(self.sources)
            and page['returned'] == len(page['items']) == min(page['limit'], max(0, page['total'] - page['offset']))
            and page['truncated'] is (page['offset'] + page['returned'] < page['total']),
            'unfinished_document_table_page')
        pointers = [(p, parse_pointer(p, rule_id='query-projection')) for p in declared['select']]
        ids = []
        for item in page['items']:
            _require(type(item) is dict, 'invalid_document_query_item')
            bound = self._bound(item.get('id'), typed=True); ids.append(bound['artifact_id'])
            _same(item, project_item(bound['record'], bound['artifact_id'], pointers))
        _require(len(set(ids)) == len(ids), 'duplicate_document_query_row')
        ordered = sorted(ids)
        for sort in reversed(declared['sort']):
            key = sort['key']
            tokens = parse_pointer(key, rule_id='query-sort') if key.startswith('/') else (key,)
            ordered.sort(key=lambda identifier: _scalar_key(resolve_tokens(self.index[identifier].data,
                tokens, rule_id='query-sort'), '/sort'), reverse=sort['direction'] == 'desc')
        _same(ids, ordered)
        configuration = None; configuration_binding = None
        if configuration_id is not None:
            from ..configurations import resolve_configuration
            effective = resolve_configuration(self.sources, configuration_id)
            configuration = effective.srx_context; configuration_binding = effective.binding
        inputs_hash = canonical_json_sha256({'project': self.configuration, 'configuration': configuration,
            'sources': sorted(({'id': s.identity.id, 'sha256': sha256(s.source_bytes).hexdigest()}
                               for s in self.sources), key=lambda s: s['id'])})
        return {'query': declared, 'query_sha256': query.sha256, 'inputs_sha256': inputs_hash,
                'source_count': len(self.sources), 'configuration_binding': configuration_binding}

    def reference(self, block, data):
        source = self.index[block.data['id']]
        position, relation = next((i, r) for i, r in enumerate(source.relations) if r.type == 'references')
        target = self._bound(relation.target, typed=True)
        _same(data, {'format_version': 'artifact-reference-v1', **self._scope(),
            'validation_scope': 'supplied_model_artifact_reference', 'reference_resolved': True,
            'block': block.binding, 'render_mode': block.payload['render_mode'],
            'relation': {'relation_id': relation.identity.id, 'source_id': source.identity.id,
                'target_id': target['artifact_id'], 'pointer': '/relations/' + str(position),
                'record': relation.data, 'record_sha256': canonical_json_sha256(relation.data)},
            'target': target, **{k: False for k in ('project_files_verified', 'full_validation_passed',
                'document_structure_checked', 'document_roles_checked', 'include_graph_checked',
                'payload_semantics_evaluated', 'rendering_performed', 'write_authorized', 'approval_granted')}})

    def prose(self, block, data):
        _require(type(data) is dict and type(data.get('content')) is dict, 'invalid_document_prose')
        normalized = block.payload['markdown'].replace('\r\n', '\n').replace('\r', '\n')
        _same(data, {'format_version': 1, 'kind': 'safe-prose-v1', 'block': block.binding,
            'normalized_markdown_sha256': sha256(normalized.encode('utf-8')).hexdigest(),
            'nodes_sha256': canonical_json_sha256(data['content']), 'content': data['content'],
            'validation_scope': 'owned_prose_nodes', 'prose_parsed': True,
            **{k: False for k in ('attachments_resolved', 'project_files_verified',
                'full_validation_passed', 'rendering_performed', 'write_authorized', 'approval_granted')}})
