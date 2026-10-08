"""Resolved resource policy and actual consumers; no timing or UI oracles."""
from copy import deepcopy
import json
from unittest.mock import patch

import pytest

from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.commands import builtin_registry
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_query_page import QuerySeedPage
from specroad.graph.scope_seeds import resolve_scope_seeds
from specroad.model.canonical import canonical_json_sha256
from specroad.model.configuration import ProjectConfiguration
from specroad.model.semantic_configuration import semantic_configuration
from specroad.model.schema_catalog import SchemaCatalog
from specroad.runtime.budget_policy import ResourcePolicyError, resolve_resource_policy
from specroad.srx import EvaluationContext, SrxProgram, SrxStructureError, evaluate_with_usage
from specroad.srx.resources import WorkMeter
from specroad.srx.resource_observations import StructureObservation
from specroad.changes import bind_plan_authoring
from specroad.changes._request_identity import request_identity
from support import run_cli
from support.folds import goal, edit
from support.model import configuration_value
from support.scopes import descriptor, query, inputs
from support.srx import roots, expression_document, literal, binary
from support.srx_graph import chain, graph, reach, aid
from support.targets import model, plan
from test_preflight_profiles import startup_access


OVERRIDES = [
    ('--cpu-budget-ms', 'cpu', 1), ('--wall-budget-ms', 'wall', 1),
    ('--memory-budget-mib', 'memory', 1048576), ('--scratch-budget-mib', 'scratch', 1048576),
    ('--step-cpu-ms', 'step_cpu', 1), ('--step-wall-ms', 'step_wall', 1),
]


def environment(options, root):
    return execute_request({'command_id': 'environment.check', 'options': options}, cwd=root).result


@pytest.mark.parametrize('profile', [None, 'constrained', 'standard'])
def test_all_profile_defaults_are_used_by_the_environment_contract(tmp_path, profile):
    options = {} if profile is None else {'--resource-profile': profile}
    with startup_access(tmp_path) as accesses:
        result = environment(options, tmp_path)
    assert result.exit_code == 0 and accesses == []
    value = result.as_dict()['result']['resource_policy']
    expected = ([30000, 60000, 268435456, 536870912, 2000000, 4096, 16777216,
                 33554432, 65536, 5000, 10000] if profile != 'standard' else
                [120000, 300000, 1073741824, 4294967296, 10000000, 16384, 67108864,
                 134217728, 65536, 30000, 60000])
    metrics = ['cpu', 'wall', 'memory', 'scratch', 'graph', 'relationship_paths',
               'inline_stdout', 'persistent_cache_read', 'io_transfer', 'step_cpu', 'step_wall']
    assert {k: v['value'] for k, v in value['effective_budgets'].items()} == dict(zip(metrics, expected))
    assert value['profile'] == (profile or 'constrained')
    assert value['profile_source'] == ('default' if profile is None else 'cli')
    assert value['budget_engine_available'] is False
    assert all(b['limit_class'] == 'soft_work_target' for b in value['effective_budgets'].values())
    SchemaCatalog(builtin_registry()).validate('environment-v1', result.as_dict()['result'])


@pytest.mark.parametrize('flag,metric,factor', OVERRIDES)
def test_explicit_target_overrides_one_value_and_reports_its_origin(tmp_path, flag, metric, factor):
    result = environment({'--resource-profile': 'standard', flag: '7'}, tmp_path)
    assert result.exit_code == 0
    current = result.as_dict()['result']['resource_policy']['effective_budgets']
    baseline = resolve_resource_policy({'--resource-profile': 'standard'})['effective_budgets']
    assert current[metric]['value'] == 7 * factor
    assert current[metric]['origin'] == 'cli:' + flag
    assert current[metric]['unit'] == ('bytes' if factor > 1 else 'ms')
    assert current[metric]['limit_class'] == 'soft_work_target'
    assert {k: v for k, v in current.items() if k != metric} == {k: v for k, v in baseline.items() if k != metric}


