"""Exact query pages with independent order, count and original-value oracles."""
from itertools import permutations

import pytest

from specroad.graph.relations import SourceRelations
from specroad.model.errors import ModelError
from specroad.query import NormalizedQuery, query_records, select_query
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.relations import aid
from support.srx import binary, expression_document, field, literal


def requirement(number, **changes):
    value = domain_value('requirement', id=aid(number=number))
    value.update(changes)
    return value


def records(values):
    return [SourceRelations(artifact_bytes(value)) for value in values]


def page(values, **options):
    return query_records(records(values), NormalizedQuery(**options), project={})


def ids(result):
    return [item['id'] for item in result.data['items']]


def test_limit_one_changes_only_items_not_exact_filtered_total():
    values = [requirement(n, owner='wanted' if n in (1, 3, 5) else 'other') for n in range(5, 0, -1)]
    result = page(values, filters={'owner': ['wanted']}, limit=1)
    data = result.data
    assert set(data) == {'items', 'total', 'offset', 'limit', 'returned', 'truncated'}
    assert ids(result) == [aid(number=1)]
    assert {key: value for key, value in data.items() if key != 'items'} == {
        'total': 3, 'offset': 0, 'limit': 1, 'returned': 1, 'truncated': True}
    assert result.source_count == 5 and result.validation_scope == 'supplied_query_inventory_only'


def test_offset_is_applied_after_complete_sort_and_keeps_total():
    result = page([requirement(n) for n in (4, 2, 1, 3)], offset=1, limit=2)
    assert ids(result) == [aid(number=2), aid(number=3)]
    assert {key: value for key, value in result.data.items() if key != 'items'} == {
        'total': 4, 'offset': 1, 'limit': 2, 'returned': 2, 'truncated': True}
    last = page([requirement(n) for n in (4, 2, 1, 3)], offset=2, limit=2)
    assert ids(last) == [aid(number=3), aid(number=4)] and last.data['truncated'] is False


def test_default_order_is_type_then_id_not_source_order():
    values = [requirement(2), domain_value('goal', id=aid('goal', 2)),
              requirement(1), domain_value('goal', id=aid('goal', 1))]
    result = page(values)
    assert ids(result) == [aid('goal', 1), aid('goal', 2), aid(number=1), aid(number=2)]
    assert result.data['limit'] == 100 and result.data['total'] == 4


@pytest.mark.parametrize('key,first,second', [
    ('title', 'Alpha', 'Zulu'), ('maturity', 'draft', 'in_review'), ('revision', 2, 10),
    ('owner', 'a', 'z'), ('implementation_status', 'blocked', 'implemented'),
    ('verification_plan_status', 'planned', 'running')])
def test_named_scalar_keys_use_their_typed_ascending_order(key, first, second):
    values = [requirement(1, **{key: second}), requirement(2, **{key: first})]
    assert ids(page(values, sort=[key])) == [aid(number=2), aid(number=1)]
    assert ids(page(values, sort=[key + ':desc'])) == [aid(number=1), aid(number=2)]


@pytest.mark.parametrize('direction', ['asc', 'desc'])
def test_missing_null_boolean_number_string_precedence_and_numeric_order(direction):
    values = [requirement(1, extensions={'org.example': {}})]
    values += [requirement(n, extensions={'org.example': {'score': value}})
               for n, value in enumerate([None, False, True, -1, 2.5, 10, '2', 'a'], 2)]
    expected = list(range(1, 10)) if direction == 'asc' else list(range(9, 0, -1))
    result = page(list(reversed(values)), sort=['/extensions/org.example/score:' + direction])
    assert ids(result) == [aid(number=n) for n in expected]


def test_string_order_uses_nfc_utf8_without_casefold_or_original_rewrite():
    values = [requirement(4, title='é'), requirement(3, title='e\u0301'),
              requirement(2, title='a'), requirement(1, title='A')]
    result = page(values, sort=['title'], select=['/title'])
    assert ids(result) == [aid(number=n) for n in (1, 2, 3, 4)]
    assert [item['values']['/title'] for item in result.data['items']] == ['A', 'a', 'e\u0301', 'é']
    assert ids(page(values, sort=['title:desc'])) == [aid(number=n) for n in (3, 4, 2, 1)]


def test_multiple_keys_preserve_last_ascending_id_tie_breaker():
    values = [requirement(4, owner='b', title='Z'), requirement(3, owner='a', title='Z'),
              requirement(2, owner='a', title='Z'), requirement(1, owner='a', title='A')]
    assert ids(page(values, sort=['owner', 'title:desc'])) == [aid(number=n) for n in (2, 3, 1, 4)]


def test_sort_reads_original_fields_even_when_projection_omits_them():
    values = [requirement(1, description='first', extensions={'org.example': {'rank': 20}}),
              requirement(2, description='second', extensions={'org.example': {'rank': 3}})]
    result = page(values, sort=['/extensions/org.example/rank'], select=['/description'])
    assert result.data['items'] == [
        {'id': aid(number=2), 'artifact_type': 'requirement', 'values': {'/description': 'second'}},
        {'id': aid(number=1), 'artifact_type': 'requirement', 'values': {'/description': 'first'}}]


