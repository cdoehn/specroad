"""The explicit current-state action preserves limits while ending old chains."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from specroad_control.current_acceptance_history import validate_history
from specroad_control.errors import ControlError
from specroad_control.job_contract import new_contract
from specroad_control.local import json_write, read_private
from codex_control_tests.current_acceptance_support import AcceptanceCase
from codex_control_tests.apply_reconcile_support import patch_package


class CurrentAcceptanceTests(AcceptanceCase):
    def test_offline_intent_preserves_old_job_and_starts_nothing(self):
        self.manual(); before = self.ledger().current()
        reply = self.accept_current()
        self.assertTrue(reply['queued'])
        self.assertFalse(reply['history_advanced'])
        self.assertFalse(reply['model_called'])
        self.assertFalse(reply['service_started'])
        self.assertEqual(before, self.ledger().current())
        self.assertEqual(self.codex.calls, 0)

    def test_adoption_preserves_budget_error_and_unknown_output(self):
        self.manual(1)
        ledger = self.ledger()
        ledger.db.execute("UPDATE jobs SET error='manual_recovery_required' WHERE sha=?", (self.seed['sha256'],))
        self.adopt()
        ledger = self.ledger()
        self.assertEqual(ledger.current()['sha'], self.following['sha256'])
        self.assertEqual(ledger.request_contract(), new_contract(1, version=4))
        self.assertEqual(ledger.request_contract(self.seed['sha256']), new_contract(1, allowed=False, version=4))
        old = ledger.db.execute('SELECT * FROM jobs WHERE sha=?', (self.seed['sha256'],)).fetchone()
        self.assertEqual((old['stage'], old['error']), ('done', 'manual_recovery_required'))
        self.assertEqual(ledger.output_kind(self.seed['sha256']), 'unknown')

    def test_pause_and_active_chat_delay_adoption(self):
        self.manual(); self.accept_current()
        self.assertFalse(self.engine.tick()['again'])
        self.engine.gate.set(True); self.codex.activity.return_value = 'active'
        self.assertFalse(self.engine.tick()['again'])
        self.assertEqual(self.ledger().current()['sha'], self.seed['sha256'])
        self.codex.activity.return_value = 'idle'
        self.assertTrue(self.engine.tick()['again'])
        self.assertEqual(self.codex.calls, 0)

    def test_repetition_is_idempotent_before_and_after_adoption(self):
        self.manual(); first = self.accept_current()
        self.assertEqual(first, self.accept_current())
        self.adopt()
        self.assertTrue(self.accept_current()['completed'])
        self.assertEqual(self.ledger().db.execute('SELECT COUNT(*) FROM current_acceptances').fetchone()[0], 1)

    def test_changed_operator_intent_cannot_replace_receipt(self):
        self.manual(); self.accept_current()
        before = validate_history(self.ledger())
        for change in ({'clarification': False}, {'reason': 'different operator intent'}):
            with self.subTest(change=change), self.assertRaises(ControlError): self.accept_current(**change)
        self.assertEqual(validate_history(self.ledger()), before)

    def test_clarification_is_explicit_and_normal_work_remains_valid(self):
        self.manual(); self.adopt(clarification=False)
        self.assertEqual(self.ledger().request_contract(), new_contract(2, allowed=False, version=4))
        self.assertFalse(self.dispatch()['halted'])
        self.assertEqual(self.codex.calls, 1)
        self.assertEqual(self.ledger().output_kind(), 'patch_ready')

    def test_optional_mixed_handoff_uses_separate_attempt_and_full_gate_reset(self):
        self.manual(); self.adopt()
        self.assertFalse(self.dispatch(mixed=True)['halted'])
        ledger = self.ledger()
        directory = ledger.attempt_directory(self.paths, self.following['sha256'], 0)
        self.assertEqual(directory.parent.name, 'accepted')
        self.assertEqual(ledger.output_kind(), 'patch_ready_with_clarification')
        self.outcome(); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(), new_contract(3, version=4))

    def test_failed_mixed_handoff_consumes_only_one_slot(self):
        self.manual(); self.adopt(); self.dispatch(mixed=True)
        self.outcome(completed=1); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(), new_contract(1, allowed=False, version=4))

    def test_zero_budget_still_allows_clear_work_without_grant(self):
        self.manual(0)
        with self.assertRaises(ControlError): self.accept_current()
        self.adopt(clarification=False)
        self.assertEqual(self.ledger().request_contract(), new_contract(0, allowed=False, version=4))

    def test_unissued_same_result_can_receive_optional_clarification(self):
        self.manual(); self.engine.tick()  # Adopt an unclassified manual result, still paused.
        old = self.ledger().recorded_contract()
        self.adopt()
        self.assertEqual(self.ledger().recorded_contract(), old)
        self.assertEqual(self.ledger().request_contract(), new_contract(2, version=4))
        self.assertFalse(self.dispatch(mixed=True)['halted'])

    def test_completed_patchless_blocker_is_reissued_without_overwriting_evidence(self):
        self.manual(); self.engine.tick(); self.block_current()
        directory = self.paths.state / 'jobs' / self.following['sha256']
        originals = {p.name: read_private(p) for p in directory.iterdir() if p.is_file()}
        self.adopt()
        self.assertFalse(self.dispatch(mixed=True)['halted'])
        self.assertTrue(originals)
        self.assertEqual(originals, {name: read_private(directory / name) for name in originals})

    def test_manual_mixed_bundle_can_be_accepted_with_an_explicit_receipt(self):
        self.manual(mixed=True); self.adopt()
        self.assertEqual(self.ledger().request_contract(), new_contract(2, version=4))
        self.assertEqual(self.ledger().output_kind(self.seed['sha256']), 'unknown')

    def test_last_correction_and_immediate_dirty_preimage_suffice(self):
        self.manual(completed=1)
        original = self.latest_patch
        parent = self.external_correction()
        Path(self.seed['path']).unlink(); Path(original['path']).unlink()
        self.adopt()
        self.assertEqual(self.ledger().current()['sha'], self.following['sha256'])
        self.assertTrue(Path(parent['path']).is_file())
        self.assertEqual(self.ledger().request_contract(), new_contract(2, version=4))

    def test_completed_snapshot_must_match_every_tested_stage(self):
        self.manual(mutate_base=lambda files: files | {'src/example.py': b'forged\n'})
        with self.assertRaises(ControlError): self.accept_current()

    def test_failed_apply_is_not_an_accepted_baseline(self):
        self.manual(completed=1)
        with self.assertRaises(ControlError): self.accept_current()
        self.assertIsNone(validate_history(self.ledger()))

    def test_missing_immediate_preimage_blocks_without_advancing_history(self):
        self.manual(); Path(self.seed['path']).unlink()
        with self.assertRaises(ControlError): self.accept_current()
        self.assertEqual(self.ledger().current()['sha'], self.seed['sha256'])

    def test_existing_followup_blocks_a_second_handoff(self):
        self.manual()
        data = self.data(self.following)
        patch_package(self.exchange / 'already.zip', data)
        with self.assertRaises(ControlError): self.accept_current()

    def test_live_repository_lock_or_change_blocks_the_receipt(self):
        self.manual()
        self.engine.core.current.side_effect = ControlError('core_rejected', 'Apply is active or changed')
        with self.assertRaises(ControlError): self.accept_current()
        self.assertIsNone(validate_history(self.ledger()))

    def test_active_ledger_claim_is_never_archived(self):
        self.manual()
        self.ledger().db.execute("UPDATE jobs SET stage='running' WHERE sha=?", (self.seed['sha256'],))
        with self.assertRaises(ControlError): self.accept_current()

    def test_missing_old_budget_and_unknown_thread_state_block(self):
        self.manual()
        self.codex.activity.side_effect = ControlError('thread_unknown', 'No reliable thread state')
        with self.assertRaises(ControlError): self.accept_current()
        self.codex.activity.side_effect = None
        self.ledger().db.execute('DELETE FROM clarification_budgets')
        with self.assertRaises(ControlError): self.accept_current()

    def test_late_config_change_prevents_adoption(self):
        self.manual(); self.accept_current()
        self.paths.config.write_text(self.paths.config.read_text() + '\n# changed\n')
        self.engine.gate.set(True)
        with self.assertRaises(ControlError): self.engine.tick()
        self.assertEqual(self.ledger().current()['sha'], self.seed['sha256'])


def test_current_acceptance_cli_requires_explicit_result_reason_and_correct_command():
    from specroad_control.cli import main
    with patch('specroad_control.cli.Paths.discover') as discover:
        for args in (['accept-current'], ['accept-current', '--result', '/x.zip'],
                     ['status', '--clarification'], ['resume', '--clarification'],
                     ['accept-current', '--result', '/x.zip', '--reason', 'accept', '--retry-blocked']):
            try:
                main(args)
            except SystemExit as exc:
                assert exc.code == 2
            else:
                raise AssertionError('Incomplete or misplaced acceptance was allowed')
        discover.assert_not_called()
