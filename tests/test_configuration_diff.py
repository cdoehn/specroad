"""Actual variant membership deltas in the existing semantic Diff interfaces."""
import copy
import json

import pytest

from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.result_schemas import validate_result_document
from specroad.configurations.evaluation import ConfigurationEvaluationError
from specroad.graph.comparison import ComparisonInputs
from specroad.graph.relations import SourceRelations
from specroad.model.paths import artifact_path
from specroad.query import ComparisonSourceSnapshot, ReadCommandWork, compare_semantic, compare_sources, diff_project
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.portable import build_distribution
from support.processes import run_python
from support.read_only import inventory, make_project, no_write_attempts
from support.records import record_value
from support.relations import aid, edge
from support.srx import binary, expression_document, field, literal


def configuration(number=1, **changes):
    return record_value('configuration', id=aid('configuration', number), name='Variant ' + str(number), **changes)


def requirement(number=1, **changes):
    return domain_value('requirement', id=aid(number=number), language='en', **changes)


def condition(platform):
    return expression_document(binary('eq', field('/effective_values/platform', 'configuration'), literal(platform)))


def variants():
    return [configuration(), configuration(2, selection={'platform': 'windows'}), requirement(),
        requirement(2, applicability=condition('linux')), requirement(3, applicability=condition('windows'))]


def model(values):
    return ComparisonInputs('sample', tuple(SourceRelations(artifact_bytes(v), path=v['id'] + '.json') for v in values))


def compare(before, after, before_id=aid('configuration'), after_id=aid('configuration')):
    return compare_semantic(model(before), model(after), before_configuration_id=before_id,
                            after_configuration_id=after_id).data


def project(path, values):
    path.mkdir(); return make_project(path, *values)


def pair(tmp_path, before=None, after=None):
    old = variants() if before is None else before
    if after is None:
        after = copy.deepcopy(old); after[0]['selection'] = {'platform': 'windows'}
    return project(tmp_path / 'before', old), project(tmp_path / 'after', after)


def test_selection_change_reports_actual_membership_with_unchanged_stored_inventory():
    values = variants(); result = compare(values, values, after_id=aid('configuration', 2)); scope = result['configuration_scope']
    assert result['changed'] and result['changes'] == []
    assert result['inventory_delta'] == {'scope': 'supplied_artifact_sets', 'added_ids': [], 'removed_ids': []}
    assert scope['added_ids'] == [aid(number=3)] and scope['removed_ids'] == [aid(number=2)]
    assert scope['retained_ids'] == sorted([aid(), aid('configuration'), aid('configuration', 2)])
    assert scope['membership_changed'] and scope['configuration_changed']
    assert result['categories'] == ['configuration_changed', 'configuration_scope_changed']


def test_stored_value_change_is_separate_from_the_resulting_membership_delta():
    old = variants(); new = copy.deepcopy(old); new[0]['selection'] = {'platform': 'windows'}
    result = compare(old, new)
    assert result['configuration_scope']['added_ids'] == [aid(number=3)]
    assert result['configuration_scope']['removed_ids'] == [aid(number=2)]
    changed = result['changes'][0]
    assert changed['artifact_id'] == aid('configuration')
    assert changed['fields'][0]['category'] == 'configuration_changed'


def test_parent_switch_uses_the_actual_effective_chain_on_each_side():
    old = variants(); old.append(configuration(3, parent=aid('configuration'), dimensions=[], selection={}))
    new = copy.deepcopy(old); new[-1]['parent'] = aid('configuration', 2)
    result = compare(old, new, aid('configuration', 3), aid('configuration', 3)); scope = result['configuration_scope']
    assert scope['before']['configuration']['effective_values'] == {'platform': 'linux'}
    assert scope['after']['configuration']['effective_values'] == {'platform': 'windows'}
    assert scope['added_ids'] == [aid(number=3)] and scope['removed_ids'] == [aid(number=2)]
    assert result['changes'][0]['fields'][0]['pointer'] == '/parent'


