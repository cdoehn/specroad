"""An explicit recovery can preserve a pending claim across a manual Apply restart."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

from specroad_control.automation import Engine, Gate
from specroad_control.apply_reconcile import enqueue, validate_history, public_status
from specroad_control.apply_reconcile_proof import prove
from specroad_control.errors import ControlError
from specroad_control.local import json_write
from codex_control_tests.apply_reconcile_support import ReconcileCase, ReconcileCore, progress_log
from codex_control_tests.automation_support import FakeCodex, FakeCore, package
from codex_control_tests.test_recovery import LedgerContext


class ApplyReconciliationTests(ReconcileCase):
    def queue(self):
        return enqueue(self.paths, self.final['path'])

    def engine(self, gate=None, codex=None):
        codex = codex or FakeCodex(self, 'no_work')
        if not hasattr(codex, 'activity'):
            codex.activity = lambda: (codex.check(), 'idle')[1]
        return Engine(self.config, self.paths, gate or Gate(), core=ReconcileCore(),
                      codex=codex)

    def assert_preserved(self):
        with LedgerContext(self.paths, self.config) as ledger:
            row = ledger.current()
            self.assertEqual((row['sha'], row['stage'], row['patch_sha']),
                             (self.seed['sha256'], 'waiting_result', self.original['sha256']))
            self.assertEqual(ledger.request_contract()['clarifications_remaining'], 2)
        self.assertFalse((self.codex_home / 'calls.jsonl').exists())

    def rejected(self):
        with self.assertRaises(ControlError):
            self.queue()
        self.assert_preserved()

    def test_queue_from_active_chat_preserves_history_pause_and_all_original_bytes(self):
        self.settings(thread_status='active')
        preserved = {p: p.read_bytes() for p in [self.paths.config, self.paths.state_file,
                                               *self.directory.iterdir()]}
        reply = self.queue()
        self.assertTrue(reply['queued'])
        self.assertFalse(reply['history_advanced'] or reply['model_called'] or reply['service_started'])
        self.assert_preserved()
        self.assertEqual({p: p.read_bytes() for p in preserved}, preserved)
        self.assertEqual(public_status(self.paths)['result_sha256'], self.final['sha256'])

    def test_successful_idle_worker_atomically_advances_once_then_uses_new_source(self):
        self.queue()
        codex = FakeCodex(self, 'no_work')
        with self.engine(codex=codex) as engine:
            self.assertTrue(engine.tick()['again'])
            self.assertEqual(codex.calls, 0)
            with LedgerContext(self.paths, self.config) as ledger:
                self.assertEqual(ledger.current()['sha'], self.final['sha256'])
                self.assertEqual(ledger.request_contract()['clarifications_remaining'], 3)
                self.assertEqual(ledger.seed_sha, self.seed['sha256'])
                old = ledger.db.execute('SELECT stage,patch_sha FROM jobs WHERE sha=?', (self.seed['sha256'],)).fetchone()
                self.assertEqual(tuple(old), ('done', self.original['sha256']))
                self.assertIsNone(validate_history(ledger))
            self.assertTrue(engine.tick()['halted'])
            self.assertTrue(engine.tick()['halted'])
        self.assertEqual(codex.calls, 1)

    def test_worker_never_infers_recovery_without_explicit_queue(self):
        with self.engine() as engine:
            self.assertFalse(engine.tick()['again'])
            self.assertEqual(engine.codex.calls, 0)
        self.assert_preserved()

    def test_active_thread_waits_without_model_or_history_change(self):
        self.queue()
        codex = FakeCodex(self)
        codex.activity = lambda: 'active'
        with self.engine(codex=codex) as engine:
            self.assertEqual(engine.tick()['retry_after'], 2)
            self.assertEqual(engine.summary()['stage'], 'apply_reconciliation_waiting')
            self.assertEqual(codex.calls, 0)
        self.assert_preserved()

    def test_pause_blocks_adoption(self):
        self.queue()
        gate = Gate(); gate.set(False)
        with self.engine(gate=gate) as engine:
            self.assertFalse(engine.tick()['again'])
        self.assert_preserved()

    def test_pause_during_second_metadata_check_wins(self):
        self.queue()
        gate = Gate(); codex = FakeCodex(self)
        count = []
        def check():
            count.append(True)
            if len(count) == 2:
                gate.set(False)
        codex.check = check
        with self.engine(gate=gate, codex=codex) as engine:
            self.assertFalse(engine.tick()['again'])
        self.assert_preserved()

    def test_same_pending_request_is_idempotent(self):
        self.assertEqual(self.queue(), self.queue())
        with LedgerContext(self.paths, self.config) as ledger:
            self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM apply_reconciliations').fetchone()[0], 1)

    def test_restart_uses_same_pending_request(self):
        self.queue()
        with self.engine() as engine:
            self.assertTrue(engine.tick()['again'])
        with self.engine() as engine:
            self.assertTrue(engine.tick()['halted'])
        with LedgerContext(self.paths, self.config) as ledger:
            self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0], 2)

    def test_missing_original_patch_blocks(self):
        Path(self.original['path']).unlink(); self.rejected()

    def test_missing_checkpoint_blocks(self):
        Path(self.checkpoint['path']).unlink(); self.rejected()

    def test_missing_resumed_patch_blocks(self):
        Path(self.resumed['path']).unlink(); self.rejected()

    def test_original_result_present_blocks_reconciliation(self):
        self.result('old-failure.zip', previous=self.seed, patch_sha=self.original['sha256'], success=False)
        self.rejected()

    def test_two_continuation_results_do_not_choose_success(self):
        self.result('other.zip', previous=self.checkpoint, patch_sha=self.resumed['sha256'], success=False)
        self.rejected()

    def test_newer_unclaimed_result_blocks(self):
        self.result('newer.zip', captured_at='2026-01-01T03:00:00Z')
        self.rejected()

    def test_changed_entrypoint_program_blocks(self):
        self.create_output(extra='print("different behavior")\n'); self.rejected()

    def test_changed_commit_message_blocks(self):
        self.resumed_data['stages'][0]['message'] = 'Different work'
        self.create_output(); self.rejected()

    def test_changed_test_selection_blocks(self):
        self.resumed_data['stages'][1]['test_plan']['test_files'] = []
        self.create_output(); self.rejected()

    def test_omitted_commit_blocks(self):
        self.resumed_data['stages'].pop()
        self.create_output(); self.rejected()

    def test_false_original_plan_hash_blocks(self):
        self.resumed_data['correction_of']['plan_sha256'] = '0' * 64
        self.create_output(); self.rejected()

    def test_wrong_before_hash_blocks(self):
        self.resumed_data['stages'][0]['before']['src/example.py'] = '0' * 64
        self.create_output(); self.rejected()

    def test_dirty_success_blocks(self):
        self.create_output(dirty=True); self.rejected()

    def test_dry_run_blocks(self):
        self.create_output(dry_run=True); self.rejected()

    def test_failed_apply_blocks(self):
        self.create_output(success=False, primary_kind='entrypoint_exit'); self.rejected()

    def test_missing_completion_log_blocks(self):
        self.create_output(log='No execution evidence\n'); self.rejected()

    def test_wrong_parent_chain_blocks(self):
        log = progress_log(self.resumed_data).replace('"parent":"' + 'a' * 40, '"parent":"' + '0' * 40)
        self.create_output(log=log); self.rejected()

    def test_zero_tests_is_not_a_gate(self):
        self.create_output(log=progress_log(self.resumed_data).replace('"tests":100', '"tests":0'))
        self.rejected()

    def test_changed_original_completion_after_queue_blocks_worker(self):
        self.queue()
        json_write(self.directory / 'completion.json', {**self.answer, 'message': 'Changed'})
        with self.engine() as engine:
            with self.assertRaises(ControlError): engine.tick()
            self.assertEqual(engine.codex.calls, 0)
        self.assert_preserved()

    def test_archiving_all_artifacts_preserves_hash_bound_request(self):
        self.queue()
        archive = self.exchange / 'PatchHarbor-Archive'; archive.mkdir()
        for artifact in (self.seed, self.original, self.checkpoint, self.resumed, self.final):
            p = Path(artifact['path']); p.rename(archive / p.name)
        with self.engine() as engine:
            self.assertTrue(engine.tick()['again'])

    def test_queue_requires_existing_worker_to_be_stopped(self):
        from specroad_control.local import lock
        with lock(self.paths.state / 'worker.lock'):
            self.rejected()

    def test_worker_rollback_keeps_pending_request_and_original_claim(self):
        self.queue()
        from specroad_control.ledger import Ledger
        original = Ledger._enqueue
        def failure(ledger, source, *, decision_evidence=None):
            original(ledger, source, decision_evidence=decision_evidence)
            import sqlite3
            raise sqlite3.OperationalError('simulated disk full')
        with self.engine() as engine, patch.object(Ledger, '_enqueue', failure):
            with self.assertRaises(ControlError) as caught: engine.tick()
        self.assertEqual(caught.exception.code, 'apply_reconciliation_persist_failed')
        self.assert_preserved()
        with LedgerContext(self.paths, self.config) as ledger:
            self.assertIsNotNone(validate_history(ledger))
