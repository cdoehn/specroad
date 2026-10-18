"""Closed view planning, independent of row evaluation and rendering adapters."""
from ..graph._graph_traversal import _cycle_witness
from ..graph.scope_descriptors import ScopeDescriptor
from ..query import NormalizedQuery
from ..srx.errors import SrxError
from ..srx.graph_validation import validate_graph_node
from ..srx.pointers import parse_pointer
from ..srx.types import VALUE_TYPES


def plan_view(value, source, source_count, error_type):
    def fail(reason, pointer):
        raise error_type(reason, path=source.path, pointer=pointer)

    descriptor = ScopeDescriptor(value['scope_descriptor'])
    if descriptor.scope_kind != 'project' or descriptor.data['boundary_policy'] != 'closed':
        fail('view_scope_provider_required', '/scope_descriptor')
    # Every declaration is checked before filtering, including unused columns
    # and projections. An empty result cannot conceal an executable declaration.
    formats = value['formats']
    for i, name in enumerate(formats):
        if name not in ('json', 'markdown', 'html', 'csv'):
            fail('view_format_provider_required', '/formats/' + str(i))
        if name in formats[:i]:
            fail('view_format_duplicate', '/formats/' + str(i))
    projections = {}
    for i, projection in enumerate(value['relation_projections']):
        at = '/relation_projections/' + str(i)
        fields = {'id', 'direction', 'types', 'max_depth', 'aggregation'}
        if type(projection) is dict and projection.get('aggregation') == 'records':
            fields.add('columns')
        if (type(projection) is not dict
                or set(projection) != fields
                or type(projection['id']) is not str or not projection['id'].strip()
                or projection['id'].strip() != projection['id']
                or projection['id'] in projections):
            fail('view_relation_projection_contract', at)
        if projection['aggregation'] not in ('ids', 'count', 'records'):
            fail('view_relation_aggregation_required', at + '/aggregation')
        if type(projection['types']) is not list or not projection['types']:
            fail('view_relation_types_required', at + '/types')
        validate_graph_node({'op': 'reachable', 'where': {'op': 'literal', 'value': True},
            **{k: projection[k] for k in ('direction', 'types', 'max_depth')}},
            rule_id='document-view', at=at)
        projections[projection['id']] = projection

    def plan_column(column, at):
        if (type(column) is not dict
                or set(column) - {'serialization'} != {'source', 'heading', 'data_type', 'format', 'missing'}
                or type(column['source']) is not dict
                or type(column['heading']) is not str or not column['heading'].strip()):
            fail('view_column_contract', at)
        if column['format'] != 'plain':
            fail('view_column_format_provider_required', at + '/format')
        if 'serialization' in column and column['serialization'] != {'csv': 'typed-json-v1'}:
            fail('view_column_serialization_contract', at + '/serialization')
        if column['missing'] not in ('error', 'preserve'):
            fail('view_column_missing_provider_required', at + '/missing')
        if type(column['data_type']) is not str or column['data_type'] not in VALUE_TYPES[1:]:
            fail('view_column_data_type', at + '/data_type')
        selected = column['source']
        kind = selected.get('kind')
        if kind == 'artifact_field' and set(selected) == {'kind', 'pointer'}:
            try:
                tokens = parse_pointer(selected['pointer'], rule_id='document-view', at=at + '/source/pointer')
            except SrxError as error:
                raise error_type('view_column_pointer_invalid', path=source.path, pointer=at + '/source/pointer') from error
            if not tokens:
                fail('view_column_field_required', at + '/source/pointer')
            if tokens[0] == 'verification_result':
                fail('query_verification_provider_required', at + '/source/pointer')
            return kind, tokens, column['data_type'], column['missing'], at
        elif kind == 'relation_projection' and set(selected) == {'kind', 'projection_id'}:
            name = selected['projection_id']
            if type(name) is not str or name not in projections:
                fail('view_relation_projection_missing', at + '/source/projection_id')
            expected = 'number' if projections[name]['aggregation'] == 'count' else 'array'
            if column['data_type'] != expected:
                fail('view_column_data_type', at + '/data_type')
            return kind, name, expected, column['missing'], at
        else:
            fail('view_column_source_provider_required', at + '/source')

    columns = [plan_column(column, '/columns/' + str(i))
               for i, column in enumerate(value['columns'])]
    projection_columns = {}
    dependencies = []
    for i, (name, projection) in enumerate(projections.items()):
        if projection['aggregation'] != 'records':
            continue
        at = '/relation_projections/' + str(i) + '/columns'
        nested = projection['columns']
        if type(nested) is not list or not nested:
            fail('view_relation_columns_required', at)
        projection_columns[name] = [plan_column(column, at + '/' + str(j))
                                    for j, column in enumerate(nested)]
        dependencies.extend((name, selector, pointer)
            for kind, selector, _, _, pointer in projection_columns[name]
            if kind == 'relation_projection')
    cycle = _cycle_witness(dependencies, source_id=lambda edge: edge[0],
                          target_id=lambda edge: edge[1], edge_id=lambda edge: edge[2])
    if cycle is not None:
        fail('view_relation_projection_cycle', cycle[0][2] + '/source/projection_id')

    grouping = []
    for i, group in enumerate(value['grouping']):
        at = '/grouping/' + str(i)
        if (type(group) is not dict or set(group) != {'column', 'direction'}
                or type(group['column']) is not int or not 0 <= group['column'] < len(columns)
                or group['direction'] not in ('asc', 'desc')
                or group['column'] in [number for number, _ in grouping]):
            fail('view_grouping_contract', at)
        if columns[group['column']][2] not in ('null', 'boolean', 'number', 'string'):
            fail('view_grouping_scalar_required', at + '/column')
        grouping.append((group['column'], group['direction']))
    ordering = []
    for i, item in enumerate(value['sort']):
        if (type(item) is not dict or set(item) != {'key', 'direction'}
                or type(item['key']) is not str or item['direction'] not in ('asc', 'desc')):
            fail('view_sort_contract', '/sort/' + str(i))
        ordering.append(item['key'] + ':' + item['direction'])
    query = NormalizedQuery(srx_filters=[value['filter']], sort=ordering, limit=source_count)
    return descriptor, projections, columns, projection_columns, grouping, query