def test_applicability_change_has_its_own_class_without_a_configuration_change():
    old = variants(); new = copy.deepcopy(old); new[3]['applicability'] = condition('windows')
    result = compare(old, new); scope = result['configuration_scope']
    assert scope['removed_ids'] == [aid(number=2)] and scope['added_ids'] == []
    assert not scope['configuration_changed'] and scope['membership_changed']
    assert 'applicability_changed' in result['categories'] and 'configuration_scope_changed' in result['categories']
    assert 'configuration_changed' not in result['categories']


@pytest.mark.parametrize('operation', ['add_included', 'add_excluded', 'remove_excluded'])
def test_inventory_delta_is_not_mistaken_for_variant_membership(operation):
    old = variants(); new = copy.deepcopy(old)
    if operation == 'remove_excluded': new.pop()
    else: new.append(requirement(4, **({'applicability': condition('windows')} if operation == 'add_excluded' else {})))
    result = compare(old, new); scope = result['configuration_scope']
    assert scope['added_ids'] == ([aid(number=4)] if operation == 'add_included' else [])
    assert scope['removed_ids'] == []
    assert bool(result['inventory_delta']['added_ids'] or result['inventory_delta']['removed_ids'])


def test_selected_revision_change_binds_the_observation_without_inventing_membership():
    old = variants(); new = copy.deepcopy(old); new[0]['revision'] += 1
    result = compare(old, new); scope = result['configuration_scope']
    assert scope['configuration_changed'] and not scope['membership_changed']
    assert scope['added_ids'] == scope['removed_ids'] == []
    assert 'configuration_changed' in result['categories'] and 'configuration_scope_changed' not in result['categories']


def test_unchanged_explicit_variant_is_bound_but_not_a_fabricated_change():
    values = variants(); unselected = compare_semantic(model(values), model(values)).data
    selected = compare(values, values)
    assert not selected['changed'] and not unselected['changed']
    assert unselected['configuration_scope'] == {'state': 'not_evaluated'}
    assert selected['configuration_scope']['state'] == 'evaluated'
    assert selected['input_sha256'] != unselected['input_sha256']
    assert selected['evidence_currency'] == {'state': 'not_evaluated'}
    assert not selected['full_semantic_validation'] and not selected['approval_granted'] and not selected['write_authorized']


@pytest.mark.parametrize('before_id,after_id', [(None, aid('configuration')), (aid('configuration'), None)])
def test_only_a_complete_explicit_selection_pair_can_enable_variant_comparison(before_id, after_id):
    with pytest.raises(ConfigurationEvaluationError) as caught: compare(variants(), variants(), before_id, after_id)
    assert caught.value.reason == 'configuration_comparison_pair_required'


@pytest.mark.parametrize('selected', ['', 'Variant 1', aid('configuration', 99)])
def test_missing_or_ambiguous_selected_configuration_cannot_produce_a_delta(selected):
    with pytest.raises(ConfigurationEvaluationError) as caught: compare(variants(), variants(), selected, selected)
    assert caught.value.code == 'SRV130'


def test_inconsistent_variant_retains_complete_shortest_dependency_paths():
    old = [configuration(), requirement(relations=[edge('depends_on', aid(number=2))]),
        requirement(2, relations=[edge('depends_on', aid(number=3), number=2)]),
        requirement(3, applicability=condition('linux'))]
    new = copy.deepcopy(old); new[0]['selection'] = {'platform': 'windows'}
    scope = compare(old, new)['configuration_scope']
    assert scope['before']['consistent'] and not scope['after']['consistent']
    conflicts = scope['after']['inconsistent_dependencies']
    assert [(row['source_id'], row['target_id'], row['distance']) for row in conflicts] == [(aid(), aid(number=3), 2), (aid(number=2), aid(number=3), 1)]
    assert [item['id'] for item in conflicts[0]['path']['artifacts']] == [aid(), aid(number=2), aid(number=3)]


