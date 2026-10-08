"""Historical work targets, complete supplied work and unchanged hard guards."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import sys
from unittest.mock import patch

import pytest

from specroad.changes import assess_change_target, bind_plan_authoring
from specroad.changes._request_identity import request_identity
from specroad.cli.application import execute_request
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_query_page import QuerySeedPage
from specroad.graph.scope_seeds import resolve_scope_seeds
from specroad.model.canonical import canonical_json_sha256
from specroad.model.configuration import ProjectConfiguration
from specroad.model.errors import ModelError
from specroad.model.semantic_configuration import semantic_configuration
from specroad.profiles import ProfileResource, compose_profiles
from specroad.runtime.budget_policy import ResourcePolicyError, resolve_resource_policy
from specroad.srx import (EvaluationContext, SrxProgram, SrxStructureError,
                          evaluate_with_usage)
from specroad.storage.preflight_metadata import MetadataPhases
from support import run_cli
from support.folds import goal, edit
from support.model import configuration_value, configuration_file, put
from support.profiles import profile_data
from support.read_only import inventory
from support.scopes import descriptor, query, inputs
from support.srx import roots, expression_document, literal, field, binary, quantifier
from support.srx_graph import chain, graph, reach, aid
from support.targets import model, plan, POLICY, SCOPE
from test_preflight_profiles import startup_access


SOFT = ('model_bytes', 'relation_count', 'diagnostic_count', 'query_result_count',
        'srx_operations', 'srx_iterations', 'srx_graph_steps', 'import_object_count', 'merge_conflict_count')


def environment(root, **options):
    return execute_request({'command_id': 'environment.check',
        'options': {'--project': str(root), **options}}, cwd=root).result


@pytest.mark.parametrize('profile', ['constrained', 'standard'])
@pytest.mark.parametrize('state', ['clean', 'pending', 'unknown_lock'])
def test_selected_project_exposes_legacy_targets_without_model_reads_or_automatic_recovery(tmp_path, profile, state):
    declared = {**dict.fromkeys(SOFT, 1), 'json_depth': 4, 'query_default_limit': 0, 'trace_depth': 2}
    configuration_file(tmp_path, resource_limits=declared, transaction_policy={'auto_recover': True})
    put(tmp_path, 'spec/goals/broken.json', b'Model content must not be read')
    if state == 'pending':
        put(tmp_path, '.specroad/transactions/pending/journal.json', b'Never inspect or repair')
    elif state == 'unknown_lock':
        put(tmp_path, '.specroad/locks/writer.lock', b'Unknown owner')
    before = inventory(tmp_path)
    with startup_access(tmp_path):
        result = environment(tmp_path, **{'--resource-profile': profile})
    assert result.exit_code == (0 if state == 'clean' else 5)
    value = result.as_dict()['result']
    assert value['recovery_required'] is (False if state == 'clean' else True if state == 'pending' else None)
    policy = value['resource_policy']
    groups = policy['classified_limits']
    assert {k: v['value'] for k, v in groups['soft_work_target'].items()} == dict.fromkeys(SOFT, 1)
    assert groups['semantic_scope']['query_default_limit']['value'] == 0
    assert groups['hard_safety_or_format']['json_depth']['value'] == 4
    assert policy['effective_budgets']['graph']['value'] == 1
    assert policy['effective_budgets']['graph']['origin'] == 'project:resource_limits/srx_graph_steps'
    assert value['semantic_validation_performed'] is False and inventory(tmp_path) == before


@pytest.mark.parametrize('limits', [{'unknown_quantity': 1}, {'json_depth': 0}, {'srx_nodes': 0},
                                  {'model_bytes': -1}, {'srx_operations': True}])
def test_invalid_project_resource_declarations_keep_model_error_class_and_original_bytes(tmp_path, limits):
    configuration_file(tmp_path, resource_limits=limits)
    before = inventory(tmp_path)
    with startup_access(tmp_path):
        result = environment(tmp_path)
    assert result.exit_code == 3 and inventory(tmp_path) == before
    if result.result is not None:
        assert result.result['compatible'] is False
        assert result.result['resource_policy']['classified_limits']['hard_safety_or_format'] == {}


def test_changed_metadata_cannot_publish_stale_project_budget_values(tmp_path):
    configuration_file(tmp_path, resource_limits={'srx_graph_steps': 1})
    native = MetadataPhases.read_bytes
    reads = []

    def changing(ledger, boundary, path, **kwargs):
        raw = native(ledger, boundary, path, **kwargs)
        reads.append(path)
        # Root selection reads once; race the diagnosis's own capture.
        if reads.count('specroad.json') == 2:
            configuration_file(tmp_path, resource_limits={'srx_graph_steps': 99})
        return raw

    with patch.object(MetadataPhases, 'read_bytes', changing):
        result = environment(tmp_path)
    assert result.exit_code == 6
    assert json.loads((tmp_path / 'specroad.json').read_bytes())['resource_limits']['srx_graph_steps'] == 99
    if result.result is not None:
        assert result.result['resource_policy']['classified_limits']['soft_work_target'] == {}


@pytest.mark.parametrize('name', SOFT)
def test_historical_soft_quantities_change_runtime_policy_but_not_current_semantic_configuration(name):
    original = ProjectConfiguration(configuration_value())
    tiny = ProjectConfiguration(configuration_value(resource_limits={name: 1}))
    before = deepcopy(tiny.data)
    policy = resolve_resource_policy(resource_limits=tiny.data['resource_limits'])
    assert policy['classified_limits']['soft_work_target'][name] == {
        'value': 1, 'origin': 'project:resource_limits/' + name}
    assert canonical_json_sha256(semantic_configuration(tiny)) == canonical_json_sha256(semantic_configuration(original))
    assert tiny.data == before and name not in semantic_configuration(tiny)['resource_limits']


@pytest.mark.parametrize('name,value', [('json_depth', 4), ('srx_depth', 3), ('srx_nodes', 9),
    ('artifact_file_bytes', 4096), ('archive_uncompressed_bytes', 8192), ('xml_depth', 4),
    ('query_default_limit', 1), ('trace_depth', 2)])
def test_hard_and_semantic_constraints_remain_in_current_model_binding(name, value):
    original = ProjectConfiguration(configuration_value())
    selected = ProjectConfiguration(configuration_value(resource_limits={name: value}))
    assert semantic_configuration(selected)['resource_limits'][name] == value
    assert canonical_json_sha256(semantic_configuration(selected)) != canonical_json_sha256(semantic_configuration(original))


@pytest.mark.parametrize('profile', ['constrained', 'standard'])
def test_complete_supplied_target_is_valid_beyond_all_tiny_total_quantity_targets(profile):
    values = [goal(i) for i in range(32)]
    normal = model(values)
    limited = model(values, config=configuration_value(resource_limits=dict.fromkeys(SOFT, 1)))
    baseline = normal.manifest(normal.artifacts, SCOPE)
    saved = (normal.configuration_bytes, deepcopy(baseline.data))
    assert sum(len(d.content) for d in limited.documents) > 1
    policy = resolve_resource_policy({'--resource-profile': profile},
                                     resource_limits=limited.configuration.data['resource_limits'])
    assert policy['classified_limits']['soft_work_target']['model_bytes']['value'] == 1
    change = plan(limited, [edit(values[0], 'Complete requested result')])
    request = bind_plan_authoring(change)
    result = assess_change_target(change, limited, policy=POLICY)
    assert result.target_validated and result.data['checks_complete']
    assert len(result.artifacts) == 32
    assert set(result.data['validation']['source_report']['checked_ids']) == {v['id'] for v in values}
    assert result.artifacts[0]['statement'] == 'Complete requested result'
    assert result.data['binding']['base_model_root'] == baseline.sha256
    assert request_identity(bind_plan_authoring(result.plan)) == request_identity(request)
    assert (normal.configuration_bytes, baseline.data) == saved
    assert not result.data['write_authorized'] and not result.data['project_files_verified']


def test_tiny_query_result_target_does_not_repaginate_a_larger_requested_scope():
    values = [goal(i) for i in range(7)]
    supplied = inputs(*values, configuration=configuration_value(resource_limits={'query_result_count': 1}))
    scope = ScopeDescriptor(descriptor('query', {'query': query(offset=1, limit=5)}))
    page = QuerySeedPage(scope, supplied, [v['id'] for v in values[1:6]], total=7)
    for profile in ('constrained', 'standard'):
        policy = resolve_resource_policy({'--resource-profile': profile},
            resource_limits={'query_result_count': 1}, scope_descriptor=scope)
        bound = ScopeDescriptor(policy['classified_limits']['semantic_scope']['scope_descriptor']['value'])
        result = resolve_scope_seeds(bound, supplied, query_page=page)
        assert result.artifact_ids == tuple(v['id'] for v in values[1:6])
        assert page.total == 7 and bound.data['selector']['query']['limit'] == 5


@pytest.mark.parametrize('profile', ['constrained', 'standard'])
def test_large_actual_srx_evaluation_completes_above_legacy_counters_with_same_output(profile):
    document = roots({'values': list(range(1025))})
    document['project']['resource_limits'] = {'srx_operations': 1, 'srx_iterations': 1}
    program = SrxProgram(expression_document(quantifier('all', field('/values'),
        binary('gte', field('', context='item'), literal(0)))), rule_id='complete')
    context = EvaluationContext(document, rule_id='complete', resource_options={'--resource-profile': profile})
    result = evaluate_with_usage(program, context)
    assert result.value is True and result.usage.iterations == 1025
    assert result.usage.evaluation_steps == 2 + 1025 * 3
    assert result.usage.data['exceeded_targets'] == ['evaluation_steps', 'iterations']
    assert result.usage.evaluation_completed and context.data == document
    assert result.usage.data['checkpoint'] is None and not result.usage.data['resume_available']


@pytest.mark.parametrize('profile', ['constrained', 'standard'])
def test_actual_graph_keeps_all_requested_work_after_legacy_graph_target(profile):
    values = chain(); document = roots(values[0])
    document['project']['resource_limits'] = {'srx_graph_steps': 1}
    context = EvaluationContext(document, rule_id='graph', graph=graph(values),
                                resource_options={'--resource-profile': profile})
    program = SrxProgram(expression_document(reach(aid(number=3), depth=2)), rule_id='graph')
    result = evaluate_with_usage(program, context)
    assert result.value is True and result.usage.graph_steps > 1 and result.usage.evaluation_completed
    assert result.usage.policy.work.graph_steps == 1
    assert result.usage.data['exceeded_targets'] == ['graph_steps']


@pytest.mark.parametrize('profile', ['constrained', 'standard'])
def test_large_work_target_never_bypasses_current_srx_structure_recheck(profile):
    program = SrxProgram(expression_document(binary('eq', literal(1), literal(1))), rule_id='blocked')
    document = roots(); document['project']['resource_limits'] = {'srx_nodes': 2, 'srx_operations': 10**12}
    context = EvaluationContext(document, rule_id='blocked', resource_options={
        '--resource-profile': profile, '--cpu-budget-ms': 10**12, '--memory-budget-mib': 10**9})
    with patch('specroad.srx.evaluation.evaluate_expression', side_effect=AssertionError('Unsafe operator execution')):
        with pytest.raises(SrxStructureError) as error:
            evaluate_with_usage(program, context)
    assert error.value.exit_code == 3 and error.value.metric == 'ast_nodes'


def test_profile_composition_rejects_soft_quantities_in_hard_policy_and_keeps_minimum():
    from specroad.model.canonical import canonical_json_bytes
    base = ProfileResource(canonical_json_bytes(profile_data(profile_id='core', hard_limits={'srx_depth': 4})))
    extension = ProfileResource(canonical_json_bytes(profile_data(profile_id='extra', hard_limits={'srx_depth': 40})))
    effective = compose_profiles([base, extension], core_key=base.key, cli_profiles=[extension.key])
    assert effective.data['merge']['hard_limits']['srx_depth'] == 4
    for name in ('model_bytes', 'srx_operations', 'query_result_count'):
        with pytest.raises(ModelError):
            ProfileResource(canonical_json_bytes(profile_data(profile_id='unsafe', hard_limits={name: 1})))


@pytest.mark.parametrize('changes', [
    {'state': 'unknown', 'value': 123}, {'state': 'observed', 'value': None},
    {'state': 'observed', 'value': True}, {'state': 'observed', 'value': -1},
    {'state': 'observed', 'value': 1.5}, {'source': ''}, {'scope': ''}, {'unit': ''},
    {'source': '\ud800'}])
def test_invalid_host_claims_cannot_be_promoted_to_resource_capacity(changes):
    observation = {'value': None, 'unit': 'bytes', 'source': 'not_observed',
                   'state': 'unknown', 'scope': 'process_address_space_ceiling', **changes}
    original = deepcopy(observation)
    with pytest.raises(ResourcePolicyError) as error:
        resolve_resource_policy(observations={'memory_limit': observation})
    assert error.value.exit_code == 2 and observation == original


def test_unit_conversion_cannot_turn_a_usage_problem_into_unserializable_cli_success(tmp_path):
    digits = getattr(sys, 'get_int_max_str_digits', lambda: 0)()
    raw = '9' * (digits - 2 if digits else 512)
    converted = int(raw) * 1048576
    try:
        json.dumps(converted)
    except ValueError:
        expected = 2
    else:
        expected = 0
    child = run_cli(['environment', 'check', '--memory-budget-mib', raw, '--format', 'json'], tmp_path, capture=True)
    assert child.returncode == expected, child.stderr
    document = json.loads(child.stdout)
    if expected == 0:
        assert document['result']['resource_policy']['effective_budgets']['memory']['value'] == converted
    else:
        assert document['summary']['failure_kind'] == 'usage'


def test_concurrent_profile_selections_do_not_share_mutable_policy_or_context_values():
    document = roots(); original = deepcopy(document)
    program = SrxProgram(expression_document(literal(True)), rule_id='shared')

    def run(profile):
        options = {'--resource-profile': profile}
        context = EvaluationContext(document, rule_id='shared', resource_options=options)
        options['--resource-profile'] = 'unlimited'
        observed = evaluate_with_usage(program, context)
        return observed.value, context.resource_policy.work.graph_steps, context.data

    profiles = ['constrained', 'standard'] * 8
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, profiles))
    assert [r[1] for r in results] == [2000000, 10000000] * 8
    assert all(value is True and data == original for value, _, data in results)
    assert document == original
