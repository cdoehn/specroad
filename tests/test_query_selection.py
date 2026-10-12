"""Owned query inputs and exact filtering/projection oracles; no CLI claim."""
import copy
from dataclasses import FrozenInstanceError
import pytest

from specroad.graph.relations import SourceRelations
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.query.selection import NormalizedQuery, select_query
from specroad.srx import SrxError
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.relations import aid, edge
from support.srx import expression_document, binary, field, literal
from support.srx_graph import incoming


def value(number, kind='requirement', **changes):
    return domain_value(kind, id=aid(kind, number), **changes)


def select(values, **options):
    return select_query(tuple(SourceRelations(artifact_bytes(v)) for v in values),
                        NormalizedQuery(**options), project={})


def test_repeated_values_are_or_and_distinct_groups_are_and():
    values = [value(1, owner='team-a'), value(2, owner='team-b'),
              value(3, owner='team-c'), value(4, owner='team-a', maturity='retired')]
    result = select(values, filters={'owner': ['team-a', 'team-b'], 'maturity': ['draft']})
    assert result.artifact_ids == (aid(number=1), aid(number=2))
    assert result.total == 2
    assert result.items == [{key: values[i][key] for key in
        ('id', 'artifact_type', 'title', 'revision', 'maturity',
         'implementation_status', 'verification_plan_status')} for i in (0, 1)]


def test_all_srx_filters_are_and_with_each_other_and_value_filters():
    values = [value(i, owner='a' if i < 4 else 'b', revision=i) for i in range(1, 5)]
    filters = [expression_document(binary('gt', field('/revision'), literal(1))),
               expression_document(binary('lt', field('/revision'), literal(3)))]
    assert select(values, filters={'owner': ['a']}, srx_filters=filters).artifact_ids == (aid(number=2),)
    assert select(values, srx_filters=[expression_document(literal(True)),
                                     expression_document(literal(False))]).items == []


def test_empty_and_duplicate_groups_have_no_extra_effect():
    values = [value(1, owner='a'), value(2, owner='b')]
    assert select(values, filters={'owner': []}).items == select(values).items
    assert select(values, filters={'owner': ['a', 'a']}).items == select(values, filters={'owner': ['a']}).items
    assert NormalizedQuery(filters={'owner': ['b', 'a', 'a']}).sha256 == NormalizedQuery(filters={'owner': ['a', 'b']}).sha256


def test_tags_and_stored_statuses_combine_without_verification_invention():
    values = [value(1, tags=['offline', 'fast'], implementation_status='implemented', verification_plan_status='planned'),
              value(2, tags=['slow'], implementation_status='implemented', verification_plan_status='planned'),
              value(3, tags=['offline'], verification_plan_status='not_planned')]
    result = select(values, filters={'tag': ['offline', 'fast'],
        'implementation_status': ['implemented'], 'verification_plan_status': ['planned']})
    assert result.artifact_ids == (aid(number=1),)
    assert result.items[0]['verification_plan_status'] == 'planned'
    assert 'verification_result' not in result.items[0]


def test_relation_filters_include_real_incoming_views_and_missing_group_is_or():
    values = [value(1, relations=[edge('depends_on', aid(number=2))]), value(2), value(3)]
    assert select(values, filters={'has_relation': ['depends_on']}).artifact_ids == (aid(number=1), aid(number=2))
    assert select(values, filters={'missing_relation': ['depends_on']}).artifact_ids == (aid(number=3),)
    assert select(values, filters={'missing_relation': ['depends_on', 'refines']}).total == 3
    assert select(values, filters={'has_relation': ['depends_on'], 'missing_relation': ['depends_on']}).total == 0


def test_inverse_superseded_by_is_a_computed_relation_filter():
    values = [value(1, relations=[edge('supersedes', aid(number=2))]), value(2)]
    assert select(values, filters={'has_relation': ['superseded_by']}).artifact_ids == (aid(number=2),)
    assert select(values, filters={'has_relation': ['supersedes']}).artifact_ids == (aid(number=1),)


def test_srx_graph_reads_all_sources_before_value_filtering():
    values = [value(1, owner='source', relations=[edge('depends_on', aid(number=2))]),
              value(2, owner='target')]
    predicate = expression_document(binary('eq', incoming(), literal(1)))
    assert select(values, filters={'owner': ['target']}, srx_filters=[predicate]).artifact_ids == (aid(number=2),)


def test_srx_context_uses_explicit_project_configuration_and_computed_relations():
    records = [SourceRelations(artifact_bytes(value(1, owner='engineering')))]
    predicate = expression_document(binary('eq', field('/owner'), field('/expected', 'project')))
    result = select_query(records, NormalizedQuery(srx_filters=[predicate]),
                         project={'expected': 'engineering'},
                         configuration={'configuration_id': 'cfg', 'effective_values': {}})
    assert result.artifact_ids == (aid(number=1),)


def test_projection_preserves_pointer_order_missing_null_false_and_nested_data():
    source = value(1, extensions={'org.example': {'a/b': {'~': [None, False, 0, {'x': 'Grüße'}]}}})
    pointers = ['/title', '/extensions/org.example/a~1b/~0/3', '/absent',
                '/extensions/org.example/a~1b/~0/0', '/extensions/org.example/a~1b/~0/1',
                '/extensions/org.example/a~1b/~0/2']
    result = select([source], select=pointers)
    assert result.items == [{'id': source['id'], 'artifact_type': 'requirement', 'values': dict(zip(
        pointers, [source['title'], {'x': 'Grüße'}, {'state': 'missing'}, None, False, 0]))}]
    assert list(result.items[0]['values']) == pointers


