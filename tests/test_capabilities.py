"""Actual capability data and side effects; no presentation or doc oracles."""

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.capabilities import capabilities
from specroad.cli.commands import builtin_registry
from specroad.cli.contracts import CommandProtocol
from specroad.cli.registry import CommandRegistry
from specroad.cli.results import CommandResult
from support import run_cli, run_core


class CapabilitiesWorkTests(unittest.TestCase):
    def test_capabilities_match_actual_registered_handlers_and_descriptions(self):
        registry = builtin_registry(); document = capabilities(registry); semantic = document['semantic']
        ids = {command.command_id for command in registry.commands}
        self.assertEqual({item['command_id'] for item in semantic['commands']}, ids)
        self.assertEqual(set(semantic['capability_ids']), {'cli.' + item for item in ids} |
                         {'python.structured-request', 'python.srx.evaluate'})
        self.assertEqual(set(semantic['command_groups']), {item.split('.')[0] for item in ids})
        self.assertEqual(semantic['command_classes'], ['read_only', 'root_creation'])
        for item in semantic['commands']:
            result = dispatch_result(['command', 'describe', item['command_id']], registry=registry)
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(list(result.result['stdout']['formats']), item['output_formats'])

    def test_unimplemented_formats_versions_and_engines_are_not_advertised(self):
        semantic = capabilities(builtin_registry())['semantic']
        self.assertEqual(semantic['output_formats'], ['json', 'pretty'])
        self.assertNotIn('sarif', semantic['output_formats'])
        self.assertEqual(semantic['exchange_formats'], [])
        self.assertEqual(semantic['supported_versions']['schema'], ['0.2.0'])
        self.assertEqual(semantic['supported_versions']['srx'], ['1.0'])
        self.assertEqual(semantic['supported_versions']['proposal'], [])
        self.assertFalse(semantic['work']['engine_available'])
        self.assertEqual(semantic['work']['checkpoint_algorithms'], [])
        self.assertIsNone(semantic['work']['budget_policy_version'])

    def test_advertised_model_versions_match_retrievable_schema_contracts(self):
        outcomes = [dispatch_result(argv) for argv in (
            ['version', '--format=json'], ['capabilities', '--format=json'],
            ['schema', 'list', '--format=json'])]
        for outcome in outcomes:
            self.assertEqual(outcome.exit_code, 0)
        identity, available, catalog = [outcome.as_dict()['result'] for outcome in outcomes]
        versions = available['semantic']['supported_versions']['schema']
        self.assertEqual(versions, ['0.2.0'])
        self.assertEqual(identity['supported_schema_versions'], versions)
        model_rows = [row for row in catalog['schemas']
                      if row['category'] in ('artifact', 'configuration')]
        self.assertEqual({row['category'] for row in model_rows},
                         {'artifact', 'configuration'})
        self.assertEqual(sorted({row['version'] for row in model_rows}), versions)
        for row in model_rows:
            with self.subTest(schema_id=row['schema_id']):
                result = dispatch_result(['schema', 'show', row['schema_id'], '--format=json'])
                self.assertEqual(result.exit_code, 0)
                schema = result.as_dict()['result']['schema']
                self.assertEqual(schema['properties']['schema_version']['const'], row['version'])

    def test_actual_cli_json_and_python_entry_deliver_the_same_semantics(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli(['capabilities', '--format', 'json'], tmp, capture=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            envelope = json.loads(result.stdout)
            response = execute_request({'command_id': 'capabilities', 'options': {'--format': 'json'}}).result
            self.assertEqual(envelope['result']['semantic'], response.as_dict()['result']['semantic'])
            self.assertIsNone(envelope['project'])
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_adding_a_real_handler_changes_capabilities_without_executing_it(self):
        calls = []; original = builtin_registry()
        extra = replace(original.resolve('version'), command_id='fixture.ready', words=('fixture', 'ready'),
            handler=lambda i: calls.append(i) or CommandResult(i.command.command_id),
            protocol=CommandProtocol('fixture-ready-v1', {'command_id': 'fixture.ready'}))
        registry = CommandRegistry((*original.commands, extra))
        self.assertIn('cli.fixture.ready', capabilities(registry)['semantic']['capability_ids'])
        self.assertNotIn('cli.fixture.ready', capabilities(original)['semantic']['capability_ids'])
        self.assertEqual(calls, [])
        self.assertEqual(dispatch_result(['fixture', 'ready'], registry=registry).exit_code, 0)
        self.assertEqual(len(calls), 1)

    def test_returned_data_cannot_mutate_next_capability_query(self):
        registry = builtin_registry(); first = capabilities(registry); original = capabilities(registry)
        first['semantic']['commands'].clear(); first['semantic']['supported_versions']['schema'].append('fake')
        first['semantic']['supported_versions']['srx'].clear()
        first['semantic']['capability_ids'].clear()
        first['runtime']['interpreter']['python_version'] = 'fake'
        self.assertEqual(capabilities(registry), original)

    def test_display_options_do_not_change_semantic_capabilities(self):
        documents = [dispatch_result(argv).as_dict()['result']['semantic'] for argv in (
            ['capabilities'], ['capabilities', '--format=json'],
            ['capabilities', '--quiet', '--no-color'])]
        self.assertEqual(documents[0], documents[1]); self.assertEqual(documents[1], documents[2])

    def test_bad_distribution_identity_is_environment_failure_not_fake_version(self):
        with patch('specroad._build.BUILD_METADATA', {'format_version': 999}):
            result = dispatch_result(['capabilities'])
            self.assertEqual(result.exit_code, 5)
            self.assertIsNone(result.result)
        self.assertEqual(dispatch_result(['capabilities']).exit_code, 0)

    def test_project_and_work_options_do_not_activate_unimplemented_operations(self):
        with tempfile.TemporaryDirectory() as tmp:
            for suffix in (['--project', tmp], ['--work-dir', tmp], ['--format', 'sarif'], ['extra']):
                self.assertEqual(dispatch_result(['capabilities', *suffix], cwd=tmp).exit_code, 2)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_unknown_host_limits_are_not_reported_as_zero_or_capacity(self):
        runtime = capabilities(builtin_registry())['runtime']
        self.assertIn('interpreter', runtime)
        self.assertIsNone(runtime['limits']['host_memory_bytes'])
        self.assertIsNone(runtime['limits']['host_cpu_quota'])
        semantic = capabilities(builtin_registry())['semantic']
        self.assertNotIn('limits', semantic)
        self.assertEqual(semantic['python_support']['verification_status'], 'unrecorded')
        self.assertEqual(semantic['python_support']['fully_verified_minors'], [])

    def test_bootstrap_does_not_scan_or_write_project_or_start_external_code(self):
        body = '''
import os
root = os.getcwd(); effects = []
def observe(event, args):
    if event in {'subprocess.Popen', 'os.system', 'os.posix_spawn', 'socket.connect', 'socket.getaddrinfo', 'builtins.input'}:
        effects.append(event); raise AssertionError('unexpected external operation')
    if event in {'open', 'os.scandir', 'os.listdir'} and args and isinstance(args[0], (str, bytes)):
        path = os.path.abspath(os.fsdecode(args[0]))
        if path == root or path.startswith(root + os.sep):
            effects.append(event); raise AssertionError('unexpected project access')
sys.addaudithook(observe)
from specroad.cli.application import dispatch_result
result = dispatch_result(['capabilities', '--format=json'])
assert result.exit_code == 0 and result.project is None
assert not effects
assert 'specroad.cli.project_selection' not in sys.modules
assert 'specroad.cli.presentation' not in sys.modules
assert 'py3langid' not in sys.modules
'''
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'specroad.json').write_bytes(b'broken metadata')
            (root / 'model').mkdir(); (root / 'model/item').write_bytes(b'untouched')
            result = run_core(body, root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / 'model/item').read_bytes(), b'untouched')


