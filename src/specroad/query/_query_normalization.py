"""Pure query grammar normalization; no graph traversal or result projection."""
import unicodedata

from ..graph._scope_selector_contract import _query
from ..graph.relation_types import CORE_RELATION_TYPES
from ..model.artifact_schemas import MATURITIES
from ..model.artifact_types import artifact_types
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.domain_fields import IMPLEMENTATION_STATUSES, VERIFICATION_PLAN_STATUSES
from ..model.errors import ModelError
from ..srx import SrxProgram
from ..srx.pointers import parse_pointer


def _sequence(values):
    if type(values) not in (list, tuple):
        raise ModelError('query_sequence_required')
    return values


def _text(value):
    if type(value) is not str or not value.strip() or '\0' in value:
        raise ModelError('query_text_required')
    try:
        value.encode('utf-8')
    except UnicodeError as error:
        raise ModelError('query_text_required') from error
    return value


def normalize_query(*, filters=None, srx_filters=(), select=(), sort=(),
                    evaluation=None, offset=0, limit=None, default_limit=100):
    filters = {} if filters is None else filters
    canonical_json_bytes(filters)
    if type(filters) is not dict:
        raise ModelError('query_filter_object_required')
    groups = {}
    for name, values in filters.items():
        checked = [_text(value) for value in _sequence(values)]
        if name == 'full_text':
            checked = [unicodedata.normalize('NFC', value).casefold() for value in checked]
        # Keep empty groups until the closed grammar has rejected unknown
        # names; an absent/empty known group contributes true at selection.
        groups[name] = sorted(set(checked), key=lambda value: value.encode('utf-8'))
    expressions = []
    for index, document in enumerate(_sequence(srx_filters)):
        program = SrxProgram(document, rule_id='query-filter-' + str(index))
        expressions.append({'expression': program.document,
                            'sha256': canonical_json_sha256(program.document)})
    pointers = []
    for pointer in _sequence(select):
        parse_pointer(pointer, rule_id='query-projection')
        if pointer not in pointers:
            pointers.append(pointer)
    ordering = []
    for value in _sequence(sort):
        value = _text(value)
        key, separator, direction = value.rpartition(':')
        if not separator or direction not in ('asc', 'desc'):
            key, direction = value, 'asc'
        ordering.append({'key': key, 'direction': direction})
    if not ordering:
        ordering = [{'key': 'artifact_type', 'direction': 'asc'},
                    {'key': 'id', 'direction': 'asc'}]
    value = {'filters': groups, 'srx_filters': expressions, 'select': pointers,
             'sort': ordering, 'evaluation': evaluation, 'offset': offset,
             'limit': default_limit if limit is None else limit}
    canonical_json_bytes(value)
    _query(value)
    vocabularies = {'type': tuple(item.artifact_type for item in artifact_types()),
        'maturity': MATURITIES, 'implementation_status': IMPLEMENTATION_STATUSES,
        'verification_plan_status': VERIFICATION_PLAN_STATUSES,
        'has_relation': (*CORE_RELATION_TYPES, 'superseded_by'),
        'missing_relation': (*CORE_RELATION_TYPES, 'superseded_by')}
    for name, choices in vocabularies.items():
        if any(item not in choices for item in groups.get(name, ())):
            raise ModelError('query_filter_value_invalid', pointer='/filters/' + name)
    value['filters'] = {name: values for name, values in groups.items() if values}
    return canonical_json_bytes(value)
