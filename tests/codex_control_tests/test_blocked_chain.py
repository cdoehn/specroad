"""Recovery advances only a proven correction chain and preserves blocked authority."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from specroad_control.apply_reconcile import enqueue, validate_history, public_status
from specroad_control.automation import Engine, Gate
from specroad_control.errors import ControlError
from specroad_control.local import json_write
from codex_control_tests.blocked_chain_support import BlockedChainCase, ReconcileCore, log_for
from codex_control_tests.automation_support import FakeCodex
from codex_control_tests.test_recovery import LedgerContext


class BlockedChainTests(BlockedChainCase):
    def queue(self):
        return enqueue(self.paths, self.final['path'], blocked=True)

    def engine(self, *, gate=None, codex=None):
        codex = codex or FakeCodex(self, 'no_work')
        if not hasattr(codex, 'activity'): codex.activity = lambda: 'idle'
        return Engine(self.config, self.paths, gate or Gate(), core=ReconcileCore(), codex=codex)

    def preserved(self):
        with LedgerContext(self.paths, self.config) as ledger:
            self.assertEqual((ledger.current()['sha'], ledger.current()['stage'], ledger.current()['error'], ledger.current()['patch_sha']),
                             (self.seed['sha256'], 'uncertain', 'dev_blocked', None))
            self.assertEqual(ledger.request_contract()['clarifications_remaining'], 2)
            self.assertIsNone(ledger.output_kind())
        self.assertFalse((self.codex_home / 'calls.jsonl').exists())

    def rejected(self):
        with self.assertRaises(ControlError): self.queue()
        self.preserved()

    def test_active_chat_can_queue_without_changing_claim_pause_or_original_receipts(self):
        self.settings(thread_status='active')
        originals = {p: p.read_bytes() for p in [self.paths.config, self.paths.state_file, *self.directory.iterdir()]}
        answer = self.queue()
        self.assertTrue(answer['queued'])
        self.assertFalse(answer['model_called'] or answer['service_started'] or answer['history_advanced'])
        self.assertEqual(originals, {p: p.read_bytes() for p in originals})
        self.assertEqual(public_status(self.paths)['result_sha256'], self.final['sha256'])
        self.preserved()

    def test_idle_adoption_preserves_blockade_seed_and_budget_then_dispatches_once(self):
        originals = {p: p.read_bytes() for p in self.directory.iterdir()}
        self.queue()
        with self.engine() as engine:
            self.assertTrue(engine.tick()['again'])
            self.assertEqual(engine.codex.calls, 0)
            with LedgerContext(self.paths, self.config) as ledger:
                self.assertEqual(ledger.current()['sha'], self.final['sha256'])
                self.assertEqual(ledger.seed_sha, self.seed['sha256'])
                self.assertEqual(ledger.request_contract(), {'version': 3, 'clarification_allowed': False,
                    'clarification_limit': 3, 'clarifications_remaining': 2})
                old = ledger.db.execute('SELECT stage,patch_sha,error FROM jobs WHERE sha=?', (self.seed['sha256'],)).fetchone()
                self.assertEqual(tuple(old), ('done', None, 'dev_blocked'))
                self.assertIsNone(ledger.db.execute('SELECT output_kind FROM request_contracts WHERE sha=?', (self.seed['sha256'],)).fetchone()[0])
                self.assertIsNone(validate_history(ledger))
            self.assertTrue(engine.tick()['halted']); self.assertTrue(engine.tick()['halted'])
            self.assertEqual(engine.codex.calls, 1)
        self.assertEqual(originals, {p: p.read_bytes() for p in originals})

    def test_without_explicit_queue_worker_does_not_infer_recovery(self):
        with self.engine() as engine:
            self.assertFalse(engine.tick()['again']); self.assertEqual(engine.codex.calls, 0)
        self.preserved()

    def test_active_thread_waits_without_model(self):
        self.queue(); codex = FakeCodex(self); codex.activity = lambda: 'active'
        with self.engine(codex=codex) as engine:
            self.assertEqual(engine.tick()['retry_after'], 2); self.assertEqual(codex.calls, 0)
        self.preserved()

    def test_pause_preserves_pending_recovery(self):
        self.queue(); gate = Gate(); gate.set(False)
        with self.engine(gate=gate) as engine: self.assertFalse(engine.tick()['again'])
        self.preserved()

    def test_repeat_same_intent_is_idempotent(self):
        self.assertEqual(self.queue(), self.queue())
        with LedgerContext(self.paths, self.config) as ledger:
            self.assertEqual(len(ledger.db.execute('SELECT * FROM apply_reconciliations').fetchall()), 1)

    def test_old_command_does_not_accept_blocked_correction_chain(self):
        with self.assertRaises(ControlError): enqueue(self.paths, self.final['path'])
        self.preserved()

    def test_missing_original_patch_blocks(self):
        Path(self.original['path']).unlink(); self.rejected()

    def test_second_original_patch_blocks(self):
        from codex_control_tests.apply_reconcile_support import patch_package
        other = deepcopy(self.original_data); other['bundle_number'] = '009'
        patch_package(self.exchange / 'other.zip', other); self.rejected()

    def test_second_failure_result_blocks(self):
        self.result('other.zip', previous=self.seed, patch_sha=self.original['sha256'], success=False)
        self.rejected()

    def test_changed_program_blocks(self):
        self.create_output(extra='print("unreviewed")\n'); self.rejected()

    def test_wrong_preimage_blocks(self):
        self.resumed_data['stages'][0]['before']['src/example.py'] = '0' * 64
        self.create_output(); self.rejected()

    def test_omitted_mandatory_test_blocks(self):
        self.resumed_data['stages'][1]['test_plan']['test_files'] = []
        self.create_output(); self.rejected()

    def test_omitted_commit_blocks(self):
        self.resumed_data['stages'].pop(); self.create_output(); self.rejected()

    def test_checkpoint_prefix_must_have_passing_gates(self):
        self.create_checkpoint(log=log_for(self.original_data, ['d' * 40], failed=True).replace(b'"tests":10', b'"tests":0'))
        self.create_output(); self.rejected()

    def test_final_snapshot_must_account_for_all_files(self):
        self.final_files['src/unexplained.py'] = b'unknown = True\n'
        self.create_output(); self.rejected()

    def test_newer_result_blocks(self):
        self.result('later.zip', captured_at='2026-01-01T03:00:00Z'); self.rejected()

    def test_archiving_all_inputs_keeps_pinned_proof_valid(self):
        self.queue(); archive = self.exchange / 'PatchHarbor-Archive'; archive.mkdir()
        for fact in (self.seed, self.original, self.checkpoint, self.resumed, self.final):
            p = Path(fact['path']); p.rename(archive / p.name)
        with self.engine() as engine: self.assertTrue(engine.tick()['again'])

    def test_modified_original_completion_blocks_adoption(self):
        self.queue(); json_write(self.directory / 'completion.json', {**self.answer, 'message': 'Different'})
        with self.engine() as engine:
            with self.assertRaises(ControlError): engine.tick()
            self.assertEqual(engine.codex.calls, 0)
        self.preserved()

    def test_partial_transaction_failure_rolls_back_new_claim_and_receipt(self):
        self.queue()
        from specroad_control import apply_reconcile_history as history
        original = history.adopt_blocked
        def failure(ledger, source):
            original(ledger, source)
            import sqlite3
            raise sqlite3.OperationalError('simulated storage failure')
        with self.engine() as engine, patch.object(history, 'adopt_blocked', failure):
            with self.assertRaises(ControlError) as caught: engine.tick()
        self.assertEqual(caught.exception.code, 'apply_reconciliation_persist_failed'); self.preserved()
        with LedgerContext(self.paths, self.config) as ledger:
            self.assertIsNotNone(validate_history(ledger))
            self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0], 1)