class CapabilitiesRobustnessTests(unittest.TestCase):
    @staticmethod
    def resource_api(address=(1024, 2048), cpu=(10, 20)):
        from types import SimpleNamespace
        return SimpleNamespace(RLIMIT_AS=1, RLIMIT_CPU=2, RLIM_INFINITY=-1,
                               getrlimit=lambda kind: address if kind == 1 else cpu)

    def test_known_process_limits_are_reported_with_units_and_scope(self):
        from specroad.runtime.limits import current_limits
        with patch('specroad.runtime.limits._resource_api', return_value=self.resource_api()):
            result = current_limits()
        self.assertEqual(result['process_address_space_bytes']['soft'], {'state': 'known', 'value': 1024})
        self.assertEqual(result['process_address_space_bytes']['hard'], {'state': 'known', 'value': 2048})
        self.assertEqual(result['process_address_space_bytes']['unit'], 'bytes')
        self.assertEqual(result['process_cpu_seconds']['soft'], {'state': 'known', 'value': 10})
        self.assertEqual(result['process_cpu_seconds']['scope'], 'process')
        self.assertIsNone(result['host_memory_bytes'])
        self.assertIsNone(result['host_cpu_quota'])

    def test_unlimited_process_limit_does_not_imply_unlimited_host_capacity(self):
        from specroad.runtime.limits import current_limits
        with patch('specroad.runtime.limits._resource_api', return_value=self.resource_api((-1, -1), (10, -1))):
            result = current_limits()
        self.assertEqual(result['process_address_space_bytes']['soft'], {'state': 'unlimited', 'value': None})
        self.assertEqual(result['process_cpu_seconds']['soft']['value'], 10)
        self.assertEqual(result['process_cpu_seconds']['hard']['state'], 'unlimited')
        self.assertEqual(result['host_limits_status'], 'unknown')
        self.assertIsNone(result['host_memory_bytes'])

    def test_missing_or_failing_limit_facilities_remain_unknown(self):
        from specroad.runtime.limits import current_limits
        from types import SimpleNamespace
        def denied(kind):
            raise OSError('fixture failure')
        failing = SimpleNamespace(RLIMIT_AS=1, RLIMIT_CPU=2, RLIM_INFINITY=-1, getrlimit=denied)
        for api in (None, object(), failing):
            with patch('specroad.runtime.limits._resource_api', return_value=api):
                result = current_limits()
            for key in ('process_address_space_bytes', 'process_cpu_seconds'):
                self.assertEqual(result[key]['soft'], {'state': 'unknown', 'value': None})
                self.assertEqual(result[key]['source'], 'unavailable')

    def test_malformed_or_contradictory_limits_cannot_become_capacity_claims(self):
        from specroad.runtime.limits import current_limits
        for limits in ((True, 10), (-2, 10), ('10', 20), (20, 10), (-1, 10), (float('nan'), 10), (1,), None):
            with self.subTest(limits=limits):
                with patch('specroad.runtime.limits._resource_api', return_value=self.resource_api(limits, limits)):
                    result = current_limits()
                self.assertEqual(result['process_cpu_seconds']['soft']['state'], 'unknown')

    def test_runtime_changes_do_not_change_semantic_projection(self):
        registry = builtin_registry()
        with patch('specroad.runtime.limits._resource_api', return_value=self.resource_api()), \
             patch('specroad.runtime.identity.platform.machine', return_value='machine-a'):
            first = capabilities(registry)
        with patch('specroad.runtime.limits._resource_api', return_value=self.resource_api((4096, 8192), (30, 60))), \
             patch('specroad.runtime.identity.platform.machine', return_value='machine-b'):
            second = capabilities(registry)
        self.assertEqual(first['semantic'], second['semantic'])
        self.assertNotEqual(first['runtime'], second['runtime'])
        self.assertEqual(json.dumps(first['semantic'], sort_keys=True, separators=(',', ':')),
                         json.dumps(second['semantic'], sort_keys=True, separators=(',', ':')))

    def test_registry_order_and_working_directory_do_not_change_semantic_bytes(self):
        original = builtin_registry(); reversed_registry = CommandRegistry(tuple(reversed(original.commands)))
        encode = lambda data: json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode('utf-8')
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            Path(one, 'specroad.json').write_bytes(b'broken')
            a = dispatch_result(['capabilities'], registry=original, cwd=one).as_dict()['result']['semantic']
            b = dispatch_result(['capabilities', '--quiet', '--no-color'], registry=reversed_registry, cwd=two).as_dict()['result']['semantic']
            self.assertEqual(encode(a), encode(b))
            self.assertEqual(Path(one, 'specroad.json').read_bytes(), b'broken')
            self.assertEqual(list(Path(two).iterdir()), [])

    def test_distribution_identity_changes_the_semantic_input_binding(self):
        registry = builtin_registry()
        record = {'format_version': 1, 'hash_algorithm': 'specroad-dev-payload-v1', 'build_sha256': 'a' * 64}
        with patch('specroad._build.BUILD_METADATA', record):
            first = capabilities(registry)
        with patch('specroad._build.BUILD_METADATA', dict(record, build_sha256='b' * 64)):
            second = capabilities(registry)
        self.assertNotEqual(first['semantic'], second['semantic'])
        self.assertEqual(first['semantic']['distribution']['build_sha256'], 'a' * 64)
        self.assertEqual(second['semantic']['distribution']['build_sha256'], 'b' * 64)

    def test_limit_query_is_fresh_for_each_embedded_invocation(self):
        with patch('specroad.runtime.limits._resource_api', side_effect=[
            self.resource_api(cpu=(10, 20)), self.resource_api(cpu=(20, 40))]):
            a = execute_request({'command_id': 'capabilities'}).result.as_dict()['result']
            b = execute_request({'command_id': 'capabilities'}).result.as_dict()['result']
        self.assertEqual(a['semantic'], b['semantic'])
        self.assertEqual(a['runtime']['limits']['process_cpu_seconds']['soft']['value'], 10)
        self.assertEqual(b['runtime']['limits']['process_cpu_seconds']['soft']['value'], 20)

    def test_bootstrap_succeeds_without_current_directory_lookup(self):
        with patch('pathlib.Path.cwd', side_effect=FileNotFoundError):
            result = dispatch_result(['capabilities'])
        self.assertEqual(result.exit_code, 0)
        self.assertIsNone(result.project)

    def test_no_claim_is_made_for_a_handler_without_a_machine_contract(self):
        base = builtin_registry()
        extra = replace(base.resolve('version'), command_id='fixture.undeclared', words=('undeclared',), protocol=None)
        registry = CommandRegistry((*base.commands, extra))
        result = dispatch_result(['capabilities'], registry=registry)
        self.assertEqual(result.exit_code, 2)
        self.assertIsNone(result.result)

    def test_relocated_module_and_zipapp_self_description_remains_executable(self):
        from support.portable import build_distribution, files_under
        from support.processes import run_python
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); build_distribution(root / 'build')
            relocated = root / 'relocated'; (root / 'build').rename(relocated)
            project = root / 'project'; project.mkdir(); (project / 'specroad.json').write_bytes(b'broken')
            before = files_under(project); dist_before = files_under(relocated)
            semantics = []
            for target in (relocated / 'module', relocated / 'specroad.pyz'):
                result = run_python(['-I', '-S', '-B', str(target), 'capabilities', '--format=json'], project, capture=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                semantic = json.loads(result.stdout)['result']['semantic']
                self.assertEqual(semantic['supported_versions']['schema'], ['0.2.0'])
                self.assertEqual(semantic['supported_versions']['srx'], ['1.0'])
                self.assertIn('python.srx.evaluate', semantic['capability_ids'])
                semantics.append(semantic)
                for command in semantic['commands']:
                    description = run_python(['-I', '-S', '-B', str(target), 'command', 'describe',
                        command['command_id'], '--format=json'], project, capture=True)
                    self.assertEqual(description.returncode, 0, description.stderr)
                    self.assertEqual(json.loads(description.stdout)['result']['command_id'], command['command_id'])
            self.assertEqual(semantics[0]['capability_ids'], semantics[1]['capability_ids'])
            self.assertEqual(semantics[0]['distribution']['build_sha256'], semantics[1]['distribution']['build_sha256'])
            self.assertEqual(files_under(project), before)
            self.assertEqual(files_under(relocated), dist_before)

    def test_bootstrap_limit_observation_never_changes_process_limits(self):
        body = '''
effects = []
def observe(event, args):
    if event in {'resource.setrlimit', 'resource.prlimit'}:
        effects.append(event); raise AssertionError('limit mutation forbidden')
sys.addaudithook(observe)
from specroad.cli.application import dispatch_result
assert dispatch_result(['capabilities']).exit_code == 0
assert not effects
'''
        with tempfile.TemporaryDirectory() as tmp:
            result = run_core(body, tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
