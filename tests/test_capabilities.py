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
        self.assertEqual(set(semantic['capability_ids']), {'cli.' + item for item in ids} | {'python.structured-request'})
        self.assertEqual(set(semantic['command_groups']), {item.split('.')[0] for item in ids})
        self.assertEqual(semantic['command_classes'], ['read_only'])
        for item in semantic['commands']:
            result = dispatch_result(['command', 'describe', item['command_id']], registry=registry)
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(list(result.result['stdout']['formats']), item['output_formats'])

    def test_unimplemented_formats_versions_and_engines_are_not_advertised(self):
        semantic = capabilities(builtin_registry())['semantic']
        self.assertEqual(semantic['output_formats'], ['json', 'pretty'])
        self.assertNotIn('sarif', semantic['output_formats'])
        self.assertEqual(semantic['exchange_formats'], [])
        for kind in ('schema', 'srx', 'proposal'):
            self.assertEqual(semantic['supported_versions'][kind], [])
        self.assertFalse(semantic['work']['engine_available'])
        self.assertEqual(semantic['work']['checkpoint_algorithms'], [])
        self.assertIsNone(semantic['work']['budget_policy_version'])

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
