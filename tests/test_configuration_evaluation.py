"""Configuration evaluation, complete dependency paths and real read-only commands."""
from dataclasses import FrozenInstanceError
import json
from unittest.mock import patch

import pytest

from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.result_schemas import validate_result_document
from specroad.configurations import evaluate_configuration
from specroad.configurations.evaluation import ConfigurationEvaluationError
from specroad.configurations.project_evaluation import evaluate_project_configuration
from specroad.graph.path_output import PathRecord
from specroad.graph.relations import SourceRelations
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.model.schema_catalog import SchemaCatalog
from specroad.query.read_work import ReadCommandWork
from support.artifacts import artifact_bytes
from support.model import put
from support.read_only import inventory, make_project, no_write_attempts
from support.records import record_value
from support.relations import aid, artifact, edge, rid
from support.srx import binary, expression_document, field, literal


def configuration(number=1, **changes):
    return record_value('configuration', id=aid('configuration', number), name='Variant ' + str(number), **changes)


def condition(value):
    return expression_document(binary('eq', field('/effective_values/platform', 'configuration'), literal(value)))


def records(*values):
    return tuple(SourceRelations(artifact_bytes(value)) for value in values)


def evaluate(*values, selected=aid('configuration')):
    return evaluate_configuration(records(*values), selected).data


def chain():
    return [configuration(), artifact(relations=[edge('depends_on', aid(number=2))]),
            artifact(number=2, relations=[edge('depends_on', aid(number=3), number=2)]),
            artifact(number=3, applicability=condition('windows'))]


def project(root, values=None):
    root.mkdir()
    make_project(root, *(chain() if values is None else values))
    return root


def signature(conflict):
    path = conflict['path']
    PathRecord.from_dict(path)
    return ([item['id'] for item in path['artifacts']],
            [item['relation_id'] for item in path['relations']], path['inverse'])


def test_classifications_include_unconditional_matching_and_excluded_records():
    result = evaluate(configuration(), artifact(), artifact(number=2, applicability=condition('linux')),
                      artifact(number=3, applicability=condition('windows')))
    assert result['applicable_artifact_ids'] == [aid('configuration'), aid(), aid(number=2)]
    assert result['excluded_artifact_ids'] == [aid(number=3)]
    by_id = {item['artifact_id']: item for item in result['evaluations']}
    assert by_id[aid()]['reason'] == 'unconditional'
    assert by_id[aid(number=2)]['reason'] == 'condition_true'
    assert by_id[aid(number=3)]['reason'] == 'condition_false'
    assert result['consistent'] and result['inconsistent_dependencies'] == []
    assert result['dependency_scope'] == 'stored_strong_relations'
    assert result['source_count'] == 4 and result['relation_count'] == 0
    validate_result_document('configuration-evaluation-v1', result)


def test_all_applicable_origins_receive_complete_shortest_dependency_paths():
    result = evaluate(*chain())
    assert not result['consistent']
    assert [(c['source_id'], c['target_id'], c['distance']) for c in result['inconsistent_dependencies']] == [
        (aid(), aid(number=3), 2), (aid(number=2), aid(number=3), 1)]
    assert signature(result['inconsistent_dependencies'][0]) == (
        [aid(), aid(number=2), aid(number=3)], [rid(), rid(2)], [False, False])
    assert signature(result['inconsistent_dependencies'][1]) == (
        [aid(number=2), aid(number=3)], [rid(2)], [False])


def test_shorter_route_wins_over_a_lexicographically_earlier_long_route():
    values = chain()
    values[1]['relations'].append(edge('depends_on', aid(number=3), number=3))
    result = evaluate(*values)
    first = result['inconsistent_dependencies'][0]
    assert first['distance'] == 1
    assert signature(first) == ([aid(), aid(number=3)], [rid(3)], [False])


def test_multiple_excluded_targets_are_all_reported():
    result = evaluate(configuration(), artifact(relations=[edge('depends_on', aid(number=2)),
        edge('depends_on', aid(number=3), number=2)]),
        artifact(number=2, applicability=condition('windows')),
        artifact(number=3, applicability=condition('windows')))
    assert [item['target_id'] for item in result['inconsistent_dependencies']] == [aid(number=2), aid(number=3)]


def test_excluded_source_is_not_an_applicable_origin_or_transit_node():
    values = chain(); values[2]['applicability'] = condition('windows')
    result = evaluate(*values)
    assert [(c['source_id'], c['target_id']) for c in result['inconsistent_dependencies']] == [(aid(), aid(number=2))]


