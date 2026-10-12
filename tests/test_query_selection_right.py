"""Query input/status boundaries and exact combinations on owned source bytes."""
import copy
import itertools
import pytest

from specroad.graph.relations import SourceRelations
from specroad.model.errors import ModelError
from specroad.query import NormalizedQuery, select_query
from specroad.srx import SrxError
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.relations import aid
from support.srx import binary, expression_document, field, literal


def record(number, **changes):
    return SourceRelations(artifact_bytes(domain_value('requirement', id=aid(number=number), **changes)))


def test_stored_plan_status_combinations_return_exact_ids_and_values():
    statuses = ('not_planned', 'planned', 'running', 'waived', 'not_applicable')
    records = [record(i + 1, verification_plan_status=status, owner='a' if i % 2 == 0 else 'b')
               for i, status in enumerate(statuses)]
    query = NormalizedQuery(filters={'verification_plan_status': ['planned', 'running', 'waived'],
                                     'owner': ['a', 'b']},
        srx_filters=[expression_document(binary('ne', field('/owner'), literal('b')))],
        select=['/verification_plan_status', '/implementation_status'])
    result = select_query(records, query, project={})
    assert result.artifact_ids == (aid(number=3),)
    assert result.items == [{'id': aid(number=3), 'artifact_type': 'requirement',
        'values': {'/verification_plan_status': 'running', '/implementation_status': 'not_started'}}]


@pytest.mark.parametrize('options', [
    {'type': ['requirement', 'REQUIREMENT']}, {'maturity': ['draft', 'passed']},
    {'implementation_status': ['implemented', 'done']},
    {'verification_plan_status': ['planned', 'passed']},
    {'has_relation': ['depends_on', 'unknown']}, {'missing_relation': ['unknown']}])
def test_invalid_alternative_is_not_ignored_because_another_value_is_valid(options):
    with pytest.raises(ModelError) as caught:
        NormalizedQuery(filters=options)
    assert caught.value.reason == 'query_filter_value_invalid'
    assert caught.value.pointer == '/filters/' + next(iter(options))


@pytest.mark.parametrize('pointer', ['/verification_result', '/verification_result/status'])
@pytest.mark.parametrize('populated', [False, True])
def test_computed_verification_projection_requires_provider_even_without_matches(pointer, populated):
    query = NormalizedQuery(filters={'owner': ['nobody']}, select=[pointer])
    with pytest.raises(ModelError) as caught:
        select_query([record(1, owner='other')] if populated else [], query, project={})
    assert caught.value.reason == 'query_verification_provider_required'
    assert caught.value.pointer == '/select'


@pytest.mark.parametrize('name,value', [('verification_plan_status', 'passed'),
    ('verification_plan_status', None), ('implementation_status', True),
    ('implementation_status', ['implemented'])])
def test_invalid_stored_status_on_unselected_source_rejects_partial_success(name, value):
    records = [record(1, owner='selected'), record(2, owner='other', **{name: value})]
    with pytest.raises(ModelError) as caught:
        select_query(records, NormalizedQuery(filters={'owner': ['selected']}), project={})
    assert caught.value.reason == 'query_stored_status_invalid'
    assert caught.value.pointer == '/' + name


def test_extension_metadata_named_verification_result_remains_passive_data():
    source = record(1, extensions={'org.example': {'verification_result': 'external-note'}})
    query = NormalizedQuery(select=['/extensions/org.example/verification_result', '/absent'])
    result = select_query([source], query, project={})
    assert result.items[0]['values'] == {'/extensions/org.example/verification_result': 'external-note',
                                       '/absent': {'state': 'missing'}}


def test_normalized_envelope_roundtrip_is_owned_and_preserves_projection_order():
    query = NormalizedQuery(filters={'owner': ['team-b', 'team-a']},
        srx_filters=[expression_document(literal(True))], select=['/revision', '/title'],
        sort=['/extensions/org.example/a:desc:asc'], offset=9, limit=0)
    data = query.data
    loaded = NormalizedQuery.from_data(data)
    assert loaded.data == query.data and loaded.sha256 == query.sha256
    data['select'].clear();data['srx_filters'][0]['expression']['expression']['value'] = False
    assert loaded.data == query.data


