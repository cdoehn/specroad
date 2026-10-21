"""Live M6 sorting and page delivery over an owned supplied-input selection.

Selection still materializes its input and matches. Sorting uses bounded runs;
advance performs real sort/delivery work, not replay of a precomputed page.
This is a process-local capability, not a durable Work checkpoint or CLI adapter.
"""

from ..diagnostics.spooling import DiagnosticSort
from ..model.errors import ModelError
from ..security.errors import SafetyViolation
from ..srx.pointers import parse_pointer
from ..storage._spool_segments import _positive
from ._query_normalization import _sequence
from .paging import QueryPage
from .selection import NormalizedQuery, select_query
from ._paging_spool import _QuerySpool, _rows
from ._configuration_inputs import configured_sources


class QueryWork:
    """Owned external sort followed by forward-only exact page construction.

    The caller chooses a new private spool root outside explicit protected
    boundaries. close releases handles and preserves all owned files. State is
    descriptive only; it grants no permission to reopen arbitrary spool paths.
    """

    def __init__(self, root, records, query, *, project, protected_roots,
                 configuration=None, configuration_id=None, batch_bytes=65536, verification=None):
        _positive(batch_bytes)
        if type(query) is not NormalizedQuery:
            raise ModelError('normalized_query_required')
        records = tuple(_sequence(records))
        records = configured_sources(records, configuration_id)
        data = query.data
        ordering = []
        for index, item in enumerate(data['sort']):
            pointer = '/sort/' + str(index)
            key = item['key']
            tokens = parse_pointer(key, rule_id='query-sort', at=pointer + '/key') if key.startswith('/') else (key,)
            if verification is None and tokens and tokens[0] == 'verification_result':
                raise ModelError('query_verification_provider_required', pointer=pointer)
            ordering.append((tokens, item['direction'] == 'desc', pointer))
        self._selection = select_query(records, query, project=project, configuration=configuration,
                                       configuration_id=configuration_id, verification=verification)
        self._evaluation_input = None if verification is None else verification.work_input
        ids = set(self._selection.artifact_ids)
        artifacts = {record.identity.id: record.data for record in records if record.identity.id in ids}
        if verification is not None:
            for subject in verification.data['aggregation']['subjects']:
                identifier = subject['subject_artifact_id']
                if identifier in artifacts:
                    artifacts[identifier] = {**artifacts[identifier],
                        'verification_result': subject['verification_result']}
        self._offset, self._limit = data['offset'], data['limit']
        self._items = []
        self._visited = self._units = 0
        self._cursor = self._result = None
        self._failed = self._closed = False
        self._sort = DiagnosticSort(root, _rows(self._selection, artifacts, ordering),
                                    protected_roots=protected_roots, batch_bytes=batch_bytes,
                                    _spool_type=_QuerySpool)

    @property
    def evaluation_input(self):
        return self._evaluation_input

    @property
    def state(self):
        return {'format': 'query-work-cursor-v1',
                'phase': 'complete' if self._result is not None else 'failed' if self._failed else
                         'cancelled' if self._closed else 'delivery' if self._cursor is not None else 'sorting',
                'query_sha256': self._selection.query_sha256,
                'inputs_sha256': self._selection.inputs_sha256,
                'evaluation_binding': self._selection.evaluation_binding,
                'units_completed': self._units, 'visited_records': self._visited,
                'retained_items': len(self._items), 'complete': self._result is not None,
                'durable_checkpoint': False, 'sort': self._sort.state,
                'delivery': None if self._cursor is None else self._cursor.state}

    @property
    def result(self):
        if self._result is None or self._closed:
            raise ValueError('Query work has no available complete page')
        return self._result

    def advance(self, units=1):
        _positive(units)
        if self._closed:
            raise ValueError('Query work is closed')
        try:
            for _ in range(units):
                if self._result is not None:
                    break
                if not self._sort.state['complete']:
                    self._sort.advance(1)
                elif self._cursor is None:
                    spool = self._sort.result
                    if spool.manifest['record_count'] != self._selection.total:
                        raise SafetyViolation('Query spool changed the complete selection count')
                    self._cursor = spool.cursor()
                elif self._visited < min(self._offset + self._limit, self._selection.total):
                    rows = self._cursor.read_page(1)
                    if len(rows) != 1:
                        raise SafetyViolation('Query spool delivery ended before the exact page')
                    if self._visited >= self._offset:
                        self._items.append(rows[0].item)
                    self._visited += 1
                else:
                    # Sorting is complete even for an empty page or limit zero.
                    # Check the owned run once more before publishing a result.
                    with self._sort.result.cursor():
                        pass
                    self._result = QueryPage(self._selection, self._items, self._offset, self._limit)
                    self._cursor.close()
                self._units += 1
            return self.state
        except BaseException:
            self._failed = True
            self._result = None
            self.close()
            raise

    def close(self):
        if not self._closed:
            self._closed = True
            self._sort.close()

    def __enter__(self):
        if self._closed:
            raise ValueError('Query work is closed')
        return self

    def __exit__(self, *unused):
        self.close()