@pytest.mark.parametrize('route', ['cli', 'structured', 'registry'])
def test_all_overrides_reach_the_same_real_command(tmp_path, route):
    options = {flag: str(i + 1) for i, (flag, _, _) in enumerate(OVERRIDES)}
    arguments = ['environment', 'check', '--format', 'json',
                 *[part for pair in options.items() for part in pair]]
    if route == 'cli':
        child = run_cli(arguments, tmp_path, capture=True)
        assert child.returncode == 0, child.stderr
        value = json.loads(child.stdout)['result']
    elif route == 'structured':
        result = environment(options, tmp_path)
        assert result.exit_code == 0
        value = result.as_dict()['result']
    else:
        registry = builtin_registry()
        result = registry.execute_result(registry.parse(arguments), cwd=tmp_path)
        assert result.exit_code == 0
        value = result.as_dict()['result']
    assert value['resource_policy']['effective_budgets']['cpu']['value'] == 1
    assert value['resource_policy']['effective_budgets']['memory']['value'] == 3 * 1048576
    assert value['resource_policy']['effective_budgets']['step_wall']['value'] == 6
    assert value['semantic_validation_performed'] is False and list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('flag,metric,factor', OVERRIDES)
@pytest.mark.parametrize('invalid', ['0', '-1', 'unlimited'])
def test_nonpositive_or_unlimited_cli_targets_are_usage_errors(tmp_path, flag, metric, factor, invalid):
    with startup_access(tmp_path) as accesses:
        result = dispatch_result(['environment', 'check', flag, invalid], cwd=tmp_path)
    assert result.exit_code == 2 and accesses == [] and list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('value', [0, -1, True, 1.5, None, '1.5', ' 1', []])
def test_embedded_invalid_targets_cannot_silently_disable_budget_policy(value):
    with pytest.raises(ResourcePolicyError) as error:
        resolve_resource_policy({'--cpu-budget-ms': value})
    assert error.value.exit_code == 2


def test_explicit_step_windows_can_exceed_parent_targets_without_clamping():
    policy = resolve_resource_policy({'--cpu-budget-ms': 1, '--wall-budget-ms': 2,
                                      '--step-cpu-ms': 9000, '--step-wall-ms': 18000})
    values = policy['effective_budgets']
    assert [values[k]['value'] for k in ('cpu', 'wall', 'step_cpu', 'step_wall')] == [1, 2, 9000, 18000]
    assert values['step_cpu']['origin'] == 'cli:--step-cpu-ms'


def test_command_describes_resolved_policy_without_inventing_a_work_engine():
    result = dispatch_result(['command', 'describe', 'environment.check'])
    assert result.exit_code == 0
    value = result.as_dict()['result']
    assert value['budget_policy_version'] == 'runtime-budget-v2'
    assert {flag for flag, _, _ in OVERRIDES} <= {item['flag'] for item in value['options']}
    assert value['work']['continuation_supported'] is False
    assert value['work']['checkpoint_algorithms'] == [] and 8 not in value['exit_codes']
    capabilities = dispatch_result(['capabilities']).as_dict()['result']['semantic']['work']
    assert capabilities['engine_available'] is False and capabilities['checkpoint_algorithms'] == []


def test_declared_limits_have_distinct_semantic_safety_and_work_classes():
    limits = {'model_bytes': 1, 'relation_count': 2, 'diagnostic_count': 3, 'query_result_count': 4,
              'srx_operations': 5, 'srx_iterations': 6, 'srx_graph_steps': 7, 'import_object_count': 8,
              'merge_conflict_count': 9, 'query_default_limit': 0, 'trace_depth': 0,
              'artifact_file_bytes': 11, 'json_depth': 12, 'xml_depth': 13, 'srx_depth': 14,
              'srx_nodes': 15, 'archive_uncompressed_bytes': 16}
    value = resolve_resource_policy(resource_limits=limits)
    groups = value['classified_limits']
    assert set(groups['soft_work_target']) == {'model_bytes', 'relation_count', 'diagnostic_count',
        'query_result_count', 'srx_operations', 'srx_iterations', 'srx_graph_steps',
        'import_object_count', 'merge_conflict_count'}
    assert set(groups['semantic_scope']) == {'query_default_limit', 'trace_depth'}
    assert set(groups['hard_safety_or_format']) == {'artifact_file_bytes', 'json_depth', 'xml_depth',
        'srx_depth', 'srx_nodes', 'archive_uncompressed_bytes'}
    assert groups['observed_host_limit'] == {}
    assert {name: entry['value'] for group in groups.values() for name, entry in group.items()} == limits
    assert value['effective_budgets']['graph']['value'] == 7
    assert value['effective_budgets']['graph']['origin'] == 'project:resource_limits/srx_graph_steps'


