"""Environment report contracts and actual access effects; no presentation tests."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.contracts import (CommandClass, CommandProtocol, CommandSpec,
    EffectScope, PositionalSpec, PreflightProfile)
from specroad.cli.registry import CommandRegistry
from specroad.cli.options import global_options
from specroad.model.schema_catalog import SchemaCatalog
from specroad.runtime import UnsupportedRuntimeError
from support import run_cli, run_core
from support.model import configuration_file, put
from support.read_only import inventory, no_write_attempts
from test_preflight_profiles import startup_access


def report(options=None, *, registry=None, cwd=None):
    return execute_request({'command_id': 'environment.check', 'options': options or {}},
                           registry=registry, cwd=cwd).result


def checks(value):
    return {item['check_id']: item for item in value['checks']}


@pytest.mark.parametrize('route', ['structured', 'cli', 'registry'])
def test_projectless_diagnosis_does_not_discover_broken_project(tmp_path, route):
    put(tmp_path, 'specroad.json', b'Invalid configuration must remain unselected')
    put(tmp_path, '.specroad/transactions/pending/journal.json', b'Unselected')
    before = inventory(tmp_path)
    registry = builtin_registry()
    with startup_access(tmp_path) as accesses:
        if route == 'structured':
            result = report(cwd=tmp_path)
        elif route == 'cli':
            result = dispatch_result(['environment', 'check'], cwd=tmp_path)
        else:
            result = registry.execute_result(registry.parse(['environment', 'check']), cwd=tmp_path)
    assert result.exit_code == 0 and result.project is None
    value = result.as_dict()['result']
    assert value['environment_format_version'] == '1.0.0'
    assert value['compatible'] is True and value['operation_readiness'] == 'not_requested'
    assert value['recovery_required'] is None and not value['semantic_validation_performed']
    assert value['target_command_id'] is None and value['metadata'] is None
    assert [c['check_id'] for c in value['checks']] == sorted(checks(value))
    assert checks(value)['project.metadata']['state'] == 'not_applicable'
    assert accesses == [] and inventory(tmp_path) == before
    assert registry.resolve('environment.check').preflight_for({}) is PreflightProfile.BOOTSTRAP


def test_fresh_process_reports_environment_without_project_access_or_external_processes(tmp_path):
    put(tmp_path, 'specroad.json', b'Broken')
    body = '''
import os, json
root = os.getcwd(); effects = []
def observe(event, args):
    if event in {'subprocess.Popen', 'os.system', 'os.posix_spawn', 'socket.connect', 'socket.getaddrinfo'}:
        effects.append(event); raise AssertionError('Unexpected external operation')
    if event in {'open', 'os.scandir', 'os.listdir'} and args and isinstance(args[0], (str, bytes)):
        path = os.path.abspath(os.fsdecode(args[0]))
        if path == root or path.startswith(root + os.sep):
            effects.append(event); raise AssertionError('Unexpected project access')
sys.addaudithook(observe)
from specroad.cli.application import dispatch_result
result = dispatch_result(['environment', 'check'])
assert result.exit_code == 0 and result.project is None
assert effects == []
print(json.dumps(result.as_dict()))
'''
    child = run_core(body, tmp_path, capture=True)
    assert child.returncode == 0, child.stderr
    assert json.loads(child.stdout)['result']['semantic_validation_performed'] is False
    cli = run_cli(['environment', 'check', '--format', 'json'], tmp_path, capture=True)
    assert cli.returncode == 0, cli.stderr
    assert json.loads(cli.stdout)['result']['environment_format_version'] == '1.0.0'
    assert (tmp_path / 'specroad.json').read_bytes() == b'Broken'


@pytest.mark.parametrize('state', ['clean', 'broken_model', 'pending', 'history'])
def test_explicit_project_diagnoses_metadata_without_validating_or_repairing_model(tmp_path, state):
    configuration_file(tmp_path, transaction_policy={'auto_recover': True})
    if state == 'broken_model':
        put(tmp_path, 'spec/goals/invalid.json', b'Not JSON')
        put(tmp_path, 'profiles/core.json', b'Invalid unneeded profile')
    elif state == 'pending':
        put(tmp_path, '.specroad/transactions/pending/journal.json', b'Never load this body')
    elif state == 'history':
        for name in ('.specroad/cache/broken', '.specroad/requests/broken',
                     '.specroad/transactions/receipts/broken', '.specroad/recovery/transaction-audit/broken'):
            put(tmp_path, name, b'Historical data outside diagnosis')
    before = inventory(tmp_path)
    with startup_access(tmp_path):
        result = report({'--project': str(tmp_path)})
    assert result.exit_code == (5 if state == 'pending' else 0)
    assert result.complete
    value = result.as_dict()['result']
    assert value['compatible'] is (state != 'pending')
    assert value['recovery_required'] is (state == 'pending')
    assert value['semantic_validation_performed'] is False
    assert checks(value)['project.metadata']['state'] == 'passed'
    assert checks(value)['project.operational']['state'] == ('failed' if state == 'pending' else 'passed')
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('selector', ['fixture.target', 'fixture target', 'target-alias'])
def test_for_command_resolves_registered_aliases_without_executing_target(tmp_path, selector):
    calls = []
    target = replace(builtin_registry().resolve('version'), command_id='fixture.target',
        words=('fixture', 'target'), aliases=(('target-alias',),),
        handler=lambda i: calls.append(i) or 0,
        protocol=CommandProtocol('fixture-v1', {'command_id': 'fixture.target'}))
    registry = CommandRegistry((*builtin_registry().commands, target))
    with startup_access(tmp_path) as accesses:
        result = report({'--for-command': selector}, registry=registry, cwd=tmp_path)
    assert result.exit_code == 0 and result.result['compatible'] is True
    assert result.result['operation_readiness'] == 'ready'
    assert result.result['target_command_id'] == 'fixture.target'
    assert calls == [] and accesses == []


@pytest.mark.parametrize('selected', [False, True])
def test_missing_target_project_and_arguments_remain_unknown(tmp_path, selected):
    configuration_file(tmp_path)
    calls = []
    target = CommandSpec('fixture.model', ('fixture', 'model'), CommandClass.READ_ONLY,
        PreflightProfile.PROJECT_READ, EffectScope.NONE, lambda i: calls.append(i) or 0,
        options=global_options('--project'), positionals=(PositionalSpec('input'),), requires_project=True,
        protocol=CommandProtocol('fixture-v1', {'command_id': 'fixture.model',
                                               'arguments': {'input': 'not-supplied'}}))
    registry = CommandRegistry((*builtin_registry().commands, target))
    options = {'--for-command': 'fixture.model', **({'--project': str(tmp_path)} if selected else {})}
    with startup_access(tmp_path) as accesses:
        result = report(options, registry=registry, cwd=tmp_path)
    assert result.exit_code == 0 and result.result['compatible'] is None
    assert result.result['operation_readiness'] == 'unknown' and calls == []
    observed = checks(result.result)
    assert observed['command.project']['state'] == ('passed' if selected else 'unknown')
    assert observed['command.arguments']['state'] == 'unknown'
    if not selected:
        assert accesses == [] and result.project is None


@pytest.mark.parametrize('prerequisite', ['git', 'write', 'root_creation'])
def test_target_prerequisites_are_not_probed_or_assumed_available(tmp_path, prerequisite):
    calls = []
    target = CommandSpec('fixture.target', ('fixture', 'target'),
        CommandClass.ROOT_CREATION if prerequisite == 'root_creation' else CommandClass.READ_ONLY,
        PreflightProfile.ROOT_CREATION if prerequisite == 'root_creation' else PreflightProfile.INPUT_READ,
        EffectScope.NEW_ROOT if prerequisite == 'root_creation' else
        EffectScope.EXTERNAL_OUTPUT if prerequisite == 'write' else EffectScope.NONE,
        lambda i: calls.append(i) or 0, requires_git=prerequisite == 'git',
        protocol=CommandProtocol('fixture-v1', {'command_id': 'fixture.target'}))
    registry = CommandRegistry((*builtin_registry().commands, target))
    with startup_access(tmp_path) as accesses:
        result = report({'--for-command': 'fixture.target'}, registry=registry, cwd=tmp_path)
    assert result.exit_code == 0 and result.result['compatible'] is None
    assert result.result['operation_readiness'] == 'unknown'
    assert checks(result.result)['command.git' if prerequisite == 'git' else 'command.write_paths']['state'] == 'unknown'
    assert accesses == [] and calls == [] and list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('kind,code', [('syntax', 3), ('schema', 3), ('execution', 7)])
def test_invalid_configuration_keeps_model_and_safety_failure_classes(tmp_path, kind, code):
    configuration_file(tmp_path, **({'schema_version': '99.0.0'} if kind == 'schema' else {}))
    if kind == 'syntax':
        (tmp_path / 'specroad.json').write_bytes(b'Broken')
    elif kind == 'execution':
        value = json.loads((tmp_path / 'specroad.json').read_bytes())
        value['hooks'] = {'run': 'not-allowed'}
        (tmp_path / 'specroad.json').write_text(json.dumps(value))
    before = inventory(tmp_path)
    with startup_access(tmp_path):
        result = report({'--project': str(tmp_path)})
    assert result.exit_code == code
    assert not result.details['preflight']['normal_operation_started']
    assert inventory(tmp_path) == before


def test_unavailable_optional_resource_api_keeps_quotas_unknown_and_diagnosis_complete(tmp_path):
    with patch('specroad.runtime.limits._resource_api', return_value=None), startup_access(tmp_path):
        result = report({'--for-command': 'version'}, cwd=tmp_path)
    assert result.exit_code == 0 and result.result['compatible'] is True
    assert result.result['operation_readiness'] == 'ready'
    assert all(v['value'] is None and v['state'] == 'unknown' for v in result.result['observations'].values())
    assert all(not c['required'] for c in result.result['checks'] if c['check_id'].startswith('resources.'))


def test_observed_address_space_limit_is_qualified_and_never_claims_available_memory(tmp_path):
    api = SimpleNamespace(RLIMIT_AS=1, RLIMIT_CPU=2, RLIM_INFINITY=-1,
                          getrlimit=lambda resource: (123456789, 234567890) if resource == 1 else (-1, -1))
    with patch('specroad.runtime.limits._resource_api', return_value=api), startup_access(tmp_path):
        result = report(cwd=tmp_path)
    assert result.exit_code == 0
    assert dict(result.result['observations']['memory_limit']) == {
        'value': 123456789, 'unit': 'bytes', 'source': 'getrlimit.RLIMIT_AS',
        'state': 'observed', 'scope': 'process_address_space_ceiling'}
    assert result.result['observations']['cpu_capacity']['state'] == 'unknown'
    assert result.result['observations']['storage_capacity']['state'] == 'unknown'


@pytest.mark.parametrize('selected', [None, 'constrained', 'standard'])
def test_resource_profile_reports_declared_targets_with_origin_without_claiming_engine(tmp_path, selected):
    with startup_access(tmp_path):
        result = report({} if selected is None else {'--resource-profile': selected}, cwd=tmp_path)
    assert result.exit_code == 0
    policy = result.result['resource_policy']
    profile = selected or 'constrained'
    assert policy['policy_version'] == 'runtime-budget-v2' and policy['profile'] == profile
    assert policy['profile_source'] == ('default' if selected is None else 'cli')
    assert policy['budget_engine_available'] is False and policy['scope'] == 'declared_soft_work_targets'
    budgets = policy['effective_budgets']
    assert budgets['cpu']['value'] == (120000 if profile == 'standard' else 30000)
    assert budgets['memory']['value'] == (1024 if profile == 'standard' else 256) * 1024**2
    assert budgets['io_transfer']['value'] == 65536
    assert all(v['origin'] == 'profile:' + profile and v['limit_class'] == 'soft_work_target' for v in budgets.values())


@pytest.mark.parametrize('arguments', [
    ['--resource-profile', 'unlimited'], ['--for-command', 'unavailable'],
    ['--work-dir', 'not-created'], ['--format', 'sarif'], ['extra']])
def test_invalid_environment_requests_are_usage_failures_without_side_effects(tmp_path, arguments):
    with startup_access(tmp_path):
        result = dispatch_result(['environment', 'check', *arguments], cwd=tmp_path)
    assert result.exit_code == 2 and list(tmp_path.iterdir()) == []


def test_environment_contract_is_described_retrievable_and_validates_actual_report(tmp_path):
    registry = builtin_registry()
    described = dispatch_result(['command', 'describe', 'environment.check']).as_dict()['result']
    assert described['command_class'] == 'read_only' and described['requires_project'] is False
    assert described['stdout']['result_schema'] == 'environment-v1'
    assert set(described['stdout']['formats']) == {'pretty', 'json'}
    assert described['write_effects']['scope'] == 'none'
    assert {p['flag'] for p in described['options']} >= {'--project', '--for-command', '--resource-profile'}
    result = execute_request(described['examples'][0], cwd=tmp_path).result
    assert result.exit_code == 0
    catalog = SchemaCatalog(registry)
    catalog.validate('environment-v1', result.as_dict()['result'])
    assert catalog.show('environment-v1')['schema']['properties']['semantic_validation_performed']['const'] is False
    assert 'cli.environment.check' in dispatch_result(['capabilities']).result['semantic']['capability_ids']


def test_bad_distribution_record_is_an_explicit_blocker_with_complete_report(tmp_path):
    with patch('specroad._build.BUILD_METADATA', {'format_version': 999}), startup_access(tmp_path):
        result = report({'--for-command': 'version'}, cwd=tmp_path)
    assert result.exit_code == 5 and result.complete
    assert result.result['compatible'] is False and result.result['operation_readiness'] == 'blocked'
    assert checks(result.result)['distribution.metadata']['state'] == 'failed'
    assert result.result['distribution']['build_id'] is None


def test_runtime_failure_in_diagnostic_phase_retains_complete_machine_report(tmp_path):
    with patch('specroad.runtime.environment.check_runtime', side_effect=UnsupportedRuntimeError()), startup_access(tmp_path):
        result = report({'--for-command': 'version'}, cwd=tmp_path)
    assert result.exit_code == 5 and result.complete
    assert result.result['python']['supported'] is False and result.result['compatible'] is False
    assert checks(result.result)['runtime.python']['reason'] == 'unsupported_runtime'
