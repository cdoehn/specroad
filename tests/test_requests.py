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
        for command in ('retire', 'init.unavailable', 'work.resume'):
            self.assertEqual(execute_request({'command_id': command}).result.exit_code, 2)
        self.assertEqual(dispatch_result(['retire']).exit_code, 2)
        self.assertEqual({c.command_id for c in builtin_registry().commands}, {'help', 'version', 'command.describe', 'capabilities', 'schema.list', 'schema.show', 'environment.check', 'init'})
        diagnosed = execute_request({'command_id': 'environment.check'}).result
        self.assertEqual(diagnosed.exit_code, 0)
        self.assertFalse(diagnosed.result['semantic_validation_performed'])


class RequestRobustnessTests(unittest.TestCase):
    def test_missing_input_and_exclusion_are_rejected_before_file_effects(self):
        calls = []
        command = fixture_command(lambda i: calls.append(i) or 0, options=(
            OptionSpec('--input', takes_value=True, required=True),
            OptionSpec('--one', excludes=('--two',)), OptionSpec('--two')))
        registry = CommandRegistry((command,))
        for options in ({}, {'--input': ''}, {'--input': 'file', '--one': True, '--two': True}):
            self.assertEqual(execute_request({'command_id': command.command_id, 'options': options}, registry=registry).result.exit_code, 2)
        self.assertEqual(calls, [])

    def test_malformed_envelopes_cannot_supply_handlers_or_context(self):
        calls = []; registry = CommandRegistry((fixture_command(lambda i: calls.append(i) or 0),))
        for request in (None, [], 'fixture.operation', {}, {'command_id': 1},
                        {'command_id': 'fixture.operation', 'handler': 'anything'},
                        {'command_id': 'fixture.operation', 'resolved': {}},
                        {'command_id': 'fixture.operation', 'project_root': '/arbitrary'},
                        {'command_id': 'fixture.operation', 'options': None}):
            self.assertEqual(execute_request(request, registry=registry).result.exit_code, 2)
        self.assertEqual(calls, [])

    def test_invalid_option_types_are_not_coerced(self):
        calls = []; registry = CommandRegistry((fixture_command(lambda i: calls.append(i) or 0),))
        for options in ({'--select': 'a'}, {'--select': []}, {'--select': [1]}, {'--select': [None]},
                        {'--select': [True]}, {'--check': 1}, {'--check': False}, {'--check': 'true'},
                        {'--check': [True]}, {'--unknown': True}, {'select': ['a']},
                        {1: True}, {'--select': {'nested': 'a'}}):
            with self.subTest(options=repr(options)):
                self.assertEqual(execute_request({'command_id': 'fixture.operation', 'options': options}, registry=registry).result.exit_code, 2)
        self.assertEqual(calls, [])

    def test_invalid_unicode_and_nul_are_usage_errors_for_both_inputs(self):
        calls = []; registry = CommandRegistry((fixture_command(lambda i: calls.append(i) or 0),))
        for text in ('x\0y', '\ud800'):
            self.assertEqual(dispatch_result(['fixture-op', '--select', text], registry=registry).exit_code, 2)
            self.assertEqual(execute_request({'command_id': 'fixture.operation', 'options': {'--select': [text]}}, registry=registry).result.exit_code, 2)
        self.assertEqual(calls, [])

    def test_missing_cli_input_never_attempts_to_read_stdin(self):
        # Child-local audit hook observes an actual input attempt and fails it.
        # The parent neither waits for a prompt nor parses the usage message.
        body = '''
from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.registry import CommandClass, CommandRegistry, CommandSpec, EffectScope, OptionSpec, PreflightProfile
attempts = []
def guard(event, args):
    if event == 'builtins.input':
        attempts.append(event)
        raise AssertionError('interactive input is forbidden')
sys.addaudithook(guard)
calls = []
command = CommandSpec('fixture.input', ('fixture', 'input'), CommandClass.READ_ONLY,
    PreflightProfile.INPUT_READ, EffectScope.NONE, handler=lambda i: calls.append(i) or 0,
    options=(OptionSpec('--input', takes_value=True, required=True),))
registry = CommandRegistry((command,))
for result in (dispatch_result(['fixture', 'input'], registry=registry),
               execute_request({'command_id': 'fixture.input'}, registry=registry).result):
    assert result.exit_code == 2 and result.status.value == 'failed'
    assert len(result.diagnostics) == 1
assert attempts == [] and calls == []
'''
        with tempfile.TemporaryDirectory() as tmp:
            r = run_core(body, tmp)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_handler_failure_and_unavailable_result_never_claim_success(self):
        from specroad.cli.results import OperationFailure, FailureKind
        def io_failure(invocation):
            raise OSError('private environment')
        def conflict(invocation):
            raise OperationFailure(FailureKind.CONFLICT, 'conflict')
        def broken(invocation):
            raise ValueError('private failure')
        for handler, code in ((io_failure, 5), (conflict, 6), (broken, 4), (lambda i: None, 4), (lambda i: 8, 4)):
            registry = CommandRegistry((fixture_command(handler),))
            self.assertEqual(execute_request({'command_id': 'fixture.operation'}, registry=registry).result.exit_code, code)
            self.assertEqual(dispatch_result(['fixture-op'], registry=registry).exit_code, code)

    def test_foreign_or_forged_invocation_cannot_execute_a_handler(self):
        from specroad.cli.contracts import Invocation
        calls = []; command = fixture_command(lambda i: calls.append('original') or 0)
        registry = CommandRegistry((command,))
        forged = replace(command, handler=lambda i: calls.append('forged') or 0)
        with self.assertRaises(CommandUsageError):
            registry.execute_result(Invocation(forged, {}))
        with self.assertRaises(CommandUsageError):
            registry.execute_result(None)
        invalid = Invocation(command, {'--unknown': True})
        self.assertEqual(registry.execute_result(invalid).exit_code, 2)
        self.assertEqual(calls, [])

    def test_registry_convenience_entry_cannot_bypass_root_validation(self):
        from specroad.cli.options import global_options
        calls = []; command = fixture_command(lambda i: calls.append(i) or 0,
            preflight_profile=PreflightProfile.PROJECT_METADATA, requires_project=True,
            options=global_options('--project'))
        registry = CommandRegistry((command,))
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(registry.invoke(['fixture-op'], cwd=tmp), 2)
            self.assertEqual(registry.execute(registry.parse(['fixture-op']), cwd=tmp), 2)
            self.assertEqual(calls, [])
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_context_dependencies_are_local_to_one_call(self):
        from specroad.cli.invocation_context import InvocationContextBuilder
        from specroad.runtime import UnsupportedRuntimeError
        def denied():
            raise UnsupportedRuntimeError('fixture runtime')
        builder = InvocationContextBuilder(runtime_check=denied)
        self.assertEqual(execute_request({'command_id': 'version'}, context_builder=builder).result.exit_code, 5)
        self.assertEqual(execute_request({'command_id': 'version'}).result.exit_code, 0)

    def test_choices_repetitions_and_infix_options_have_same_semantics(self):
        calls = []; command = fixture_command(lambda i: calls.append(dict(i.options)) or 0,
            options=(OptionSpec('--mode', takes_value=True, choices=('a', 'b')),
                     OptionSpec('--select', takes_value=True, repeatable=True)))
        registry = CommandRegistry((command,))
        for values in (['a', 'b'], ['a', 'a'], ['Größe', 'x=y']):
            argv = ['fixture', '--mode=b', 'operation'] + [f'--select={v}' for v in values]
            self.assertEqual(dispatch_result(argv, registry=registry).exit_code, 0)
            self.assertEqual(execute_request({'command_id': command.command_id,
                'options': {'--mode': 'b', '--select': values}}, registry=registry).result.exit_code, 0)
            self.assertEqual(calls[-1], calls[-2])
        for mode in ('c', '--other'):
            self.assertEqual(execute_request({'command_id': command.command_id,
                'options': {'--mode': mode}}, registry=registry).result.exit_code, 2)

    def test_data_request_uses_canonical_id_not_alias_spelling(self):
        calls = []; registry = CommandRegistry((fixture_command(lambda i: calls.append(i) or 0),))
        self.assertEqual(execute_request({'command_id': 'fixture-op'}, registry=registry).result.exit_code, 2)
        self.assertEqual(execute_request({'command_id': 'fixture.operation'}, registry=registry).result.exit_code, 0)
        self.assertEqual(len(calls), 1)

    def test_error_format_preference_does_not_turn_bad_request_into_success(self):
        response = execute_request({'command_id': 'unavailable', 'options': {'--format': 'json', '--quiet': True}})
        self.assertEqual(response.options['--format'], 'json')
        self.assertTrue(response.options['--quiet'])
        self.assertEqual(response.result.exit_code, 2)
        self.assertEqual(response.result.as_dict()['summary']['failure_kind'], 'usage')
