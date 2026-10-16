"""Closed table declarations adapted to the existing Query/SRX contracts."""
from ..graph.scope_descriptors import ScopeDescriptor
from ..query import NormalizedQuery
from ..srx import MISSING
from ..srx.errors import SrxError
from ..srx.pointers import parse_pointer
from ..srx.types import VALUE_TYPES, value_type


class TableProjection:
    def __init__(self, error_type):
        self.error_type = error_type

    def _fail(self, reason, source, pointer):
        raise self.error_type(reason, path=source.path, pointer=pointer)


    def _columns(self, values, source, pointer, *, literal=False, view=False):
        """Closed column forms; a static field is not a template expression."""
        result = []
        for index, value in enumerate(values):
            at = pointer + '/' + str(index)
            if type(value) is not dict:
                self._fail('table_column_required', source, at)
            if 'field' in value:
                if view:
                    self._fail('table_column_contract', source, at)
                allowed = {'field', 'heading', 'data_type'} if literal else {'field'}
                if not set(value) <= allowed or type(value['field']) is not str:
                    self._fail('table_column_contract', source, at)
                if literal and not value['field'].strip():
                    self._fail('table_column_contract', source, at + '/field')
                if 'heading' in value and (type(value['heading']) is not str or not value['heading'].strip()):
                    self._fail('table_column_contract', source, at + '/heading')
                field, declared, missing = value['field'], value.get('data_type'), 'preserve'
                field_pointer = at + '/field'
            else:
                if (literal or set(value) != {'source', 'heading', 'data_type', 'format', 'missing'}
                        or type(value['source']) is not dict
                        or set(value['source']) != {'kind', 'pointer'}
                        or value['source']['kind'] != 'artifact_field'
                        or type(value['heading']) is not str or not value['heading'].strip()):
                    self._fail('table_column_contract', source, at)
                if value['format'] != 'plain':
                    self._fail('table_column_format_provider_required', source, at + '/format')
                if value['missing'] != 'error':
                    self._fail('table_column_missing_provider_required', source, at + '/missing')
                field, declared, missing = value['source']['pointer'], value['data_type'], 'error'
                field_pointer = at + '/source/pointer'
            if 'data_type' in value and (type(declared) is not str or declared not in VALUE_TYPES[1:]):
                self._fail('table_column_data_type', source, at + '/data_type')
            tokens = None
            if not literal:
                try:
                    tokens = parse_pointer(field, rule_id='document-table', at=field_pointer)
                except SrxError as error:
                    raise self.error_type('table_column_pointer_invalid', path=source.path, pointer=field_pointer) from error
                if tokens and tokens[0] == 'verification_result':
                    self._fail('query_verification_provider_required', source, field_pointer)
            result.append((tokens, declared, missing, at))
        return result


    def _cell(self, value, column, source):
        _, declared, missing, pointer = column
        kind = value_type(value, rule_id='document-table')
        if value is MISSING:
            if missing == 'error': self._fail('table_column_value_missing', source, pointer)
            return {'type': 'missing'}
        if declared is not None and kind != declared:
            self._fail('table_column_value_type', source, pointer)
        return {'type': kind, 'value': value}


    def _view_query(self, value, source, source_count):
        descriptor = ScopeDescriptor(value['scope_descriptor'])
        if descriptor.scope_kind != 'project' or descriptor.data['boundary_policy'] != 'closed':
            self._fail('table_view_scope_provider_required', source, '/scope_descriptor')
        if value['grouping'] or value['relation_projections']:
            self._fail('table_view_projection_provider_required', source, '/relation_projections')
        # Validate every declared view column even when a query block supplies its
        # own columns. Unsupported declarations cannot disappear behind an override.
        self._columns(value['columns'], source, '/columns', view=True)
        ordering = []
        for index, item in enumerate(value['sort']):
            if (type(item) is not dict or set(item) != {'key', 'direction'}
                    or type(item['key']) is not str or item['direction'] not in ('asc', 'desc')):
                self._fail('table_view_sort_contract', source, '/sort/' + str(index))
            ordering.append(item['key'] + ':' + item['direction'])
        # A view has no implicit 100-row page. This basic project view selects all
        # its filtered rows; a query block's normalized envelope retains its page.
        query = NormalizedQuery(srx_filters=[value['filter']], sort=ordering, limit=source_count)
        return query, descriptor


    def _literal_rows(self, payload, columns, source):
        rows = []
        for index, values in enumerate(payload['rows']):
            pointer = '/payload/rows/' + str(index)
            if len(values) != len(columns):
                self._fail('table_row_width', source, pointer)
            pending = list(values)
            while pending:
                current = pending.pop()
                if type(current) is dict:
                    if {'id', 'artifact_type'} <= set(current):
                        self._fail('table_literal_artifact_copy', source, pointer)
                    pending.extend(current.values())
                elif type(current) is list: pending.extend(current)
            rows.append({'cells': [self._cell(value, column, source) for value, column in zip(values, columns)]})
        return rows
