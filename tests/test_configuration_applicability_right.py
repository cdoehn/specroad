"""Explicit selection requirements and complete applicability access boundaries."""
import pytest

from specroad.configurations import ApplicabilityResult, evaluate_applicability, resolve_configuration
from specroad.graph.relations import SourceRelations
from specroad.model.errors import ModelError
from support.artifacts import artifact_bytes
from support.records import record_value
from support.srx import binary, expression_document, field, literal, quantifier


def source(node=None, **changes):
    value = record_value('document', tags=['safety'])
    if node is not None:
        value['applicability'] = expression_document(node)
    value.update(changes)
    return SourceRelations(artifact_bytes(value), path='spec/documents/source.json')


def selected(prefix='SR'):
    value = record_value('configuration', id=prefix + '-CFG-' + '0' * 26)
    return resolve_configuration([SourceRelations(artifact_bytes(value))], value['id'])


@pytest.mark.parametrize('node', [None, literal(True), literal(False), field('/effective_values/unknown', 'configuration')],
                         ids=['unconditional', 'true', 'false', 'missing'])
def test_required_selection_cannot_be_replaced_by_any_artifact_condition(node):
    record = source(node)
    before = record.source_bytes
    with pytest.raises(ModelError) as caught:
        evaluate_applicability(record, require_configuration=True)
    assert caught.value.reason == 'configuration_required'
    assert caught.value.path == record.path
    assert record.source_bytes == before


@pytest.mark.parametrize('value', [None, 0, 1, '', 'false', [], {}])
def test_selection_requirement_is_an_exact_boolean_option(value):
    with pytest.raises(ModelError) as caught:
        evaluate_applicability(source(), selected(), require_configuration=value)
    assert caught.value.reason == 'configuration_requirement_boolean_required'


def test_explicit_selection_satisfies_the_requirement_without_changing_classification():
    record = source(binary('eq', field('/effective_values/platform', 'configuration'), literal('linux')))
    configuration = selected()
    assert evaluate_applicability(record, configuration, require_configuration=True).data == (
        evaluate_applicability(record, configuration).data)


def test_required_selection_also_applies_to_direct_result_construction():
    with pytest.raises(ModelError) as caught:
        ApplicabilityResult(source(), require_configuration=True)
    assert caught.value.reason == 'configuration_required'


@pytest.mark.parametrize('node,configuration', [(None, None), (literal(True), None), (literal(False), True)],
                         ids=['applicable', 'potential', 'excluded'])
def test_classifications_have_no_implicit_gate_truth_value(node, configuration):
    result = evaluate_applicability(source(node), selected() if configuration else None)
    with pytest.raises(TypeError):
        bool(result)


@pytest.mark.parametrize('node', [None, literal(True)], ids=['unconditional', 'conditional'])
def test_configuration_from_another_project_prefix_is_rejected(node):
    with pytest.raises(ModelError) as caught:
        evaluate_applicability(source(node), selected('XX'))
    assert caught.value.reason == 'configuration_project_mismatch'


def test_matching_foreign_prefix_is_a_valid_explicit_same_project_pair():
    record = source(literal(True), id='XX-DOC-' + '0' * 26)
    assert evaluate_applicability(record, selected('XX')).status == 'applicable'


def wrapped(node, placement):
    if placement == 'direct':
        return node
    if placement == 'short-or':
        return {'op': 'or', 'args': [literal(True), node]}
    if placement == 'short-and':
        return {'op': 'and', 'args': [literal(False), node]}
    if placement == 'empty-any':
        return quantifier('any', literal([]), node)
    if placement == 'empty-all':
        return quantifier('all', literal([]), node)
    return {'op': 'not', 'arg': node}


@pytest.mark.parametrize('configured', [False, True])
@pytest.mark.parametrize('context', ['project', 'relations'])
@pytest.mark.parametrize('placement', ['direct', 'short-or', 'short-and', 'empty-any', 'empty-all', 'unary'])
def test_every_executable_branch_rejects_forbidden_context_access(configured, context, placement):
    node = wrapped({'op': 'exists', 'arg': field('', context)}, placement)
    with pytest.raises(ModelError) as caught:
        evaluate_applicability(source(node), selected() if configured else None)
    assert caught.value.reason == 'invalid_applicability'
    assert caught.value.__cause__.reason == 'applicability_context_forbidden'
    assert caught.value.pointer.endswith('/context')


@pytest.mark.parametrize('configured', [False, True])
@pytest.mark.parametrize('pointer', ['/relations', '/relations/0/type', '/applicability', '/purpose',
                                   '/verification_result', '/__class__', '/relat~1ions', '/relations~0'])
