"""Query normalization, filtering and projection over explicitly supplied records.

This is the selection stage, before ordering and pagination. It neither loads a
project nor certifies complete project coverage, evaluation currency or approval.
The normalized envelope also binds the options consumed by later query stages.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import unicodedata

from ..graph._scope_selector_contract import _query
from ..graph.relation_types import CORE_RELATION_TYPES
from ..model.artifact_schemas import MATURITIES
from ..model.artifact_types import artifact_types
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.domain_fields import IMPLEMENTATION_STATUSES, VERIFICATION_PLAN_STATUSES
from ..model.errors import ModelError
from ..srx import EvaluationContext, LoadedGraph, SrxProgram, evaluate, require_type, MISSING
from ..srx.pointers import parse_pointer, resolve_tokens


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


@dataclass(frozen=True, init=False)
class NormalizedQuery:
    """Materialized scope-query grammar. SRX inputs are documents, never paths.

    A valid envelope is not proof that every downstream provider exists. In
    particular, selection cannot invent verification results or release closure.
    """
    _encoded: bytes

    def __init__(self, *, filters=None, srx_filters=(), select=(), sort=(),
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
        object.__setattr__(self, '_encoded', canonical_json_bytes(value))

    @classmethod
    def from_data(cls, value):
        """Revalidate a closed normalized envelope, including every SRX binding.

        Scope metadata or a matching hash alone cannot authenticate a program.
        No unknown field or non-normalized value is silently discarded.
        """
        canonical_json_bytes(value)
        _query(value)
        result = cls(filters=value['filters'],
            srx_filters=[item['expression'] for item in value['srx_filters']],
            select=value['select'],
            sort=[item['key'] + ':' + item['direction'] for item in value['sort']],
            evaluation=value['evaluation'], offset=value['offset'], limit=value['limit'])
        if result.data != value:
            raise ModelError('non_normalized_query')
        return result

    @property
    def data(self):
        return json.loads(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()


@dataclass(frozen=True, init=False)
class QuerySelection:
    """Owned complete selection within the supplied inventory, not a result page."""
    query_sha256: str
    inputs_sha256: str
    source_count: int
    artifact_ids: tuple
    _items: bytes

    def __init__(self, query, inputs_sha256, source_count, ids, items):
        object.__setattr__(self, 'query_sha256', query.sha256)
        object.__setattr__(self, 'inputs_sha256', inputs_sha256)
        object.__setattr__(self, 'source_count', source_count)
        object.__setattr__(self, 'artifact_ids', tuple(ids))
        # Preserve requested pointer order in each values object. This is an
        # owned projection, not the canonical hash representation of the input.
        object.__setattr__(self, '_items', json.dumps(items, ensure_ascii=False,
                                                    allow_nan=False).encode('utf-8'))

    @property
    def items(self):
        return json.loads(self._items)

    @property
    def total(self):
        return len(self.artifact_ids)

    @property
    def pagination_applied(self):
        return False

    @property
    def validation_scope(self):
        return 'supplied_query_inventory_only'


def select_query(records, query, *, project, configuration=None):
    """OR within a value group; AND across groups and all SRX expressions.

    No file access, cache hints, callbacks, implicit evaluation or early paging.
    Sort/offset/limit remain bound for later stages and do not truncate selection.
    Unsupported semantic providers fail even for an empty candidate inventory.
    """
    if type(query) is not NormalizedQuery:
        raise ModelError('normalized_query_required')
    data = query.data
    for name in ('verification_result', 'release', 'full_text'):
        if name in data['filters']:
            raise ModelError('query_filter_provider_required', pointer='/filters/' + name)
    if data['evaluation'] is not None:
        raise ModelError('query_evaluation_provider_required')
    records = _sequence(records)
    graph = LoadedGraph(records, rule_id='query')
    roots = EvaluationContext({'artifact': {}, 'project': project,
        'configuration': configuration, 'relations': []}, rule_id='query').data
    input_hash = canonical_json_sha256({'project': roots['project'],
        'configuration': roots['configuration'],
        'sources': sorted(({'id': record.identity.id,
                           'sha256': sha256(record.source_bytes).hexdigest()} for record in records),
                          key=lambda item: item['id'])})
    programs = tuple(SrxProgram(item['expression'], rule_id='query-filter-' + str(index))
                     for index, item in enumerate(data['srx_filters']))
    pointers = [(pointer, parse_pointer(pointer, rule_id='query-projection'))
                for pointer in data['select']]
    # Validate these known stored status contracts over the entire supplied
    # inventory, including candidates which a later value filter will omit.
    for identifier in graph.artifact_ids:
        artifact = graph.artifact(identifier, rule_id='query')
        if 'verification_result' in artifact:
            raise ModelError('query_stored_verification_result', pointer='/verification_result')
        for name, choices in (('implementation_status', IMPLEMENTATION_STATUSES),
                              ('verification_plan_status', VERIFICATION_PLAN_STATUSES)):
            if name in artifact and (type(artifact[name]) is not str or artifact[name] not in choices):
                raise ModelError('query_stored_status_invalid', pointer='/' + name)
    if any(tokens and tokens[0] == 'verification_result' for _, tokens in pointers):
        raise ModelError('query_verification_provider_required', pointer='/select')
    selected = []
    for identifier in graph.artifact_ids:
        current = graph.candidate_roots(roots, identifier, rule_id='query')
        artifact = current['artifact']
        kinds = {view['type'] for view in current['relations']}
        matches = True
        for name, values in data['filters'].items():
            if name == 'tag':
                matched = any(value in artifact.get('tags', []) for value in values)
            elif name == 'has_relation':
                matched = any(value in kinds for value in values)
            elif name == 'missing_relation':
                matched = any(value not in kinds for value in values)
            else:
                field = 'artifact_type' if name == 'type' else name
                matched = any(artifact.get(field, MISSING) == value for value in values)
            matches = matches and matched
        if not matches:
            continue
        context = EvaluationContext(current, rule_id='query', graph=graph)
        for program in programs:
            matched = require_type(evaluate(program, context), ('boolean',),
                                   rule_id=program.rule_id)
            if not matched:
                matches = False
                break
        if not matches:
            continue
        if pointers:
            values = {}
            for pointer, tokens in pointers:
                value = resolve_tokens(artifact, tokens, rule_id='query-projection')
                values[pointer] = {'state': 'missing'} if value is MISSING else value
            item = {'id': identifier, 'artifact_type': artifact['artifact_type'], 'values': values}
        else:
            fields = ('id', 'artifact_type', 'title', 'revision', 'maturity',
                      'implementation_status', 'verification_plan_status')
            item = {name: artifact[name] for name in fields if name in artifact}
        selected.append((artifact['artifact_type'], identifier, item))
    selected.sort(key=lambda item: (item[0], item[1]))
    return QuerySelection(query, input_hash, len(records),
                          [item[1] for item in selected], [item[2] for item in selected])
