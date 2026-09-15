"""Structured request, canonical alias and real file-effect integration tests."""

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.requests import CommandRequest
from specroad.cli.registry import (CommandClass, CommandRegistry, CommandSpec,
    CommandUsageError, EffectScope, OptionSpec, PreflightProfile)
from specroad.cli.results import CommandResult
from support import run_core


def fixture_command(handler, **changes):
    return replace(CommandSpec(
        command_id='fixture.operation', words=('fixture', 'operation'),
        aliases=(('fixture-op',),), command_class=CommandClass.READ_ONLY,
        preflight_profile=PreflightProfile.INPUT_READ, effect_scope=EffectScope.NONE,
        handler=handler, options=(OptionSpec('--select', takes_value=True, repeatable=True),
                                OptionSpec('--check'),)), **changes)


class RequestWorkTests(unittest.TestCase):
    def test_actual_bootstrap_has_one_result_for_cli_alias_and_request(self):
        outcomes = [dispatch_result(['--help']), dispatch_result(['-h']),
                    execute_request({'command_id': 'help'}).result]
        self.assertEqual([item.exit_code for item in outcomes], [0, 0, 0])
        self.assertEqual([item.command for item in outcomes], ['help', 'help', 'help'])
        self.assertEqual([item.project for item in outcomes], [None, None, None])

    def test_alias_and_structured_request_normalize_the_same_operation(self):
        calls = []
        def handler(invocation):
            calls.append((invocation.command.command_id, dict(invocation.options), dict(invocation.resolved.values)))
            return CommandResult(invocation.command.command_id, result={'selected': list(invocation.options['--select'])})
        registry = CommandRegistry((fixture_command(handler),))
        canonical = dispatch_result(['fixture', 'operation', '--select', 'a', '--select=b', '--check'], registry=registry)
        alias = dispatch_result(['fixture-op', '--select=a', '--check', '--select=b'], registry=registry)
        request = execute_request({'command_id': 'fixture.operation', 'options': {'--select': ['a', 'b'], '--check': True}}, registry=registry).result
        self.assertEqual(calls[0], calls[1]); self.assertEqual(calls[1], calls[2])
        self.assertEqual(canonical.as_dict(), alias.as_dict())
        self.assertEqual(canonical.as_dict(), request.as_dict())

    def test_structured_input_is_defensively_frozen(self):
        supplied = {'--select': ['a']}; request = CommandRequest('fixture.operation', supplied)
        supplied['--select'].append('b'); supplied['--check'] = True
        self.assertEqual(dict(request.options), {'--select': ('a',)})
        with self.assertRaises(TypeError):
            request.options['--check'] = True

    def test_public_handler_is_executed_once_with_real_file_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); target = root / 'output'; target.write_bytes(b'')
            def handler(invocation):
                with target.open('ab') as stream:
                    stream.write(b'x')
                return CommandResult(invocation.command.command_id, result={'changed': True})
            command = fixture_command(handler, command_class=CommandClass.GENERATED_OUTPUT,
                                      effect_scope=EffectScope.EXTERNAL_OUTPUT)
            registry = CommandRegistry((command,))
            self.assertEqual(dispatch_result(['fixture-op'], registry=registry).exit_code, 0)
            self.assertEqual(target.read_bytes(), b'x')
            self.assertEqual(execute_request({'command_id': command.command_id}, registry=registry).result.exit_code, 0)
            self.assertEqual(target.read_bytes(), b'xx')

    def test_structured_public_api_runs_in_fresh_process(self):
        body = '''
from specroad.cli.application import execute_request
response = execute_request({'command_id': 'version', 'options': {'--format': 'json'}})
assert response.result.exit_code == 0
assert response.result.command == 'version'
assert response.result.result['python_support']['verification_status'] == 'unrecorded'
'''
        with tempfile.TemporaryDirectory() as tmp:
            r = run_core(body, tmp)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_structured_options_obey_command_specific_availability(self):
        self.assertEqual(execute_request({'command_id': 'help', 'options': {'--project': '/tmp'}}).result.exit_code, 2)
        self.assertEqual(execute_request({'command_id': 'version', 'options': {'--strict': True}}).result.exit_code, 2)
        self.assertEqual(execute_request({'command_id': 'help', 'options': {'--format': 'sarif'}}).result.exit_code, 2)

    def test_input_strings_remain_data_not_shell_commands(self):
        calls = []; text = '$(false); arbitrary | data with spaces'
        registry = CommandRegistry((fixture_command(lambda i: calls.append(dict(i.options)) or 0),))
        self.assertEqual(execute_request({'command_id': 'fixture.operation', 'options': {'--select': [text]}}, registry=registry).result.exit_code, 0)
        self.assertEqual(calls, [{'--select': (text,)}])

    def test_non_git_operation_and_alias_use_project_without_git(self):
        from specroad.cli.options import global_options
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'specroad.json').write_bytes(b'{}')
            original = (root / 'specroad.json').read_bytes(); calls = []
            command = fixture_command(lambda i: calls.append(i.resolved.project_root) or 0,
                preflight_profile=PreflightProfile.PROJECT_METADATA, requires_project=True,
                options=global_options('--project'))
            registry = CommandRegistry((command,))
            self.assertEqual(registry.invoke(['fixture-op'], cwd=root), 0)
            self.assertEqual(execute_request({'command_id': command.command_id}, registry=registry, cwd=root).result.exit_code, 0)
            self.assertEqual(calls, [root.resolve(), root.resolve()])
            self.assertFalse((root / '.git').exists())
            self.assertEqual((root / 'specroad.json').read_bytes(), original)

    def test_public_invocation_api_rebuilds_context_before_executing(self):
        from specroad.cli.invocation_context import prepare_invocation
        from specroad.cli.options import global_options
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'specroad.json').write_bytes(b'{}'); calls = []
            command = fixture_command(lambda i: calls.append(i.resolved.values['fail_on']) or 0,
                preflight_profile=PreflightProfile.PROJECT_METADATA, requires_project=True,
                options=global_options('--project'))
            registry = CommandRegistry((command,))
            invocation = prepare_invocation(registry.parse(['fixture-op', '--project', str(root)]))
            (root / 'specroad.json').write_bytes(b'{"validation_policy":{"fail_on":"warning"}}')
            self.assertEqual(registry.execute_result(invocation).exit_code, 0)
            self.assertEqual(calls, ['warning'])

    def test_unavailable_aliases_are_not_silently_registered(self):
        for command in ('retire', 'init', 'environment.check', 'work.resume'):
            self.assertEqual(execute_request({'command_id': command}).result.exit_code, 2)
        self.assertEqual(dispatch_result(['retire']).exit_code, 2)
        self.assertEqual({c.command_id for c in builtin_registry().commands}, {'help', 'version'})