@pytest.mark.parametrize('kind', ['conflicts_with', 'duplicates'])
def test_weak_relations_are_not_required_variant_dependencies(kind):
    result = evaluate(configuration(), artifact(relations=[edge(kind, aid(number=2))]),
                      artifact(number=2, applicability=condition('windows')))
    assert result['consistent'] and not result['inconsistent_dependencies']


def test_stored_direction_is_not_reversed_to_invent_a_required_path():
    result = evaluate(configuration(), artifact(), artifact(number=2, applicability=condition('windows'),
                      relations=[edge('depends_on', aid())]))
    assert result['consistent']


def test_dependency_cycle_terminates_and_preserves_shortest_explanation():
    values = chain(); values[2]['relations'].append(edge('depends_on', aid(), number=3))
    result = evaluate(*values)
    assert [c['distance'] for c in result['inconsistent_dependencies']] == [2, 1]


def test_selected_parent_chain_drives_both_classifications_and_explanations():
    root = configuration()
    child = configuration(2, parent=root['id'], dimensions=[], selection={'platform': 'windows'})
    result = evaluate(root, child, artifact(applicability=condition('windows')), selected=child['id'])
    assert aid() in result['applicable_artifact_ids']
    assert result['configuration']['effective_values']['platform'] == 'windows'
    assert result['configuration']['configuration_id'] == child['id']


def test_configuration_only_inventory_has_a_complete_empty_conflict_set():
    result = evaluate(configuration())
    assert result['applicable_artifact_ids'] == [aid('configuration')]
    assert result['evaluations'][0]['reason'] == 'unconditional'
    assert result['consistent']


def test_source_order_and_original_json_formatting_do_not_change_semantic_result():
    values = chain()
    original = records(*values)
    reformatted = tuple(SourceRelations(json.dumps(value, indent=4).encode()) for value in reversed(values))
    assert evaluate_configuration(original, aid('configuration')).data == evaluate_configuration(
        reformatted, aid('configuration')).data
    assert [r.source_bytes for r in original] == [artifact_bytes(v) for v in values]


def test_result_is_owned_and_does_not_modify_original_sources():
    supplied = records(*chain()); before = [r.source_bytes for r in supplied]
    result = evaluate_configuration(supplied, aid('configuration'))
    changed = result.data; changed['configuration']['effective_values']['platform'] = 'changed'
    changed['inconsistent_dependencies'].clear()
    assert result.data['configuration']['effective_values']['platform'] == 'linux'
    assert len(result.data['inconsistent_dependencies']) == 2
    assert [r.source_bytes for r in supplied] == before
    with pytest.raises(FrozenInstanceError):
        result._encoded = b'{}'


def test_missing_explicit_configuration_is_a_configuration_error():
    with pytest.raises(ConfigurationEvaluationError) as caught:
        evaluate(artifact())
    assert caught.value.code == 'SRV130' and caught.value.reason == 'configuration_missing'


def test_invalid_applicability_is_an_error_instead_of_an_exclusion():
    with pytest.raises(ConfigurationEvaluationError) as caught:
        evaluate(configuration(), artifact(applicability=expression_document(literal('false'))))
    assert caught.value.reason == 'invalid_applicability'
    assert caught.value.pointer.startswith('/applicability')


def test_missing_required_target_prevents_any_evaluation_result():
    with pytest.raises(ModelError):
        evaluate(configuration(), artifact(relations=[edge('depends_on', aid(number=2))]))


def test_public_project_command_returns_complete_conflict_data_with_model_exit_code(tmp_path):
    root = project(tmp_path / 'project')
    result = evaluate_project_configuration(root, aid('configuration'))
    assert result.exit_code == 3 and result.complete
    assert result.as_dict()['result'] == evaluate(*chain())
    assert len(result.diagnostics) == 2 and {d.code for d in result.diagnostics} == {'SRV131'}
    assert {d.artifact_id for d in result.diagnostics} == {aid(), aid(number=2)}
    assert all(d.rationale == 'configuration_dependency_excluded' for d in result.diagnostics)
    assert not result.details['atomic_snapshot'] and not result.details['full_semantic_validation']
    assert not result.details['approval_granted'] and not result.details['write_authorized']


def test_consistent_project_command_returns_success(tmp_path):
    root = project(tmp_path / 'project', [configuration(), artifact()])
    result = evaluate_project_configuration(root, aid('configuration'))
    assert result.exit_code == 0 and result.complete and not result.diagnostics
    assert result.as_dict()['result']['consistent']


