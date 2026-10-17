"""Closed view planning, independent of row evaluation and rendering adapters."""
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
    if descriptor.data['configuration_id'] is not None:
        fail('view_configuration_provider_required', '/scope_descriptor/configuration_id')

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
        if (type(projection) is not dict
                or set(projection) != {'id', 'direction', 'types', 'max_depth', 'aggregation'}
                or type(projection['id']) is not str or not projection['id'].strip()
                or projection['id'].strip() != projection['id']
                or projection['id'] in projections):
            fail('view_relation_projection_contract', at)
        if projection['aggregation'] not in ('ids', 'count'):
            fail('view_relation_aggregation_required', at + '/aggregation')
        if type(projection['types']) is not list or not projection['types']:
            fail('view_relation_types_required', at + '/types')
        validate_graph_node({'op': 'reachable', 'where': {'op': 'literal', 'value': True},
            **{k: projection[k] for k in ('direction', 'types', 'max_depth')}},
            rule_id='document-view', at=at)
        projections[projection['id']] = projection

    columns = []
    for i, column in enumerate(value['columns']):
        at = '/columns/' + str(i)
        if (type(column) is not dict
                or set(column) != {'source', 'heading', 'data_type', 'format', 'missing'}
                or type(column['source']) is not dict
                or type(column['heading']) is not str or not column['heading'].strip()):
            fail('view_column_contract', at)
        if column['format'] != 'plain':
            fail('view_column_format_provider_required', at + '/format')
        if column['missing'] != 'error':
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
            columns.append((kind, tokens, column['data_type'], at))
        elif kind == 'relation_projection' and set(selected) == {'kind', 'projection_id'}:
            name = selected['projection_id']
            if type(name) is not str or name not in projections:
                fail('view_relation_projection_missing', at + '/source/projection_id')
            expected = 'array' if projections[name]['aggregation'] == 'ids' else 'number'
            if column['data_type'] != expected:
                fail('view_column_data_type', at + '/data_type')
            columns.append((kind, name, expected, at))
        else:
            fail('view_column_source_provider_required', at + '/source')

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
    return descriptor, projections, columns, grouping, query
