"""Explicit operator grants affect one future source, not old attempts or budgets."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch

from specroad_control.clarification_authorization_history import validate_history
from specroad_control.errors import ControlError
from specroad_control.job_contract import new_contract
from specroad_control.local import json_write, read_private
from codex_control_tests.authorization_support import AuthorizationCase
from codex_control_tests.apply_reconcile_support import patch_package


class ClarificationAuthorizationTests(AuthorizationCase):
    def test_explicit_intent_does_not_advance_history_or_start_work(self):
        self.manual()
        old = self.ledger().current()
        answer = self.authorize()
        self.assertTrue(answer['queued'])
        self.assertFalse(answer['history_advanced'])
        self.assertFalse(answer['model_called'])
        self.assertFalse(answer['service_started'])
        self.assertEqual(self.ledger().current(), old)
        self.assertEqual(self.ledger().request_contract(), new_contract(2, allowed=False))
        self.assertEqual(self.codex.calls, 0)

    def test_new_source_gets_v4_with_exact_old_budget(self):
        self.manual(1)
        old = self.ledger().current()
        self.authorize()
        self.engine.gate.set(True)
        self.assertTrue(self.engine.tick()['again'])
        ledger = self.ledger()
        self.assertEqual(ledger.current()['sha'], self.following['sha256'])
        self.assertEqual(ledger.request_contract(), new_contract(1, version=4))
        self.assertEqual(ledger.request_contract(old['sha']), new_contract(1, allowed=False))
        archived = ledger.db.execute('SELECT * FROM jobs WHERE sha=?', (old['sha'],)).fetchone()
        self.assertEqual(archived['error'], old['error'])
        self.assertEqual(archived['patch_sha'], old['patch_sha'])
        self.assertEqual(ledger.db.execute('SELECT output_kind FROM request_contracts WHERE sha=?', (old['sha'],)).fetchone()[0], 'unknown')
        self.assertEqual(self.codex.calls, 0)
        self.assertIsNone(validate_history(ledger))

    def test_pause_and_active_thread_preserve_pending_intent(self):
        self.manual(); self.authorize()
        self.assertFalse(self.engine.tick()['again'])
        self.engine.gate.set(True)
        self.codex.activity.return_value = 'active'
        for _ in range(2):
            self.assertFalse(self.engine.tick()['again'])
        self.assertEqual(self.ledger().current()['sha'], self.seed['sha256'])
        self.assertEqual(self.codex.calls, 0)
        self.codex.activity.return_value = 'idle'
        self.assertTrue(self.engine.tick()['again'])

    def test_same_request_is_idempotent_before_and_after_adoption(self):
        self.manual(); first = self.authorize()
        self.assertEqual(first, self.authorize())
        self.engine.gate.set(True); self.engine.tick()
        reply = self.authorize()
        self.assertTrue(reply['completed']); self.assertFalse(reply['queued'])
        self.assertEqual(self.ledger().db.execute('SELECT COUNT(*) FROM clarification_authorizations').fetchone()[0], 1)

    def test_unresolved_turn_is_archived_without_rewriting_attempt(self):
        self.manual()
        ledger = self.ledger()
        ledger.db.execute("UPDATE jobs SET stage='uncertain',patch_sha=NULL,error='codex_turn_failed' WHERE sha=?", (self.seed['sha256'],))
        ledger.db.execute('UPDATE request_contracts SET output_kind=NULL WHERE sha=?', (self.seed['sha256'],))
        path = self.paths.state / 'jobs' / self.seed['sha256'] / 'attempt.json'
        json_write(path, {'source_sha256': self.seed['sha256'], 'thread_id': self.thread,
                         'request_contract': new_contract(2, allowed=False)})
        raw = read_private(path)
        self.authorize(); self.engine.gate.set(True); self.engine.tick()
        self.assertEqual(read_private(path), raw)
        self.assertEqual(ledger.db.execute('SELECT stage,error,patch_sha FROM jobs WHERE sha=?', (self.seed['sha256'],)).fetchone()[:],
                         ('done', 'codex_turn_failed', None))
        self.assertEqual(self.ledger().request_contract(), new_contract(2, version=4))

    def test_authorization_does_not_make_a_clarification_commit_mandatory(self):
        self.manual(); self.authorize()
        self.engine.gate.set(True); self.engine.tick()
        selected = self.ledger().request_contract()
        from specroad_control.job_contract import schema_for
        statuses = schema_for(selected)['properties']['status']['enum']
        self.assertIn('patch_ready', statuses)
        self.assertIn('patch_ready_with_clarification', statuses)
        self.assertNotIn('spec_clarification', statuses)

    def test_next_turn_receives_optional_clarification_authority(self):
        from codex_control_tests.mixed_support import postimage
        self.manual(); self.authorize()
        self.engine.gate.set(True); self.engine.tick()
        self.files = postimage(self.files, self.latest_data['stages'])
        self.assertFalse(self.dispatch(mixed=True)['halted'])
        self.assertEqual(self.codex.calls, 1)
        self.assertEqual(self.ledger().output_kind(), 'patch_ready_with_clarification')
        self.assertEqual(self.ledger().request_contract(), new_contract(2, version=4))

    def test_no_explicit_intent_keeps_old_permission_denied(self):
        self.manual(); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(), new_contract(2, allowed=False))

    def test_zero_budget_cannot_be_replenished_by_operator_command(self):
        self.manual(0)
        with self.assertRaises(ControlError): self.authorize()
        self.assertEqual(self.ledger().request_contract(), new_contract(0, allowed=False))

    def test_failed_or_incomplete_apply_does_not_authorize(self):
        self.manual(completed=1)
        with self.assertRaises(ControlError): self.authorize()
        self.assertIsNone(validate_history(self.ledger()))

    def test_mixed_manual_bundle_does_not_masquerade_as_normal_work(self):
        self.manual(mixed=True)
        with self.assertRaises(ControlError): self.authorize()
        self.assertIsNone(validate_history(self.ledger()))

    def test_snapshot_must_match_all_completed_payloads(self):
        self.manual(mutate_base=lambda files: files | {'src/example.py': b'forged\n'})
        with self.assertRaises(ControlError): self.authorize()

    def test_ambiguous_manual_bundles_are_not_selected_by_filename(self):
        self.manual()
        other = deepcopy(self.latest_data); other['bundle_number'] = '999'
        patch_package(self.exchange / 'other.zip', other)
        with self.assertRaises(ControlError): self.authorize()

    def test_wrong_source_and_relative_result_are_rejected(self):
        self.manual()
        for changes in ({'source_sha256': '0'*64}, {'result': Path(self.following['path']).name}):
            with self.subTest(changes=changes), self.assertRaises(ControlError): self.authorize(**changes)

    def test_different_repeat_cannot_replace_original_intent(self):
        self.manual(); self.authorize()
        proof = validate_history(self.ledger())
        with self.assertRaises(ControlError): self.authorize(reason='different reason')
        self.assertEqual(validate_history(self.ledger()), proof)

    def test_missing_old_budget_is_not_invented(self):
        self.manual()
        ledger = self.ledger()
        ledger.db.execute('DELETE FROM clarification_budgets')
        ledger.db.execute('UPDATE request_contracts SET version=2')
        with self.assertRaises(ControlError): self.authorize()
        self.assertEqual(self.ledger().request_contract(), {'version': 2, 'clarification_allowed': False})

    def test_unknown_thread_activity_cannot_queue(self):
        self.manual()
        self.codex.activity.side_effect = ControlError('unknown_thread', 'No reliable activity proof')
        with self.assertRaises(ControlError): self.authorize()
        self.assertIsNone(validate_history(self.ledger()))


def test_cli_requires_explicit_binding_and_reason():
    from specroad_control.cli import main
    with patch('specroad_control.cli.Paths.discover') as discover:
        for args in (['authorize-clarification'], ['status', '--reason', 'grant'], ['status', '--source-sha256', 'a'*64]):
            try:
                main(args)
            except SystemExit as exc:
                assert exc.code == 2
            else:
                raise AssertionError('CLI accepted incomplete or misplaced authorization')
        discover.assert_not_called()