@pytest.mark.parametrize('bad', [{}, []])
@pytest.mark.parametrize('limit', [0, 1])
def test_non_scalar_sort_value_is_rejected_even_beyond_the_requested_page(bad, limit):
    values = [requirement(1, extensions={'org.example': {'score': 1}}),
              requirement(2, extensions={'org.example': {'score': bad}})]
    with pytest.raises(ModelError) as caught:
        page(values, sort=['/extensions/org.example/score'], limit=limit)
    assert (caught.value.reason, caught.value.pointer) == ('query_sort_value_not_scalar', '/sort/0')


def test_unselected_non_scalar_metadata_is_not_a_sort_operand():
    values = [requirement(1, owner='a', extensions={'org.example': {'score': 1}}),
              requirement(2, owner='b', extensions={'org.example': {'score': []}})]
    result = page(values, filters={'owner': ['a']}, sort=['/extensions/org.example/score'])
    assert ids(result) == [aid(number=1)] and result.data['total'] == 1


@pytest.mark.parametrize('key', ['verification_result', '/verification_result', '/verification_result/status'])
@pytest.mark.parametrize('empty', [False, True])
def test_computed_sort_requires_actual_provider_even_for_empty_input(key, empty):
    with pytest.raises(ModelError) as caught:
        page([] if empty else [requirement(1)], sort=[key])
    assert (caught.value.reason, caught.value.pointer) == ('query_verification_provider_required', '/sort/0')


def test_fulltext_value_and_srx_filters_all_precede_count_and_paging():
    values = [requirement(n, description='Café' if n != 4 else 'Tea', owner='a' if n != 5 else 'b')
              for n in (5, 4, 3, 2, 1)]
    predicate = expression_document(binary('ne', field('/id'), literal(aid(number=2))))
    result = page(values, filters={'full_text': ['cafe\u0301'], 'owner': ['a']},
                  srx_filters=[predicate], sort=['id:desc'], limit=1)
    assert ids(result) == [aid(number=3)]
    assert result.data['total'] == 2 and result.data['truncated'] is True


def test_zero_limit_returns_no_items_with_exact_nonzero_total():
    result = page([requirement(2), requirement(1)], limit=0)
    assert result.data == {'items': [], 'total': 2, 'offset': 0, 'limit': 0,
                           'returned': 0, 'truncated': True}


def test_effective_limit_is_materialized_without_hidden_result_count_cap():
    values = [requirement(n) for n in (3, 2, 1)]
    assert page(values, default_limit=1).data['limit'] == 1
    result = page(values, limit=10001)
    assert result.data['limit'] == 10001 and result.data['returned'] == result.data['total'] == 3
    assert result.data['truncated'] is False


def test_page_owns_projection_and_preserves_selection_input_and_query_bindings():
    values = [requirement(1, description='Cafe\u0301'), requirement(2, description='Café')]
    sources = records(values)
    before = [source.source_bytes for source in sources]
    query = NormalizedQuery(select=['/description', '/title'], limit=1)
    selected = select_query(sources, query, project={})
    result = query_records(sources, query, project={})
    changed = result.data
    changed['items'][0]['values']['/description'] = 'changed'
    changed['total'] = 999
    assert result.data['items'][0]['values']['/description'] == 'Cafe\u0301'
    assert list(result.data['items'][0]['values']) == ['/description', '/title']
    assert result.data['total'] == 2
    assert (result.query_sha256, result.inputs_sha256) == (selected.query_sha256, selected.inputs_sha256)
    assert selected.total == 2 and selected.pagination_applied is False
    assert [source.source_bytes for source in sources] == before


def test_all_input_permutations_have_the_same_sorted_page():
    values = [requirement(3, title='B'), requirement(1, title='A'), requirement(2, title='A')]
    results = [page(list(order), sort=['title:desc'], offset=1, limit=1) for order in permutations(values)]
    assert all(ids(result) == [aid(number=1)] for result in results)
    assert all(result.data == results[0].data for result in results)
    assert len({result.inputs_sha256 for result in results}) == 1


def test_query_paging_neither_consults_host_locale_nor_performs_io(monkeypatch):
    import builtins, locale, socket, subprocess
    sources = records([requirement(1, title='Z'), requirement(2, title='A')])
    query = NormalizedQuery(sort=['title'], limit=1)
    def forbidden(*args, **kwargs):
        raise AssertionError('Query paging consulted host state')
    with monkeypatch.context() as guard:
        for name in ('setlocale', 'strxfrm', 'strcoll'):
            guard.setattr(locale, name, forbidden)
        guard.setattr(builtins, 'open', forbidden)
        guard.setattr(socket, 'socket', forbidden)
        guard.setattr(subprocess, 'Popen', forbidden)
        result = query_records(sources, query, project={})
    assert ids(result) == [aid(number=2)]