def test_cli_request_and_direct_api_share_the_same_read_result(tmp_path):
    root = project(tmp_path / 'project')
    direct = evaluate_project_configuration(root, aid('configuration'))
    cli = dispatch_result(['configuration', 'evaluate', aid('configuration'), '--project', str(root), '--format=json'])
    api = execute_request({'command_id': 'configuration.evaluate',
        'arguments': {'configuration_id': aid('configuration')}, 'options': {'--project': str(root)}}).result
    for result in (cli, api):
        assert result.exit_code == direct.exit_code == 3
        assert result.as_dict()['result'] == direct.as_dict()['result']
        assert [d.as_dict() for d in result.diagnostics] == [d.as_dict() for d in direct.diagnostics]


def test_project_evaluation_works_without_write_permission_or_write_attempts(tmp_path):
    root = project(tmp_path / 'project')
    paths = [root, *root.rglob('*')]; modes = {p: p.stat().st_mode & 0o777 for p in paths}
    try:
        for path in paths:
            path.chmod(0o555 if path.is_dir() else 0o444)
        before = inventory(root)
        with no_write_attempts(), patch('builtins.input', side_effect=AssertionError('stdin')), \
                patch('secrets.token_bytes', side_effect=AssertionError('entropy')):
            result = evaluate_project_configuration(root, aid('configuration'))
            assert result.exit_code == 3 and result.complete
        assert inventory(root) == before
        assert not (root / '.specroad').exists()
    finally:
        for path, mode in modes.items():
            path.chmod(mode)


def test_retained_read_phases_do_not_publish_before_final_source_recheck(tmp_path):
    root = project(tmp_path / 'project')
    with ReadCommandWork('configuration.evaluate', root, configuration_id=aid('configuration')) as work:
        assert not work.advance(1) and work.state['phase'] == 'loaded'
        assert not work.advance(1) and work.state['phase'] == 'evaluated'
        with pytest.raises(ValueError):
            work.result
        assert work.advance(1) and work.state['units_completed'] == 3
        assert work.result.exit_code == 3 and work.result.complete


def test_source_replacement_after_evaluation_cannot_publish_old_result(tmp_path):
    root = project(tmp_path / 'project')
    with ReadCommandWork('configuration.evaluate', root, configuration_id=aid('configuration')) as work:
        assert not work.advance(2)
        put(root, artifact_path('requirement', aid(), 'SR'), artifact_bytes(artifact(revision=2)))
        assert work.advance(1)
        assert work.result.exit_code == 6 and work.result.result is None


def test_configuration_revision_change_after_evaluation_is_a_conflict(tmp_path):
    root = project(tmp_path / 'project')
    with ReadCommandWork('configuration.evaluate', root, configuration_id=aid('configuration')) as work:
        assert not work.advance(2)
        put(root, artifact_path('configuration', aid('configuration'), 'SR'), artifact_bytes(configuration(revision=2)))
        assert work.advance(1) and work.result.exit_code == 6
        assert work.result.result is None


def test_missing_configuration_command_preserves_model_reason_and_code(tmp_path):
    root = project(tmp_path / 'project', [artifact()])
    result = evaluate_project_configuration(root, aid('configuration'))
    assert result.exit_code == 3 and not result.complete and result.result is None
    assert result.diagnostics[0].code == 'SRV130'
    assert result.diagnostics[0].rationale == 'configuration_missing'


def test_command_rejects_missing_id_and_unadvertised_configuration_option(tmp_path):
    root = project(tmp_path / 'project')
    for args in (['configuration', 'evaluate'],
                 ['configuration', 'evaluate', aid('configuration'), '--configuration', aid('configuration')]):
        assert dispatch_result(args + ['--project', str(root), '--format=json']).exit_code == 2


def test_published_command_contract_and_result_schema_are_executable(tmp_path):
    command = builtin_registry().resolve('configuration.evaluate')
    assert command.words == ('configuration', 'evaluate')
    assert command.command_class.value == 'read_only'
    assert command.protocol.result_schema == 'configuration-evaluation-v1'
    assert command.budget_policy_version == 'runtime-budget-v2'
    assert not command.protocol.work.continuation_supported
    root = project(tmp_path / 'project')
    result = evaluate_project_configuration(root, aid('configuration'))
    catalog = SchemaCatalog()
    catalog.validate('configuration-evaluation-v1', result.as_dict()['result'])
    malformed = result.as_dict()['result']; malformed['inconsistent_dependencies'][0]['distance'] = 0
    with pytest.raises(ModelError):
        catalog.validate('configuration-evaluation-v1', malformed)
