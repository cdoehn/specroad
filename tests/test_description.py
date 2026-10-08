"""Machine command contracts and effects, never help text or presentation."""

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.contracts import CommandProtocol, PositionalSpec
from specroad.cli.registry import (CommandClass, CommandRegistry, CommandSpec,
    CommandUsageError, EffectScope, OptionSpec, PreflightProfile)
from specroad.cli.requests import CommandRequest
from specroad.cli.results import CommandResult
from specroad.cli.self_description import describe_command
from support import run_cli


def described_fixture(handler):
    return CommandSpec('fixture.action', ('fixture', 'action'), CommandClass.GENERATED_OUTPUT,
        PreflightProfile.INPUT_READ, EffectScope.EXTERNAL_OUTPUT, handler=handler,
        options=(OptionSpec('--mode', takes_value=True, required=True, choices=('a', 'b')),
                 OptionSpec('--left', excludes=('--right',)), OptionSpec('--right'),
                 OptionSpec('--select', takes_value=True, repeatable=True)),
        positionals=(PositionalSpec('name'), PositionalSpec('detail', required=False)),
        protocol=CommandProtocol('fixture-result-v1', {
            'command_id': 'fixture.action', 'arguments': {'name': 'sample'},
            'options': {'--mode': 'a'}}))


class DescriptionWorkTests(unittest.TestCase):
    def test_each_published_example_runs_the_actual_command(self):
        registry = builtin_registry()
        for command in registry.commands:
            document = describe_command(registry, command.command_id)
            for request in document['examples']:
                with self.subTest(command=command.command_id):
                    result = execute_request(request, registry=registry).result
                    self.assertEqual(result.exit_code, 0)
                    self.assertEqual(result.command, command.command_id)
                    self.assertIsNone(result.project)

    def test_cli_and_structured_description_are_same_contract(self):
        cli = dispatch_result(['command', 'describe', 'version', '--format', 'json'])
        data = execute_request({'command_id': 'command.describe',
            'arguments': {'command': 'version'}, 'options': {'--format': 'json'}}).result
        self.assertEqual(cli.exit_code, 0)
        self.assertEqual(cli.as_dict(), data.as_dict())
        self.assertEqual(cli.result['stdout']['json_envelope_version'], '2.0.0')

    def test_unknown_commands_are_not_success_placeholders(self):
        for target in ('init', 'retire', 'schema.unavailable', 'work.resume', 'not-registered'):
            self.assertEqual(dispatch_result(['command', 'describe', target]).exit_code, 2)

    def test_missing_extra_and_unknown_input_is_rejected(self):
        for argv in (['command', 'describe'], ['command', 'describe', 'version', 'extra'],
                     ['command', 'describe', 'version', '--unknown'],
                     ['command', 'describe', 'version', '--format', 'sarif']):
            self.assertEqual(dispatch_result(argv).exit_code, 2)

    def test_describing_writer_cannot_execute_or_create_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'produced'
            def handler(invocation):
                target.write_bytes(b'actual effect')
                return CommandResult(invocation.command.command_id, result={'created': True})
            command = described_fixture(handler)
            registry = CommandRegistry((*builtin_registry().commands, command))
            result = dispatch_result(['command', 'describe', command.command_id], registry=registry)
            self.assertEqual(result.exit_code, 0)
            self.assertFalse(target.exists())
            document = result.as_dict()['result']
            self.assertEqual(document['write_effects']['scope'], 'external_output')
            self.assertEqual(execute_request(document['examples'][0], registry=registry).result.exit_code, 0)
            self.assertEqual(target.read_bytes(), b'actual effect')

    def test_request_schema_constraints_match_rejections_before_effects(self):
        calls = []; command = described_fixture(lambda i: calls.append(i) or 0)
        registry = CommandRegistry((command,))
        document = describe_command(registry, command.command_id)
        schema = document['request_schema']
        self.assertEqual(set(schema['required']), {'command_id', 'options', 'arguments'})
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(schema['properties']['options']['required'], ['--mode'])
        self.assertEqual(schema['properties']['options']['properties']['--select']['type'], 'array')
        self.assertEqual(document['mutually_exclusive'], [['--left', '--right']])
        for options in ({}, {'--mode': 'invalid'}, {'--mode': 'a', '--left': True, '--right': True},
                        {'--mode': 'a', '--select': 'x'}):
            self.assertEqual(execute_request({'command_id': command.command_id,
                'arguments': {'name': 'sample'}, 'options': options}, registry=registry).result.exit_code, 2)
        self.assertEqual(calls, [])

    def test_invalid_examples_are_rejected_at_registration_without_execution(self):
        calls = []; command = described_fixture(lambda i: calls.append(i) or 0)
        bad = replace(command, protocol=CommandProtocol('fixture-result-v1', {'command_id': command.command_id}))
        with self.assertRaises(CommandUsageError):
            CommandRegistry((bad,))
        self.assertEqual(calls, [])

    def test_argument_mapping_is_frozen_and_preserved_in_invocation_api(self):
        arguments = {'command': 'version'}
        request = CommandRequest('command.describe', arguments=arguments)
        arguments['command'] = 'unavailable'
        with self.assertRaises(TypeError):
            request.arguments['command'] = 'help'
        registry = builtin_registry(); invocation = registry.bind_request(request)
        self.assertEqual(registry.execute_result(invocation).result['command_id'], 'version')
        self.assertEqual(request.as_dict()['arguments'], {'command': 'version'})

    def test_infix_options_and_optional_positionals_share_binding(self):
        seen = []; command = described_fixture(lambda i: seen.append(dict(i.arguments)) or 0)
        registry = CommandRegistry((command,))
        cli = dispatch_result(['fixture', '--mode=a', 'action', 'sample', '--select=x', 'detail'], registry=registry)
        data = execute_request({'command_id': command.command_id,
            'arguments': {'name': 'sample', 'detail': 'detail'},
            'options': {'--mode': 'a', '--select': ['x']}}, registry=registry).result
        self.assertEqual([cli.exit_code, data.exit_code], [0, 0])
        self.assertEqual(seen, [{'name': 'sample', 'detail': 'detail'}] * 2)

    def test_invalid_positional_contracts_are_rejected(self):
        command = described_fixture(lambda i: 0)
        for positions in ((PositionalSpec('name'), PositionalSpec('name')),
                          (PositionalSpec('optional', required=False), PositionalSpec('required')),
                          ('name',)):
            with self.assertRaises(CommandUsageError):
                replace(command, positionals=positions)
        for kwargs in ({'name': 'bad-name'}, {'name': 'x', 'required': 1},
                       {'name': 'x', 'choices': ('a', 'a')}):
            with self.assertRaises(CommandUsageError):
                PositionalSpec(**kwargs)

    def test_invalid_structured_arguments_do_not_execute_handler(self):
        calls = []; command = described_fixture(lambda i: calls.append(i) or 0)
        registry = CommandRegistry((command,))
        for arguments in (None, [], {'unknown': 'x'}, {'name': ''}, {'name': True},
                          {'name': 1}, {'name': ['x']}, {'name': '\ud800'},
                          {'name': 'x\0y'}, {'detail': 'gap'}):
            self.assertEqual(execute_request({'command_id': command.command_id,
                'arguments': arguments, 'options': {'--mode': 'a'}}, registry=registry).result.exit_code, 2)
        self.assertEqual(calls, [])

    def test_real_cli_delivers_parsable_description_in_fresh_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli(['command', 'describe', 'command.describe', '--format', 'json'], tmp, capture=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)['result']
            self.assertEqual(payload['command_id'], 'command.describe')
            self.assertEqual(payload['parameters'][0]['name'], 'command')
            self.assertEqual(execute_request(payload['examples'][0]).result.exit_code, 0)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_project_metadata_is_not_read_or_repaired(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); config = root / 'specroad.json'; config.write_bytes(b'broken metadata')
            result = dispatch_result(['command', 'describe', 'version'], cwd=root)
            self.assertEqual(result.exit_code, 0)
            self.assertIsNone(result.project)
            self.assertEqual(config.read_bytes(), b'broken metadata')
            self.assertEqual(list(root.iterdir()), [config])

    def test_description_has_no_mutable_shared_state(self):
        registry = builtin_registry()
        document = describe_command(registry, 'version')
        document['options'].clear(); document['examples'][0]['options']['--format'] = 'invalid'
        fresh = describe_command(registry, 'version')
        self.assertEqual({option['flag'] for option in fresh['options']}, {'--format', '--quiet', '--no-color'})
        self.assertEqual(execute_request(fresh['examples'][0], registry=registry).result.exit_code, 0)