def test_root_projection_is_detached_and_repeated_select_keeps_first_position():
    source = value(1)
    result = select([source], select=['/title', '', '/title'])
    item = result.items[0]
    assert list(item['values']) == ['/title', '']
    assert item['values'][''] == source
    item['values']['']['title'] = 'changed'
    assert result.items[0]['values']['']['title'] == source['title']


def test_complete_grammar_materializes_scope_values_and_binds_srx_content():
    doc = expression_document(literal(True))
    query = NormalizedQuery(filters={'type': ['goal'], 'verification_result': ['passed'],
        'release': [aid('release', 1)], 'full_text': ['CAFE\u0301']}, srx_filters=[doc],
        select=['/title'], sort=['title:desc', '/revision:asc'], evaluation={'evaluation_version': 'pending'},
        offset=3, limit=7)
    data = query.data
    assert data['filters']['full_text'] == ['café']
    assert data['srx_filters'] == [{'expression': doc, 'sha256': canonical_json_sha256(doc)}]
    assert data['sort'] == [{'key': 'title', 'direction': 'desc'}, {'key': '/revision', 'direction': 'asc'}]
    assert (data['offset'], data['limit']) == (3, 7)
    descriptor = ScopeDescriptor({'scope_version': 'scope-v1', 'scope_kind': 'query',
        'selector': {'query': data}, 'configuration_id': None,
        'closure_profile': 'core-closure-v1', 'boundary_policy': 'closed'})
    assert descriptor.data['selector']['query'] == data
    doc['expression']['value'] = False
    data['filters'].clear()
    assert query.data['srx_filters'][0]['expression']['expression']['value'] is True


def test_selection_is_complete_before_bound_sort_offset_and_limit():
    values = [value(i, title=str(6-i)) for i in range(1, 6)]
    result = select(values, sort=['title:desc'], offset=100, limit=0)
    assert result.total == result.source_count == 5
    assert result.artifact_ids == tuple(aid(number=i) for i in range(1, 6))
    assert result.pagination_applied is False
    assert result.validation_scope == 'supplied_query_inventory_only'
    assert NormalizedQuery(default_limit=17).data['limit'] == 17


@pytest.mark.parametrize('name', ['verification_result', 'release', 'full_text'])
def test_absent_semantic_provider_never_fakes_empty_success(name):
    with pytest.raises(ModelError) as caught:
        select([], filters={name: ['value']})
    assert caught.value.reason == 'query_filter_provider_required'
    assert caught.value.pointer == '/filters/' + name


def test_passive_evaluation_metadata_is_not_trusted_as_current_evidence():
    with pytest.raises(ModelError) as caught:
        select([], evaluation={'status': 'passed'})
    assert caught.value.reason == 'query_evaluation_provider_required'


@pytest.mark.parametrize('answer', [None, 0, 1, 'yes', [], {}])
def test_non_boolean_srx_answer_is_error_not_truthiness(answer):
    with pytest.raises(SrxError) as caught:
        select([value(1)], srx_filters=[expression_document(literal(answer))])
    assert caught.value.reason == 'operand_type'


def test_missing_srx_answer_is_error():
    with pytest.raises(SrxError) as caught:
        select([value(1)], srx_filters=[expression_document(field('/absent'))])
    assert caught.value.actual == 'missing'


def test_program_structure_is_validated_even_with_empty_candidates():
    with pytest.raises(SrxError):
        select([], srx_filters=[expression_document({'op': 'execute', 'path': '/tmp/query'})])
    with pytest.raises(SrxError):
        NormalizedQuery(srx_filters=['/tmp/query.json'])


@pytest.mark.parametrize('options', [{'filters': {'unknown': []}}, {'offset': True},
    {'limit': -1}, {'select': ['bad']}, {'sort': ['unknown']}, {'filters': {'owner': 'team'}}])
def test_invalid_query_shape_is_rejected_before_selection(options):
    with pytest.raises((ModelError, SrxError)):
        select([], **options)


def test_unselected_broken_graph_cannot_create_partial_success():
    with pytest.raises(SrxError) as caught:
        select([value(1, owner='selected'), value(2, owner='other',
            relations=[edge('depends_on', aid(number=99))])], filters={'owner': ['selected']})
    assert caught.value.reason == 'graph_model_invalid'


def test_stored_verification_result_is_never_accepted_as_a_computation():
    with pytest.raises(ModelError) as caught:
        select([value(1, verification_result='passed')], select=['/verification_result'])
    assert caught.value.reason == 'query_stored_verification_result'


def test_order_bindings_and_input_bytes_are_stable_and_owned():
    values = [value(2), value(1, 'goal')]
    originals = copy.deepcopy(values)
    first, second = select(values), select(list(reversed(values)))
    assert first.artifact_ids == (aid('goal', 1), aid(number=2))
    assert first.items == second.items
    assert first.inputs_sha256 == second.inputs_sha256
    values[0]['title'] = 'different'
    assert select(values).inputs_sha256 != first.inputs_sha256
    assert first.items == select(originals).items
    with pytest.raises(FrozenInstanceError):
        first.source_count = 0


def test_pure_selection_never_opens_files_or_starts_processes(monkeypatch):
    import builtins
    import subprocess
    import socket
    records = [SourceRelations(artifact_bytes(value(1)))]
    query = NormalizedQuery(select=['/title'])
    def forbidden(*args, **kwargs):
        raise AssertionError('Query selection attempted host I/O')
    with monkeypatch.context() as guard:
        guard.setattr(builtins, 'open', forbidden)
        guard.setattr(subprocess, 'Popen', forbidden)
        guard.setattr(socket, 'socket', forbidden)
        result = select_query(records, query, project={})
    assert result.artifact_ids == (aid(number=1),)
