"""Behavioral acceptance of explicit same-source authority and exactly one output."""
from unittest.mock import patch

from specroad_control.blocked_authorization_history import validate_history
from specroad_control.errors import ControlError
from specroad_control.job_contract import new_contract
from specroad_control.local import json_read, read_private
from codex_control_tests.apply_reconcile_support import patch_package
from codex_control_tests.blocked_authorization_support import BlockedAuthorizationCase


class BlockedClarificationAuthorizationTests(BlockedAuthorizationCase):
    def test_intent_does_not_start_work_change_contract_or_budget(self):
        self.blocked(); old = self.ledger().current()
        self.codex.activity.return_value = 'active'
        answer = self.grant()
        self.assertTrue(answer['queued'])
        self.assertFalse(answer['model_called']); self.assertFalse(answer['service_started'])
        self.assertEqual(self.ledger().current(), old)
        self.assertEqual(self.ledger().request_contract(), new_contract(2, allowed=False, version=4))
        self.assertEqual(self.codex.calls, 0)

    def test_pause_and_active_thread_keep_intent_without_replaying(self):
        self.blocked(); self.grant(); self.engine.gate.set(False)
        self.assertFalse(self.engine.tick()['again'])
        self.engine.gate.set(True); self.codex.activity.return_value = 'active'
        self.assertFalse(self.engine.tick()['again'])
        self.assertEqual(self.ledger().current()['stage'], 'uncertain')
        self.codex.activity.return_value = 'idle'
        self.assertTrue(self.engine.tick()['again'])
        self.assertEqual(self.ledger().current()['sha'], self.seed['sha256'])
        self.assertEqual(self.codex.calls, 0)

    def test_new_attempt_keeps_original_files_and_original_authority(self):
        self.blocked()
        root = self.paths.state / 'jobs' / self.seed['sha256']
        old = {p.name: read_private(p) for p in root.iterdir() if p.is_file()}
        self.grant(); self.engine.tick()
        self.assertFalse(self.dispatch(mixed=True)['halted'])
        ledger = self.ledger()
        self.assertEqual(ledger.recorded_contract(), new_contract(2, allowed=False, version=4))
        self.assertEqual(ledger.request_contract(), new_contract(2, version=4))
        self.assertEqual(ledger.output_kind(), 'patch_ready_with_clarification')
        self.assertEqual({name: read_private(root / name) for name in old}, old)
        new = json_read(root / 'authorized/0000/attempt.json')
        self.assertEqual(new['request_contract'], new_contract(2, version=4))
        self.assertEqual(self.codex.calls, 1)

    def test_normal_implementation_without_clarification_remains_allowed(self):
        self.adopted()
        self.assertFalse(self.dispatch()['halted'])
        self.assertEqual(self.ledger().output_kind(), 'patch_ready')
        self.assertEqual(self.codex.calls, 1)

    def test_idempotent_command_never_requeues_an_already_dispatched_attempt(self):
        self.blocked(); first = self.grant()
        self.assertEqual(self.grant(), first)
        self.engine.tick(); self.dispatch(mixed=True)
        old = self.ledger().current()
        self.assertTrue(self.grant()['completed'])
        self.assertEqual(self.ledger().current(), old)
        self.assertEqual(self.ledger().db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0], 1)
        self.assertEqual(self.codex.calls, 1)

    def test_mixed_failure_consumes_one_place_without_erasing_old_budget(self):
        self.adopted(); self.dispatch(mixed=True)
        self.outcome(completed=1)
        self.engine.tick()
        self.assertEqual(self.ledger().request_contract()['clarifications_remaining'], 1)
        self.assertFalse(self.ledger().request_contract()['clarification_allowed'])
        self.assertEqual(self.ledger().recorded_contract(self.seed['sha256'])['clarifications_remaining'], 2)

    def test_complete_normal_apply_renews_budget_only_on_its_successor(self):
        self.adopted(); self.dispatch(); self.outcome()
        self.engine.tick()
        self.assertEqual(self.ledger().request_contract(), new_contract(3, version=4))
        self.assertEqual(self.ledger().recorded_contract(self.seed['sha256'])['clarifications_remaining'], 2)

    def test_without_explicit_intent_blocked_stays_blocked(self):
        self.blocked()
        self.assertTrue(self.engine.tick()['halted'])
        self.assertEqual(self.codex.calls, 0)

    def test_zero_budget_is_not_replenished(self):
        self.blocked(remaining=0)
        with self.assertRaises(ControlError): self.grant()
        self.assertIsNone(validate_history(self.ledger()))

    def test_existing_authority_cannot_fund_another_attempt(self):
        self.blocked(allowed=True)
        with self.assertRaises(ControlError): self.grant()

    def test_existing_patch_takes_priority_over_new_attempt(self):
        self.blocked()
        patch_package(self.exchange / 'existing.zip', self.data())
        with self.assertRaises(ControlError): self.grant()
        self.assertIsNone(validate_history(self.ledger()))

    def test_patch_appearing_after_intent_blocks_adoption(self):
        self.blocked(); self.grant()
        patch_package(self.exchange / 'late.zip', self.data())
        with self.assertRaises(ControlError): self.engine.tick()
        self.assertEqual(self.ledger().current()['stage'], 'uncertain')
        self.assertEqual(self.codex.calls, 0)

    def test_wrong_source_and_unknown_activity_do_not_queue(self):
        self.blocked()
        with self.assertRaises(ControlError): self.grant(source_sha256='0' * 64)
        self.codex.activity.side_effect = ControlError('unknown_thread', 'unknown')
        with self.assertRaises(ControlError): self.grant()
        self.assertIsNone(validate_history(self.ledger()))

    def test_changed_reason_cannot_replace_an_existing_grant(self):
        self.blocked(); self.grant(); old = validate_history(self.ledger())
        with self.assertRaises(ControlError): self.grant(reason='changed')
        self.assertEqual(validate_history(self.ledger()), old)


def test_retry_blocked_flag_is_exclusive_to_complete_authorization_command():
    from specroad_control.cli import main
    with patch('specroad_control.cli.Paths.discover') as discover:
        for args in (['status', '--retry-blocked'], ['authorize-clarification', '--retry-blocked']):
            try:
                main(args)
            except SystemExit as exc:
                assert exc.code == 2
            else:
                raise AssertionError('Incomplete or misplaced authority flag accepted')
        discover.assert_not_called()