@pytest.mark.parametrize('bad', [
    {'--json-depth': '999'}, {'--network': True}, {'--workers': '8'},
    {'--resource-profile': 'unlimited'}, {'--resource-profile': None}])
def test_runtime_options_cannot_relax_safety_or_activate_workers(bad):
    with pytest.raises(ResourcePolicyError):
        resolve_resource_policy(bad)


@pytest.mark.parametrize('limits', [{'future_limit': 1}, {'json_depth': 0}, {'srx_nodes': True}])
def test_unclassified_or_invalid_hard_limits_are_rejected(limits):
    with pytest.raises(ResourcePolicyError):
        resolve_resource_policy(resource_limits=limits)


@pytest.mark.parametrize('profile', ['constrained', 'standard'])
def test_unknown_host_quotas_remain_unknown_even_with_large_declared_targets(tmp_path, profile):
    with patch('specroad.runtime.limits._resource_api', return_value=None):
        result = environment({'--resource-profile': profile, '--memory-budget-mib': '1000000'}, tmp_path)
    assert result.exit_code == 0 and result.result['compatible'] is True
    observed = result.as_dict()['result']['resource_policy']['classified_limits']['observed_host_limit']
    assert len(observed) == 3
    assert all(v['state'] == 'unknown' and v['value'] is None for v in observed.values())
    assert result.result['resource_policy']['effective_budgets']['memory']['value'] == 1000000 * 1048576


def test_known_host_ceiling_is_separate_from_soft_target_and_never_raised():
    observation = {'value': 4, 'unit': 'bytes', 'source': 'getrlimit.RLIMIT_AS',
                   'state': 'observed', 'scope': 'process_address_space_ceiling'}
    policy = resolve_resource_policy({'--memory-budget-mib': 1000}, observations={'memory_limit': observation})
    assert policy['effective_budgets']['memory']['value'] == 1000 * 1048576
    assert policy['classified_limits']['observed_host_limit']['memory_limit'] == observation


def test_profile_changes_srx_work_policy_without_changing_fach_scope_or_operations():
    original = goal(1)
    current_model = model([original])
    change = plan(current_model, [edit(original, 'Unchanged full requested edit')])
    request = bind_plan_authoring(change)
    identity = request_identity(request)
    scope = ScopeDescriptor(change.data['base']['scope_descriptor'])
    config = ProjectConfiguration(configuration_value(resource_limits={'json_depth': 30, 'trace_depth': 9}))
    semantic_hash = canonical_json_sha256(semantic_configuration(config))
    saved = (change.source_bytes, request.data, scope.canonical_bytes, config.data)
    policies = []
    for profile in ('constrained', 'standard'):
        options = {'--resource-profile': profile, '--cpu-budget-ms': 1, '--step-cpu-ms': 500000}
        policy = resolve_resource_policy(options, resource_limits=config.data['resource_limits'], scope_descriptor=scope)
        assert policy['classified_limits']['semantic_scope']['scope_descriptor']['sha256'] == scope.sha256
        assert policy['classified_limits']['hard_safety_or_format']['json_depth']['value'] == 30
        context = EvaluationContext(roots(), rule_id='profile', resource_options=options)
        policies.append(context.resource_policy)
        assert evaluate_with_usage(SrxProgram(expression_document(literal(True)), rule_id='profile'), context).value is True
        assert request_identity(bind_plan_authoring(change)) == identity
        assert canonical_json_sha256(semantic_configuration(config)) == semantic_hash
        assert (change.source_bytes, request.data, scope.canonical_bytes, config.data) == saved
    assert [p.work.graph_steps for p in policies] == [2000000, 10000000]
    assert policies[0].structure == policies[1].structure