def test_content_derived_values_and_relation_paths_are_not_metadata(configured, pointer):
    with pytest.raises(ModelError) as caught:
        evaluate_applicability(source({'op': 'exists', 'arg': field(pointer)}), selected() if configured else None)
    assert caught.value.__cause__.reason == 'applicability_field_forbidden'


GRAPH_NODES = [
    pytest.param({'op': 'relation_count', 'direction': 'both', 'types': '*'}, id='relation-count'),
    pytest.param({'op': 'incoming_count', 'types': '*'}, id='incoming-count'),
    pytest.param({'op': 'has_relation', 'direction': 'outgoing', 'types': '*'}, id='has-relation'),
    pytest.param({'op': 'reachable', 'direction': 'both', 'types': '*', 'where': literal(True), 'max_depth': 0},
                 id='reachable'),
]


@pytest.mark.parametrize('configured', [False, True])
@pytest.mark.parametrize('node', GRAPH_NODES)
def test_every_graph_operator_is_rejected_even_in_a_skipped_branch(configured, node):
    with pytest.raises(ModelError) as caught:
        evaluate_applicability(source({'op': 'or', 'args': [literal(True), node]}),
                               selected() if configured else None)
    assert caught.value.__cause__.reason == 'applicability_graph_forbidden'


def test_literal_context_shaped_data_does_not_gain_external_access():
    value = {'project': {'secret': 'passive'}, 'relations': ['passive']}
    node = quantifier('all', literal([value]), binary('eq', field('/project/secret', 'item'), literal('passive')))
    assert evaluate_applicability(source(node), selected()).status == 'applicable'


def test_namespaced_extension_data_is_passive_metadata():
    node = binary('eq', field('/extensions/example.context/project'), literal('stored'))
    record = source(node, extensions={'example.context': {'project': 'stored'}})
    assert evaluate_applicability(record, selected()).status == 'applicable'


def test_quantifier_item_cannot_be_used_outside_its_lexical_predicate():
    with pytest.raises(ModelError) as caught:
        evaluate_applicability(source({'op': 'exists', 'arg': field('', 'item')}), selected())
    assert caught.value.__cause__.reason == 'unknown_context'


def test_constant_metadata_condition_stays_potential_without_selection():
    node = binary('eq', field('/artifact_type'), literal('document'))
    assert evaluate_applicability(source(node)).status == 'potentially_applicable'


def test_missing_optional_metadata_is_not_an_exclusion_result():
    with pytest.raises(ModelError) as caught:
        evaluate_applicability(source(field('/owner')), selected())
    assert caught.value.__cause__.actual == 'missing'


def test_null_metadata_remains_null_and_is_not_missing():
    node = binary('eq', field('/extensions/example.value'), literal(None))
    assert evaluate_applicability(source(node, extensions={'example.value': None}), selected()).status == 'applicable'


def test_runtime_arithmetic_failure_is_reported_only_when_configuration_is_selected():
    record = source(binary('eq', binary('divide', literal(1), literal(0)), literal(0)))
    assert evaluate_applicability(record).status == 'potentially_applicable'
    with pytest.raises(ModelError) as caught:
        evaluate_applicability(record, selected())
    assert caught.value.reason == 'invalid_applicability'


def test_source_identity_is_rebuilt_from_replacement_bytes():
    record = source(literal(True))
    replacement = source(literal(False), id='SR-DOC-' + '1' * 26)
    object.__setattr__(record, 'source_bytes', replacement.source_bytes)
    result = evaluate_applicability(record, selected())
    assert result.artifact_id == replacement.identity.id
    assert result.status == 'excluded'


def test_source_byte_replacement_cannot_hide_configuration_applicability():
    record = source(literal(True))
    value = record_value('configuration', applicability=expression_document(literal(True)))
    object.__setattr__(record, 'source_bytes', artifact_bytes(value))
    with pytest.raises(ModelError) as caught:
        evaluate_applicability(record, selected())
    assert caught.value.reason == 'configuration_applicability_forbidden'


def test_error_diagnostic_does_not_include_private_operand_values():
    record = source(binary('eq', field('/effective_values/platform', 'configuration'), literal('PRIVATE_VALUE')))
    value = record.data
    value['applicability']['expression'] = {'op': 'not', 'arg': literal('PRIVATE_VALUE')}
    record = SourceRelations(artifact_bytes(value), path=record.path)
    with pytest.raises(ModelError) as caught:
        evaluate_applicability(record, selected())
    assert 'PRIVATE_VALUE' not in str(caught.value.diagnostic())
    assert 'PRIVATE_VALUE' not in str(caught.value.__cause__.diagnostic())
