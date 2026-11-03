"""Known in-flight work settles before a bounded continuation; no real models."""
from copy import deepcopy
from unittest.mock import patch
from specroad_control.commands import recover
from specroad_control.config import render
from specroad_control.errors import ControlError
from specroad_control.local import write_private, json_read
from codex_control_tests import test_continuation as partial
from codex_control_tests import test_overload_retry as retry
from codex_control_tests.automation_support import package


class WaitingCodex(partial.PartialCodex):
    def __init__(self, case):
        super().__init__(case)
        self.effect = {'id': 'test-command', 'type': 'commandExecution',
                       'command': 'python3 -B tools/catalog.py', 'cwd': str(case.dev),
                       'source': 'unifiedExecStartup', 'status': 'inProgress', 'exitCode': None,
                       'aggregatedOutput': '', 'durationMs': None}
        self.background = [{'processId': 'owned-test-process', 'itemId': self.effect['id'],
                            'command': self.effect['command'], 'cwd': self.effect['cwd']}]
        self.observations = 0

    def inspect_overload_wait(self, turn_id):
        self.observations += 1
        return {'thread_status': self.status, 'turn': deepcopy(self.turns[turn_id]),
                'latest_turn_id': next(reversed(self.turns)), 'background_terminals': deepcopy(self.background)}

    def finish_command(self):
        self.effect.update(status='completed', exitCode=0, aggregatedOutput='catalog finished', durationMs=300)
        self.background = []


class WaitCase(retry.RetryCase):
    def setUp(self):
        super().setUp()
        self.codex = WaitingCodex(self)
        self.engine.codex = self.codex
        self.codex.observe = self.engine.observe

    def begin(self):
        result = self.engine.tick()
        self.assertFalse(result['halted'])
        self.assertEqual(self.ledger().current()['stage'], 'overload_wait')
        self.assertIsNone(self.ledger().retry_info(self.seed['sha256']))
        return result

    def advance(self, seconds=30):
        self.now += seconds
        return self.engine.tick()


class OverloadWaitTests(WaitCase):
    def test_running_command_then_complete_then_backoff_then_same_source(self):
        self.assertEqual(self.begin()['retry_after'], 30)
        self.codex.finish_command()
        self.assertEqual(self.advance()['retry_after'], 60)
        self.assertEqual(self.ledger().current()['stage'], 'retry_wait')
        self.assertEqual(self.codex.calls, 1)
        self.advance(60)
        self.assertEqual(self.codex.calls, 2)
        self.assertEqual(self.ledger().current()['stage'], 'no_work')
        self.assertEqual(self.codex.continuations[-1]['mode'], 'continuation')
        self.assertEqual((self.dev/'partial.txt').read_text(), 'preserved work 1')

    def test_live_background_can_last_hours_without_budget_or_new_call(self):
        self.begin()
        for _ in range(3):
            self.assertEqual(self.advance(3600)['retry_after'], 30)
        self.assertEqual(self.codex.calls, 1)
        self.assertIsNone(self.ledger().retry_info(self.seed['sha256']))

    def test_events_before_due_do_not_observe_or_shift_deadline(self):
        self.begin()
        before = self.ledger().overload_wait()
        reads = self.codex.observations
        for _ in range(4):
            self.engine.tick()
        self.assertEqual(self.codex.observations, reads)
        self.assertEqual(self.ledger().overload_wait(), before)

    def test_empty_background_alone_never_authorizes_a_model(self):
        self.begin(); self.codex.background = []
        self.assertFalse(self.advance()['halted'])
        self.assertFalse(self.advance(90)['halted'])
        self.assertTrue(self.advance(30)['halted'])
        self.assertEqual(self.ledger().current()['error'], 'overload_completion_unproven')
        self.assertEqual(self.codex.calls, 1)

    def test_delayed_exit_after_background_disappears_allows_continuation(self):
        self.begin(); self.codex.background = []
        self.advance()
        self.codex.finish_command()
        self.assertEqual(self.advance()['retry_after'], 60)

    def test_protected_workspace_change_blocks_without_rebaseline(self):
        self.begin(); self.codex.finish_command()
        (self.dev/'partial.txt').write_text('foreign edit')
        self.assertTrue(self.advance()['halted'])
        self.assertEqual(self.ledger().current()['error'], 'overload_checkpoint_changed')
        self.assertEqual(self.codex.calls, 1)

    def test_command_identity_change_is_not_a_completion(self):
        self.begin(); self.codex.finish_command()
        self.codex.effect['command'] = 'another command'
        self.assertTrue(self.advance()['halted'])

    def test_new_background_is_not_accepted_as_original_work(self):
        self.begin()
        self.codex.background.append({'processId': 'foreign-process'})
        self.assertTrue(self.advance()['halted'])
        self.assertEqual(self.codex.calls, 1)

    def test_bundle_has_priority_after_command_completion(self):
        self.begin()
        package(self.exchange/'finished.zip', {'kind': 'patch', 'binding': self.binding})
        self.assertFalse(self.advance()['again'])
        self.codex.finish_command()
        self.assertTrue(self.advance()['again'])
        self.assertEqual(self.ledger().current()['stage'], 'waiting_result')
        self.assertIsNone(self.ledger().retry_info(self.seed['sha256']))
        self.assertEqual(self.codex.calls, 1)

    def test_explicit_modern_recovery_is_offline_and_keeps_pause_and_receipts(self):
        self.codex.background = []
        self.codex.inspect_overload_wait = None  # Simulate old worker's failure path.
        self.assertTrue(self.engine.tick()['halted'])
        self.codex.finish_command()
        write_private(self.paths.config, render(self.config).encode())
        directory = self.paths.state/'jobs'/self.seed['sha256']
        before = {name: (directory/name).read_bytes() for name in ('attempt.json', 'failure.json', 'dispatch.json')}
        self.engine.gate.set(False)
        with patch('specroad_control.commands.Engine', return_value=self.engine):
            with patch.object(self.codex, 'check', side_effect=AssertionError('general check must stay strict')):
                result = recover(self.paths)
        self.assertEqual(result['stage'], 'retry_wait')
        self.assertFalse(result['model_called'])
        self.assertFalse(result['service_started'])
        self.assertFalse(self.engine.gate.allowed)
        self.assertEqual(self.codex.calls, 1)
        self.assertEqual(before, {name: (directory/name).read_bytes() for name in before})
        self.assertEqual(json_read(directory/'failure.json')['turn_status'], 'failed')

    def test_modern_recovery_requires_terminal_commands(self):
        self.codex.inspect_overload_wait = None
        self.engine.tick()
        write_private(self.paths.config, render(self.config).encode())
        with patch('specroad_control.commands.Engine', return_value=self.engine), self.assertRaises(ControlError):
            recover(self.paths)
        self.assertEqual(self.ledger().current()['stage'], 'uncertain')
        self.assertEqual(self.codex.calls, 1)