@pytest.mark.parametrize('profile,exceeded', [('constrained', True), ('standard', False)])
def test_resolved_profile_selects_the_real_meter_threshold(profile, exceeded):
    context = EvaluationContext(roots(), rule_id='meter', resource_options={'--resource-profile': profile})
    # Explicit count fixture exercises the real accumulator, not a claimed timed graph benchmark.
    meter = WorkMeter(context.resource_policy, StructureObservation(1, 1))
    meter.add('graph_steps', 2000001)
    observation = meter.observation(True)
    assert observation.graph_steps == 2000001 and observation.evaluation_completed is True
    assert observation.data['soft_budget_exceeded'] is exceeded


@pytest.mark.parametrize('limit', [0, 1])
def test_query_pagination_and_bound_page_survive_resource_profile_switch(limit):
    values = chain()
    scope = ScopeDescriptor(descriptor('query', {'query': query(offset=1, limit=limit)}))
    supplied = inputs(*values)
    page = QuerySeedPage(scope, supplied, [] if limit == 0 else [aid(number=2)], total=3)
    expected = resolve_scope_seeds(scope, supplied, query_page=page)
    for profile in ('constrained', 'standard'):
        policy = resolve_resource_policy({'--resource-profile': profile}, scope_descriptor=scope)
        bound = policy['classified_limits']['semantic_scope']['scope_descriptor']
        restored = ScopeDescriptor(bound['value'])
        assert restored.sha256 == scope.sha256
        assert restored.data['selector']['query']['offset'] == 1
        assert restored.data['selector']['query']['limit'] == limit
        assert resolve_scope_seeds(restored, supplied, query_page=page) == expected
        assert page.total == 3


@pytest.mark.parametrize('profile', ['constrained', 'standard'])
@pytest.mark.parametrize('depth,expected', [(1, False), (2, True)])
def test_actual_srx_graph_evaluation_keeps_semantic_depth(profile, depth, expected):
    values = chain()
    document = roots(values[0])
    context = EvaluationContext(document, rule_id='depth', graph=graph(values),
                                resource_options={'--resource-profile': profile})
    program = SrxProgram(expression_document(reach(aid(number=3), depth=depth)), rule_id='depth')
    result = evaluate_with_usage(program, context)
    assert result.value is expected and result.usage.evaluation_completed
    assert context.data == document
    assert context.resource_policy.work.graph_steps == (2000000 if profile == 'constrained' else 10000000)


@pytest.mark.parametrize('profile', ['constrained', 'standard'])
def test_profile_preserves_hard_structure_and_soft_excess_does_not_end_valid_evaluation(profile):
    program = SrxProgram(expression_document(binary('eq', literal(1), literal(1))), rule_id='boundary')
    data = roots()
    data['project']['resource_limits'] = {'srx_nodes': 3, 'srx_depth': 2, 'srx_operations': 1}
    options = {'--resource-profile': profile, '--memory-budget-mib': 1000000}
    result = evaluate_with_usage(program, EvaluationContext(data, rule_id='boundary', resource_options=options))
    assert result.value is True and result.usage.evaluation_steps == 3
    assert result.usage.data['soft_budget_exceeded'] and result.usage.evaluation_completed
    assert result.usage.data['checkpoint'] is None and result.usage.data['resume_available'] is False
    data['project']['resource_limits']['srx_nodes'] = 2
    with pytest.raises(SrxStructureError) as error:
        evaluate_with_usage(program, EvaluationContext(data, rule_id='boundary', resource_options=options))
    assert error.value.metric == 'ast_nodes' and error.value.limit == 2 and error.value.exit_code == 3


def test_resolved_values_own_their_inputs_and_do_not_write_back_budget_options():
    limits = {'srx_graph_steps': 1, 'json_depth': 4}
    scope = ScopeDescriptor(descriptor())
    options = {'--resource-profile': 'standard', '--cpu-budget-ms': 5}
    original = deepcopy((limits, options))
    first = resolve_resource_policy(options, resource_limits=limits, scope_descriptor=scope)
    first['effective_budgets']['cpu']['value'] = 99
    first['classified_limits']['semantic_scope']['scope_descriptor']['value']['selector']['foreign'] = True
    second = resolve_resource_policy(options, resource_limits=limits, scope_descriptor=scope)
    assert second['effective_budgets']['cpu']['value'] == 5
    assert second['classified_limits']['semantic_scope']['scope_descriptor']['value'] == descriptor()
    assert (limits, options) == original
