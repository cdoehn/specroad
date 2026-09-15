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
        for target in ('init', 'retire', 'schema.show', 'work.resume', 'not-registered'):
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