class DescriptionRobustnessTests(unittest.TestCase):
    def test_id_spelling_and_alias_describe_identical_canonical_data(self):
        registry = builtin_registry()
        documents = [describe_command(registry, name) for name in ('help', '--help', '-h')]
        self.assertEqual(documents[0], documents[1]); self.assertEqual(documents[1], documents[2])
        self.assertEqual(describe_command(registry, 'command describe'),
                         describe_command(registry, 'command.describe'))
        result = dispatch_result(['command', 'describe', '--format=json', '--', '-h'])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.result['command_id'], 'help')

    def test_quoted_spelling_is_data_not_an_executable_command_line(self):
        for target in ('version --format json', 'version; touch output', 'version\n--help', ' version', 'version '):
            self.assertEqual(dispatch_result(['command', 'describe', target]).exit_code, 2)

    def test_ambiguous_alias_cannot_select_arbitrary_description(self):
        base = builtin_registry().resolve('version')
        other = replace(base, command_id='fixture', words=('other',), aliases=(('version-id',),),
            protocol=CommandProtocol('fixture-v1', {'command_id': 'fixture'}))
        shadow = replace(base, command_id='version_id', words=('version-id-two',), aliases=(('fixture',),),
            protocol=CommandProtocol('fixture-v1', {'command_id': 'version_id'}))
        registry = CommandRegistry((other, shadow))
        with self.assertRaises(CommandUsageError):
            describe_command(registry, 'fixture')

    def test_all_current_handlers_explicitly_declare_no_continuation(self):
        registry = builtin_registry()
        for command in registry.commands:
            document = describe_command(registry, command.command_id)
            work = document['work']
            self.assertFalse(work['continuation_supported'])
            self.assertEqual(work['external_side_effects'], [])
            self.assertEqual(work['checkpoint_algorithms'], [])
            self.assertEqual(document['write_effects']['external_work'], [])
            self.assertEqual(document['lock_kind'], 'none')
            self.assertNotIn(8, document['exit_codes'])
            self.assertEqual(document['budget_policy_version'],
                             'runtime-budget-v2' if command.command_id == 'environment.check' else None)
            self.assertIsNone(document['stdout']['continuation']['sarif_fallback'])

    def test_minimum_step_limits_are_explicitly_unmeasured(self):
        document = describe_command(builtin_registry(), 'command.describe')
        minimum = document['work']['minimum_step']
        self.assertEqual(minimum['required_inputs'], ['command_registry'])
        self.assertEqual(minimum['limits_status'], 'unmeasured')
        self.assertIsNone(minimum['limits']['memory_bytes'])
        self.assertIsNone(minimum['limits']['cpu_seconds'])
        self.assertEqual(minimum['blocked_exit_code'], 5)

    def test_metadata_cannot_activate_a_missing_work_engine(self):
        from specroad.cli.contracts import WorkContract
        for kwargs in ({'continuation_supported': True}, {'continuation_supported': 0},
                       {'checkpoint_algorithms': ('sha256',)}, {'external_side_effects': ('work_root',)},
                       {'required_inputs': ('same', 'same')}):
            with self.assertRaises(CommandUsageError):
                WorkContract(**kwargs)

    def test_current_handlers_reject_work_and_write_options_before_effects(self):
        registry = builtin_registry()
        for command in registry.commands:
            document = describe_command(registry, command.command_id)
            accepted = {option['flag'] for option in document['options']}
            rejected = ('--work-dir', '--resume', '--request-id', '--dry-run', '--actor-id')
            if command.command_id == 'environment.check':
                self.assertIn('--project', accepted)
            else:
                rejected += ('--project',)
            for flag in rejected:
                self.assertNotIn(flag, accepted)
                example = document['examples'][0]
                example['options'][flag] = 'unavailable'
                self.assertEqual(execute_request(example).result.exit_code, 2)
                del example['options'][flag]

    def test_mutating_a_contract_document_cannot_change_the_active_registry(self):
        registry = builtin_registry(); document = describe_command(registry, 'version')
        document['work']['checkpoint_algorithms'].append('fake')
        document['work']['continuation_supported'] = True
        self.assertEqual(describe_command(registry, 'version')['work']['checkpoint_algorithms'], [])
        self.assertEqual(dispatch_result(['version', '--work-dir', 'fake'], registry=registry).exit_code, 2)

    def test_description_observes_no_project_reads_processes_network_or_stdin(self):
        from support import run_core
        body = '''
import os
root = os.getcwd(); effects = []
def observe(event, args):
    if event in {'subprocess.Popen', 'os.system', 'os.posix_spawn', 'socket.connect', 'socket.getaddrinfo', 'builtins.input'}:
        effects.append(event); raise AssertionError('forbidden bootstrap effect')
    if event in {'open', 'os.scandir', 'os.listdir'} and args and isinstance(args[0], (str, bytes)):
        path = os.path.abspath(os.fsdecode(args[0]))
        if path == root or path.startswith(root + os.sep):
            effects.append(event); raise AssertionError('forbidden project access')
sys.addaudithook(observe)
from specroad.cli.application import dispatch_result
for target in ('version', 'help', 'command.describe'):
    result = dispatch_result(['command', 'describe', target, '--format=json'])
    assert result.exit_code == 0 and result.project is None
assert not effects
assert 'specroad.cli.project_selection' not in sys.modules
assert 'specroad.cli.presentation' not in sys.modules
assert 'py3langid' not in sys.modules
'''
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'specroad.json').write_bytes(b'broken')
            result = run_core(body, root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / 'specroad.json').read_bytes(), b'broken')

    def test_unknown_argument_names_and_extra_options_have_no_stdin_fallback(self):
        for request in ({'command_id': 'command.describe', 'arguments': {'COMMAND': 'version'}},
                        {'command_id': 'command.describe', 'arguments': {'command': 'version', 'input': '-'}},
                        {'command_id': 'command.describe', 'arguments': {'command': 'version'}, 'stdin': '-'}):
            self.assertEqual(execute_request(request).result.exit_code, 2)

    def test_described_exitcodes_cover_real_usage_and_runtime_failures(self):
        from specroad.cli.invocation_context import InvocationContextBuilder
        from specroad.runtime import UnsupportedRuntimeError
        def unsupported():
            raise UnsupportedRuntimeError('fixture')
        registry = builtin_registry()
        for command in registry.commands:
            document = describe_command(registry, command.command_id)
            response = execute_request(document['examples'][0],
                context_builder=InvocationContextBuilder(runtime_check=unsupported)).result
            self.assertEqual(response.exit_code, 5)
            self.assertIn(response.exit_code, document['exit_codes'])
            self.assertIn(response.diagnostics[0].code, document['diagnostic_codes'])

    def test_text_values_keep_unicode_spaces_and_literal_separator(self):
        calls = []; command = described_fixture(lambda i: calls.append(dict(i.arguments)) or 0)
        registry = CommandRegistry((command,))
        for text in ('Größe 😀', 'a=b', '--literal', '-h', 'line\nbreak'):
            result = dispatch_result(['fixture', 'action', '--mode=a', '--', text], registry=registry)
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(calls[-1], {'name': text})
        self.assertEqual(dispatch_result(['--', 'fixture', 'action', '--mode=a', 'x'], registry=registry).exit_code, 2)

    def test_missing_protocol_is_not_fabricated_from_handler_name(self):
        command = replace(described_fixture(lambda i: 0), protocol=None)
        registry = CommandRegistry((*builtin_registry().commands, command))
        self.assertEqual(dispatch_result(['command', 'describe', command.command_id], registry=registry).exit_code, 2)

    def test_stored_invocation_arguments_rebind_and_do_not_inject_registry(self):
        from specroad.cli.contracts import Invocation
        registry = builtin_registry(); command = registry.resolve('command.describe')
        invocation = Invocation(command, {}, arguments={'command': 'version'}, registry=object())
        self.assertEqual(registry.execute_result(invocation).result['command_id'], 'version')
        bad = replace(invocation, arguments={'command': 'unavailable'})
        self.assertEqual(registry.execute_result(bad).exit_code, 2)
