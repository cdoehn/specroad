"""Configuration races, interrupted writes and live requests fail without lost work."""
from contextlib import closing
from dataclasses import replace
from unittest.mock import patch

from codex_control_tests.automation_support import AutomationCase
from codex_control_tests.test_start_current import configure_start_case
from specroad_control import budget_config
from specroad_control.config import load, render
from specroad_control.correction_budget import bind, read, require_available
from specroad_control.errors import ControlError
from specroad_control.job_contract import new_contract, scope
from specroad_control.ledger import Ledger
from specroad_control.local import json_write, lock, read_private, write_private
from specroad_control.start_current import enqueue, active_cycle, ACTIVE


class BudgetConfigRightTests(AutomationCase):
    setUp = configure_start_case

    def change(self, **values):
        with patch('specroad_control.ipc.request', return_value={'ok': True}):
            return budget_config.configure(self.paths, **values)

    def test_invalid_values_never_change_file_or_issue_ipc(self):
        original = read_private(self.paths.config)
        invalid = [0, -1, True, 1.5, '30', 1 << 63]
        with patch('specroad_control.ipc.request', side_effect=AssertionError('invalid write')):
            for name in ('clarification_limit', 'correction_limit'):
                for value in invalid:
                    with self.subTest(name=name, value=value), self.assertRaises(ControlError):
                        budget_config.configure(self.paths, **{name: value})
            for value in (0, 1, 'true'):
                with self.subTest(value=value), self.assertRaises(ControlError):
                    budget_config.configure(self.paths, clarification_allowed=value)
            with self.assertRaises(ControlError):
                budget_config.configure(self.paths, worker_limit=12)
        self.assertEqual(read_private(self.paths.config), original)

    def test_existing_operation_lock_rejects_competitor_without_lost_update(self):
        original = read_private(self.paths.config)
        with lock(self.paths.state / 'operation.lock'), self.assertRaises(ControlError) as raised:
            self.change(correction_limit=31)
        self.assertEqual(raised.exception.code, 'already_running')
        self.assertEqual(read_private(self.paths.config), original)
        self.change(correction_limit=31)
        self.change(clarification_limit=37)
        self.assertEqual((load(self.paths).correction_limit, load(self.paths).clarification_limit), (31, 37))

    def test_interruption_before_atomic_replace_keeps_previous_file_and_ledger(self):
        original = read_private(self.paths.config)
        ledger = self.paths.ledger.read_bytes()
        with patch('specroad_control.local.os.replace', side_effect=OSError('injected storage error')):
            with self.assertRaises(OSError):
                self.change(correction_limit=38)
        self.assertEqual(read_private(self.paths.config), original)
        self.assertEqual(self.paths.ledger.read_bytes(), ledger)

    def test_detected_external_edit_is_preserved_instead_of_overwritten(self):
        external = render(replace(self.config, correction_limit=41)).encode()
        actual = budget_config.parse
        def parse_then_edit(*args, **kwargs):
            parsed = actual(*args, **kwargs)
            write_private(self.paths.config, external)
            return parsed
        with patch.object(budget_config, 'parse', side_effect=parse_then_edit), self.assertRaises(ControlError) as raised:
            self.change(clarification_limit=39)
        self.assertEqual(raised.exception.code, 'configuration_changed')
        self.assertEqual(read_private(self.paths.config), external)

    def test_missing_file_and_corrupt_file_never_fall_back_to_unbound_defaults(self):
        original = read_private(self.paths.config)
        ledger = self.paths.ledger.read_bytes()
        for raw in (None, b'[automation\ninvalid'):
            if raw is None:
                self.paths.config.unlink()
            else:
                write_private(self.paths.config, raw)
            with self.subTest(raw=raw), self.assertRaises(ControlError):
                self.engine.tick()
            with self.assertRaises(ControlError):
                self.change(correction_limit=30)
            self.assertEqual(self.paths.ledger.read_bytes(), ledger)
            self.assertEqual(self.codex.calls, 0)
            if raw is not None:
                self.assertEqual(read_private(self.paths.config), raw)
            write_private(self.paths.config, original)

    def test_damaged_cycle_override_does_not_silently_lose_invocation_priority(self):
        enqueue(self.paths, self.config, overrides={'clarification_limit': 35})
        self.engine.tick()
        cycle = active_cycle(self.paths)
        json_write(self.paths.state / ACTIVE, {**cycle, 'overrides': {'clarification_limit': '35'}})
        with self.assertRaises(ControlError):
            budget_config.status(self.paths)
        with self.assertRaises(ControlError):
            self.engine.tick()
        self.assertEqual(self.codex.calls, 0)

    def test_conflicting_start_override_cannot_replace_an_already_pending_request(self):
        first = enqueue(self.paths, self.config, overrides={'correction_limit': 35})
        self.assertEqual(enqueue(self.paths, self.config, overrides={'correction_limit': 35}), first)
        with self.assertRaises(ControlError):
            enqueue(self.paths, self.config, overrides={'correction_limit': 36})
        self.engine.tick()
        self.assertEqual(active_cycle(self.paths)['overrides'], {'correction_limit': 35})

    def test_policy_change_during_native_preflight_is_visible_before_dispatch(self):
        enqueue(self.paths, self.config)
        self.engine.tick()
        actual = self.core.call.side_effect
        def delayed_preflight(*args):
            self.change(clarification_allowed=False, correction_limit=39)
            return actual(*args)
        self.core.call.side_effect = delayed_preflight
        self.engine.tick()
        self.assertEqual(self.engine.summary()['budget_policy']['effective']['correction_limit'], 39)
        self.assertFalse(self.engine.config.clarification_allowed)
        with closing(Ledger(self.paths.ledger, scope(self.config))) as ledger:
            self.assertEqual(ledger.request_contract(), new_contract(20, version=4, limit=20))
        self.assertEqual(self.codex.calls, 1)

    def test_change_during_dev_turn_does_not_rewrite_attempt_or_prompt(self):
        enqueue(self.paths, self.config)
        self.engine.tick()
        original = self.codex.run
        captured = []
        def during_turn(prompt, schema, directory, **kwargs):
            before = read_private(directory / 'attempt.json')
            self.change(clarification_limit=49, correction_limit=59, clarification_allowed=False)
            captured.append((before, read_private(directory / 'attempt.json')))
            return original(prompt, schema, directory, **kwargs)
        self.codex.run = during_turn
        self.engine.tick()
        self.assertEqual(len(captured), 1)
        self.assertEqual(*captured[0])
        self.assertEqual(self.codex.calls, 1)

    def test_raising_limit_preserves_proven_exhausted_correction_sequence(self):
        target = self.paths.state / 'exhausted.sqlite3'
        previous = self.result('failed-first.zip', operation='apply', success=False, dirty=True, entrypoint_started=True)
        with closing(Ledger(target, scope(self.config), initial=previous)) as ledger:
            ledger.bind_contract(new_contract(0, allowed=False, version=4, limit=20))
            bind(ledger, previous, 1)
            ledger.change('waiting_result', patch_sha='1' * 64, output_kind='patch_ready')
            following = self.result('failed-repair.zip', previous=previous, patch_sha='1' * 64, success=False, dirty=True)
            ledger.enqueue(following, decision_evidence={'verified': True}, correction_limit=1)
        before = target.read_bytes()
        self.change(correction_limit=99)
        with closing(Ledger(target, scope(self.config))) as ledger:
            value = read(ledger, following['sha256'])
            self.assertEqual((value['maximum'], value['remaining']), (1, 0))
            with self.assertRaises(ControlError) as raised:
                require_available(value)
        self.assertEqual(raised.exception.code, 'correction_budget_exhausted')
        self.assertEqual(target.read_bytes(), before)

    def test_persisted_policy_is_not_reported_as_rolled_back_when_worker_is_offline(self):
        with patch('specroad_control.ipc.request', side_effect=ControlError('not_running', 'offline')):
            result = budget_config.configure(self.paths, correction_limit=31)
        self.assertTrue(result['saved'])
        self.assertEqual(result['worker_notification'], 'not_running')
        self.assertEqual(load(self.paths).correction_limit, 31)
        self.assertEqual(result['effective'], budget_config.status(self.paths)['effective'])