@pytest.mark.parametrize('mutation', ['top', 'empty_filter', 'operand', 'sort', 'missing_field',
                                     'empty_group', 'wrong_hash', 'boolean_limit'])
def test_untrusted_normalized_envelope_rejects_unknown_or_noncanonical_fields(mutation):
    data = NormalizedQuery(srx_filters=[expression_document(literal(True))]).data
    if mutation == 'top':data['unrecognized'] = True
    elif mutation == 'empty_filter':data['filters']['unrecognized'] = []
    elif mutation == 'operand':data['srx_filters'][0]['filename'] = '/tmp/filter.json'
    elif mutation == 'sort':data['sort'][0]['extra'] = True
    elif mutation == 'missing_field':del data['evaluation']
    elif mutation == 'empty_group':data['filters']['owner'] = []
    elif mutation == 'wrong_hash':data['srx_filters'][0]['sha256'] = '0' * 64
    elif mutation == 'boolean_limit':data['limit'] = True
    with pytest.raises(ModelError):
        NormalizedQuery.from_data(data)


def test_self_consistent_srx_hash_does_not_admit_an_unknown_operator():
    from specroad.model.canonical import canonical_json_sha256
    data = NormalizedQuery().data
    document = expression_document({'op': 'external', 'command': 'not-executed'})
    data['srx_filters'] = [{'expression': document, 'sha256': canonical_json_sha256(document)}]
    with pytest.raises(SrxError) as caught:
        NormalizedQuery.from_data(data)
    assert caught.value.reason == 'unsupported_operator'


def test_scope_metadata_is_not_a_query_provider_or_an_executable_query():
    with pytest.raises(ModelError) as caught:
        select_query([], NormalizedQuery().data, project={})
    assert caught.value.reason == 'normalized_query_required'


def test_empty_supported_inventory_has_exact_empty_selection():
    query = NormalizedQuery.from_data(NormalizedQuery(filters={'type': ['requirement']},
                                                     select=['/title']).data)
    result = select_query([], query, project={})
    assert result.items == [] and result.artifact_ids == () and result.total == result.source_count == 0
    assert result.query_sha256 == query.sha256 and result.pagination_applied is False


def test_unicode_owner_values_are_exact_and_are_not_fulltext_normalized():
    records = [record(1, owner='Café'), record(2, owner='Cafe\u0301'), record(3, owner='CAFÉ')]
    for owner, expected in [('Café', 1), ('Cafe\u0301', 2), ('CAFÉ', 3)]:
        result = select_query(records, NormalizedQuery(filters={'owner': [owner]}), project={})
        assert result.artifact_ids == (aid(number=expected),)


def test_all_source_permutations_preserve_exact_combined_selection_and_binding():
    records = [record(1, owner='a'), record(2, owner='b'), record(3, owner='a', revision=2)]
    query = NormalizedQuery(filters={'owner': ['b', 'a'], 'maturity': ['draft']},
        srx_filters=[expression_document(binary('eq', field('/revision'), literal(1)))],
        select=['/owner', '/revision'])
    first = select_query(records, query, project={})
    assert first.artifact_ids == (aid(number=1), aid(number=2))
    assert first.items == [{'id': aid(number=n), 'artifact_type': 'requirement',
                            'values': {'/owner': owner, '/revision': 1}} for n, owner in ((1, 'a'), (2, 'b'))]
    for order in itertools.permutations(records):
        result = select_query(order, query, project={})
        assert result.items == first.items and result.inputs_sha256 == first.inputs_sha256


def test_filter_projection_and_context_mutations_do_not_reuse_old_results():
    records = [record(1, owner='a'), record(2, owner='b')]
    context = {'owner': 'a'}
    query = NormalizedQuery(srx_filters=[expression_document(binary('eq', field('/owner'),
                                                                    field('/owner', 'project')))])
    first = select_query(records, query, project=context)
    original = copy.deepcopy(first.items)
    context['owner'] = 'b'
    second = select_query(records, query, project=context)
    assert first.artifact_ids == (aid(number=1),) and second.artifact_ids == (aid(number=2),)
    assert first.inputs_sha256 != second.inputs_sha256 and first.items == original
