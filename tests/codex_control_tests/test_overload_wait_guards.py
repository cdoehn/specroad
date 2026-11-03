"""Durable checkpoints, bounded budgets, races and explicit modern recovery."""
from copy import deepcopy
from dataclasses import replace
import contextlib
import io
import json
import sqlite3
from unittest.mock import patch
from specroad_control.automation import Engine, Gate
from specroad_control.commands import recover
from specroad_control.config import render
from specroad_control.errors import ControlError
from specroad_control.local import json_read, json_write, write_private
from specroad_control.retry_ledger import attempt_directory
from codex_control_tests.automation_support import FakeCore, package
from codex_control_tests import test_overload_wait as waiting


class WaitGuardTests(waiting.WaitCase):
    def restart(self):
        self.engine.close()
        self.engine = Engine(self.config, self.paths, Gate(), core=FakeCore(), codex=self.codex, clock=lambda: self.now)
        self.addCleanup(self.engine.close)

    def test_restart_preserves_due_checkpoint_and_budget(self):
        self.begin(); saved = self.ledger().overload_wait()
        self.now += 7; self.restart()
        self.assertEqual(self.engine.tick()['retry_after'], 23)
        self.assertEqual(self.ledger().overload_wait(), saved)
        self.codex.finish_command(); self.advance(23)
        self.assertEqual(self.ledger().retry_info(self.seed['sha256'])['number'], 1)

    def test_pause_prevents_wait_promotion_until_resume(self):
        self.begin(); self.codex.finish_command(); self.engine.gate.set(False)
        self.advance(300)
        self.assertEqual(self.ledger().current()['stage'], 'overload_wait')
        self.assertEqual(self.codex.calls, 1)
        self.engine.gate.set(True)
        self.assertEqual(self.engine.tick()['retry_after'], 60)

    def test_restart_does_not_reset_missing_exit_deadline(self):
        self.begin(); self.codex.background = []; self.advance()
        saved = self.ledger().overload_wait()
        self.restart(); self.advance(120)
        self.assertEqual(self.ledger().current()['error'], 'overload_completion_unproven')
        self.assertEqual(self.ledger().overload_wait(), saved)

    def test_runtime_metrics_do_not_change_terminal_identity(self):
        self.codex.background[0].update(cpuPercent=75.0, rssKb=8000, osPid=123)
        self.begin()
        self.codex.background[0].update(cpuPercent=0.1, rssKb=12000)
        self.assertFalse(self.advance()['halted'])
        self.codex.finish_command()
        self.assertEqual(self.advance()['retry_after'], 60)

    def test_background_must_belong_to_exact_pending_item(self):
        self.codex.background[0]['itemId'] = 'unrelated-item'
        self.assertTrue(self.engine.tick()['halted'])
        self.assertEqual(self.engine.summary()['retry_blocked_reason'], 'overload_background_unproven')

    def test_process_identity_cannot_contradict_item(self):
        self.codex.effect['processId'] = 'another-process'
        self.assertTrue(self.engine.tick()['halted'])
        self.assertEqual(self.codex.calls, 1)

    def test_replaced_command_cannot_borrow_background_identity(self):
        self.codex.background[0]['command'] = 'foreign work'
        self.assertTrue(self.engine.tick()['halted'])

    def test_newer_manual_turn_blocks_observation(self):
        self.begin()
        self.codex.turns['manual'] = {'id': 'manual', 'status': 'completed'}
        self.assertTrue(self.advance()['halted'])
        self.assertEqual(self.codex.calls, 1)

    def test_active_work_is_preserved_without_dispatch_or_interrupt(self):
        self.begin(); self.codex.status = 'active'
        self.assertTrue(self.advance()['halted'])
        self.assertEqual(self.codex.calls, 1)
        self.assertEqual(self.codex.effect['status'], 'inProgress')

    def test_completed_item_cannot_regress_while_other_command_runs(self):
        self.begin()
        # Keep the known terminal alive for one more observation.
        self.codex.effect.update(status='completed', exitCode=0)
        self.assertFalse(self.advance()['halted'])
        self.codex.effect.update(status='inProgress', exitCode=None)
        self.assertTrue(self.advance()['halted'])

    def test_finished_item_output_cannot_change_after_being_bound(self):
        self.begin(); self.codex.effect.update(status='completed', exitCode=0)
        self.advance()
        self.codex.effect['aggregatedOutput'] = 'different terminal receipt'
        self.assertTrue(self.advance()['halted'])

    def test_new_tool_item_is_not_part_of_pending_work(self):
        self.begin()
        self.codex.turns['turn-1']['items'].append({'id': 'new', 'type': 'reasoning'})
        self.assertTrue(self.advance()['halted'])

    def test_original_receipt_change_blocks_promotion(self):
        self.begin(); self.codex.finish_command()
        directory = attempt_directory(self.paths, self.seed['sha256'], 0)
        receipt = json_read(directory/'attempt.json')
        json_write(directory/'attempt.json', {**receipt, 'unexpected': True})
        self.assertTrue(self.advance()['halted'])

    def test_changed_result_blocks_before_model_call(self):
        self.begin(); self.codex.finish_command()
        (self.exchange/'seed.zip').write_bytes(b'not the bound Result')
        with self.assertRaises(ControlError):
            self.advance()
        self.assertEqual(self.codex.calls, 1)

    def test_ambiguous_bundles_do_not_choose_a_winner(self):
        self.begin(); self.codex.finish_command()
        for n in range(2):
            package(self.exchange/f'output-{n}.zip', {'kind': 'patch', 'binding': self.binding, 'different': n})
        self.assertTrue(self.advance()['halted'])
        self.assertEqual(self.ledger().current()['error'], 'ambiguous_patch')
        self.assertIsNone(self.ledger().retry_info(self.seed['sha256']))

    def test_workspace_race_at_final_scheduling_cannot_rebaseline(self):
        self.begin(); self.codex.finish_command()
        original = self.codex.inspect_continuation
        def inspect(turn_id):
            live = original(turn_id)
            (self.dev/'partial.txt').write_text('changed during final guard')
            return live
        self.codex.inspect_continuation = inspect
        self.assertTrue(self.advance()['halted'])
        self.assertEqual(self.ledger().current()['error'], 'overload_checkpoint_changed')

    def test_workspace_race_during_source_validation_blocks(self):
        self.begin(); self.codex.finish_command()
        original = self.engine.exchange.assert_current
        seen = []
        def validate(*args):
            original(*args)
            seen.append(True)
            if len(seen) == 2:
                (self.dev/'partial.txt').write_text('changed at final source validation')
        self.engine.exchange.assert_current = validate
        self.assertTrue(self.advance()['halted'])
        self.assertEqual(self.codex.calls, 1)

    def test_pause_at_dispatch_after_wait_never_starts_model(self):
        self.begin(); self.codex.finish_command(); self.advance()
        original = self.codex.run
        def run(*args, **kwargs):
            self.engine.gate.set(False)
            return original(*args, **kwargs)
        self.codex.run = run
        self.advance(60)
        self.assertEqual(self.codex.calls, 1)
        self.assertEqual(self.ledger().current()['stage'], 'retry_wait')

    def test_bundle_at_dispatch_after_wait_has_priority(self):
        self.begin(); self.codex.finish_command(); self.advance()
        original = self.codex.run
        def run(*args, **kwargs):
            package(self.exchange/'late.zip', {'kind': 'patch', 'binding': self.binding})
            return original(*args, **kwargs)
        self.codex.run = run
        self.assertTrue(self.advance(60)['again'])
        self.assertEqual(self.codex.calls, 1)
        self.assertEqual(self.ledger().current()['stage'], 'waiting_result')

    def test_second_overload_wait_uses_next_attempt_and_exhausts_same_budget(self):
        self.config = replace(self.config, retry_delays_seconds=(60,))
        self.engine.config = self.config; self.codex.failures = 2
        self.begin(); self.codex.finish_command(); self.advance()
        self.codex.effect = {**self.codex.effect, 'status': 'inProgress', 'exitCode': None}
        self.codex.after_failure = lambda _: setattr(self.codex, 'background', [
            {'processId': 'second-process', 'itemId': self.codex.effect['id'],
             'command': self.codex.effect['command'], 'cwd': self.codex.effect['cwd']}])
        self.assertFalse(self.advance(60)['halted'])
        self.assertEqual(self.ledger().overload_wait()['number'], 1)
        self.codex.finish_command()
        self.assertTrue(self.advance()['halted'])
        self.assertEqual(self.engine.summary()['retry_blocked_reason'], 'retry_exhausted')
        self.assertEqual(self.codex.calls, 2)
        self.assertEqual(self.ledger().retry_info(self.seed['sha256'])['number'], 1)

    def test_corrupt_wait_metadata_is_a_concrete_block(self):
        self.begin()
        ledger = self.ledger()
        ledger.db.execute('UPDATE overload_waits SET evidence=?', ('{}',))
        self.assertTrue(self.advance()['halted'])
        self.assertEqual(self.ledger().current()['error'], 'invalid_overload_wait')

    def test_wait_migration_rolls_back_if_job_update_fails(self):
        ledger = self.ledger()
        ledger.db.execute("""CREATE TRIGGER refuse_wait BEFORE UPDATE ON jobs
            WHEN new.stage='overload_wait' BEGIN SELECT RAISE(ABORT, 'fixture'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.engine.tick()
        self.assertEqual(ledger.current()['stage'], 'running')
        self.assertIsNone(ledger.overload_wait())
        self.assertIsNone(ledger.db.execute("SELECT 1 FROM sqlite_master WHERE name='overload_waits'").fetchone())

    def test_wait_journal_exposes_deadline_without_command_output(self):
        output = io.StringIO()
        self.codex.effect['aggregatedOutput'] = 'SECRET FIXTURE'
        with contextlib.redirect_stderr(output):
            self.begin()
        records = [json.loads(line) for line in output.getvalue().splitlines()]
        event = next(row for row in records if row.get('decision') == 'observe_background')
        self.assertEqual(event['overload_check_at'], self.now+30)
        self.assertNotIn('SECRET FIXTURE', output.getvalue())

    def old_failure(self):
        self.codex.inspect_overload_wait = None
        self.engine.tick(); self.codex.finish_command()
        write_private(self.paths.config, render(self.config).encode())

    def test_repeated_modern_recovery_preserves_due_and_number(self):
        self.old_failure()
        with patch('specroad_control.commands.Engine', return_value=self.engine):
            first = recover(self.paths); second = recover(self.paths)
        self.assertFalse(second['recovered'])
        stored = self.ledger().retry_info(self.seed['sha256'])
        self.assertEqual(stored['due'], first['retry_at'])
        self.assertEqual(stored['number'], 1)
        self.assertEqual(self.codex.calls, 1)

    def test_modern_recovery_cannot_accept_a_later_turn(self):
        self.old_failure()
        self.codex.turns['foreign'] = {'id': 'foreign', 'status': 'failed'}
        with patch('specroad_control.commands.Engine', return_value=self.engine), self.assertRaises(ControlError):
            recover(self.paths)
        self.assertIsNone(self.ledger().retry_info(self.seed['sha256']))

    def test_modern_recovery_prefers_a_bound_bundle(self):
        self.old_failure()
        package(self.exchange/'ready.zip', {'kind': 'patch', 'binding': self.binding})
        with patch('specroad_control.commands.Engine', return_value=self.engine):
            result = recover(self.paths)
        self.assertEqual(result['stage'], 'waiting_result')
        self.assertIsNone(self.ledger().retry_info(self.seed['sha256']))

    def test_modern_recovery_adopts_bundle_published_during_final_proof(self):
        self.old_failure()
        original = self.codex.inspect_continuation
        seen = []
        def inspect(turn_id):
            live = original(turn_id)
            seen.append(True)
            if len(seen) == 2:
                package(self.exchange/'recovery-race.zip', {'kind': 'patch', 'binding': self.binding})
            return live
        self.codex.inspect_continuation = inspect
        with patch('specroad_control.commands.Engine', return_value=self.engine):
            result = recover(self.paths)
        self.assertEqual(result['stage'], 'waiting_result')
        self.assertIsNone(self.ledger().retry_info(self.seed['sha256']))

    def test_modern_recovery_rejects_reused_dispatch_number(self):
        self.old_failure()
        directory = attempt_directory(self.paths, self.seed['sha256'], 0)
        attempt = json_read(directory/'attempt.json')
        json_write(directory/'attempt.json', {**attempt, 'number': 1})
        with patch('specroad_control.commands.Engine', return_value=self.engine), self.assertRaises(ControlError):
            recover(self.paths)
        self.assertIsNone(self.ledger().retry_info(self.seed['sha256']))

    def test_missing_wait_record_never_resets_to_ready(self):
        self.begin()
        self.ledger().db.execute('DELETE FROM overload_waits')
        self.assertTrue(self.advance()['halted'])
        self.assertEqual(self.ledger().current()['error'], 'invalid_overload_wait')
        self.assertEqual(self.codex.calls, 1)

    def test_bundle_appearing_during_promotion_is_adopted(self):
        self.begin(); self.codex.finish_command()
        original = self.codex.inspect_continuation
        def inspect(turn_id):
            live = original(turn_id)
            if not (self.exchange/'race.zip').exists():
                package(self.exchange/'race.zip', {'kind': 'patch', 'binding': self.binding})
            return live
        self.codex.inspect_continuation = inspect
        self.assertTrue(self.advance()['again'])
        self.assertEqual(self.ledger().current()['stage'], 'waiting_result')
        self.assertIsNone(self.ledger().retry_info(self.seed['sha256']))
        self.assertEqual(self.codex.calls, 1)