def test_configuration_comparison_is_order_independent_and_owns_its_results():
    old = variants(); new = copy.deepcopy(old); new[0]['selection'] = {'platform': 'windows'}
    before = copy.deepcopy((old, new)); first = compare(old, new); second = compare(list(reversed(old)), list(reversed(new)))
    assert first == second and (old, new) == before
    first['configuration_scope']['added_ids'].clear()
    assert compare(old, new) == second


def test_native_sources_api_cli_and_request_use_the_same_selected_scope(tmp_path):
    before, after = pair(tmp_path); selected = aid('configuration')
    sources = compare_sources(ComparisonSourceSnapshot(before), ComparisonSourceSnapshot(after),
        before_configuration_id=selected, after_configuration_id=selected)
    native = diff_project(after, str(before), against_kind='local', configuration_id=selected)
    cli = dispatch_result(['diff', '--against', str(before), '--against-kind', 'local', '--configuration', selected,
                           '--project', str(after), '--format=json'])
    request = execute_request({'command_id': 'diff', 'options': {'--against': str(before), '--against-kind': 'local',
        '--configuration': selected, '--project': str(after)}}).result
    for result in (native, cli, request):
        assert result.exit_code == 0 and result.as_dict()['result'] == sources.data
        validate_result_document('artifact-diff-v1', result.as_dict()['result'])
    assert sources.data['configuration_scope']['added_ids'] == [aid(number=3)]


def test_native_conflict_is_a_complete_failed_comparison_with_path_evidence(tmp_path):
    old = [configuration(), requirement(relations=[edge('depends_on', aid(number=2))]), requirement(2, applicability=condition('linux'))]
    before, after = pair(tmp_path, old)
    result = diff_project(after, str(before), against_kind='local', configuration_id=aid('configuration'))
    assert result.exit_code == 3 and result.complete
    assert result.result['configuration_scope']['after']['inconsistent_dependencies'][0]['target_id'] == aid(number=2)
    assert result.diagnostics[0].code == 'SRV131' and result.diagnostics[0].rule_id == 'configuration-diff-after'


def test_retained_diff_work_has_identical_configured_results(tmp_path):
    before, after = pair(tmp_path); options = {'against': str(before), 'against_kind': 'local', 'configuration_id': aid('configuration')}
    expected = diff_project(after, **options)
    with ReadCommandWork('diff', after, **options) as work:
        assert not work.advance(1) and not work.advance(1) and work.advance(1)
        assert work.result.as_dict() == expected.as_dict()


def test_retained_configured_diff_rejects_changed_sources_before_publication(tmp_path):
    before, after = pair(tmp_path)
    with ReadCommandWork('diff', after, against=str(before), against_kind='local', configuration_id=aid('configuration')) as work:
        assert not work.advance(2)
        path = after / artifact_path('configuration', aid('configuration'), 'SR')
        changed = json.loads(path.read_bytes()); changed['revision'] += 1; path.write_bytes(artifact_bytes(changed))
        assert work.advance(1) and work.result.exit_code == 6 and work.result.result is None


def test_configured_diff_performs_no_project_write_attempts(tmp_path):
    before, after = pair(tmp_path); first, second = inventory(before), inventory(after)
    with no_write_attempts():
        result = diff_project(after, str(before), against_kind='local', configuration_id=aid('configuration'))
    assert result.exit_code == 0 and inventory(before) == first and inventory(after) == second


def test_portable_cli_returns_the_actual_variant_delta(tmp_path):
    before, after = pair(tmp_path); _, package = build_distribution(tmp_path / 'distribution')
    result = run_python(['-I', '-S', '-B', str(package), 'diff', '--against', str(before), '--against-kind', 'local',
        '--configuration', aid('configuration'), '--project', str(after), '--format=json'], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['result']['configuration_scope']['added_ids'] == [aid(number=3)]
