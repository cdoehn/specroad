"""Existing isolated worker lifecycle also governs version-2 recovery intents."""
from specroad_control.apply_reconcile import enqueue, validate_history
from specroad_control.ipc import request
from specroad_control.local import json_write
from codex_control_tests.blocked_chain_support import BlockedChainCase
import codex_control_tests.test_deferred_handover as deferred
from codex_control_tests.test_recovery import LedgerContext


class BlockedChainWorkerTests(BlockedChainCase):
    worker = deferred.DeferredCase.worker
    await_state = deferred.DeferredCase.await_state
    calls = deferred.DeferredCase.calls

    def queue(self, *, running=True):
        if running:
            import json
            state = json.loads(self.paths.state_file.read_text())
            json_write(self.paths.state_file, {**state, 'desired': 'running', 'phase': 'idle'})
        self.settings(thread_status='active', mode='no_work')
        enqueue(self.paths, self.final['path'], blocked=True)

    def test_worker_waits_for_current_chat_then_dispatches_once(self):
        self.queue(); self.worker()
        self.await_state(lambda s: (s['automation'] or {}).get('stage') == 'apply_reconciliation_waiting')
        self.assertEqual(self.calls(), [])
        self.settings(thread_status='idle', mode='no_work')
        self.await_state(lambda s: (s['automation'] or {}).get('stage') == 'no_work' and not s['active_job'], timeout=30)
        self.assertEqual(len(self.calls()), 1)
        with LedgerContext(self.paths, self.config) as ledger:
            self.assertEqual(ledger.current()['sha'], self.final['sha256'])
            self.assertFalse(ledger.request_contract()['clarification_allowed'])
            self.assertEqual(ledger.request_contract()['clarifications_remaining'], 2)

    def test_pause_stays_until_explicit_resume(self):
        self.queue(running=False); self.worker()
        self.await_state(lambda s: s['phase'] == 'paused' and not s['active_job'])
        self.assertEqual(self.calls(), [])
        self.settings(thread_status='idle', mode='no_work'); request(self.paths, 'resume')
        self.await_state(lambda s: (s['automation'] or {}).get('stage') == 'no_work' and not s['active_job'], timeout=30)
        self.assertEqual(len(self.calls()), 1)

    def test_stop_keeps_pending_intent_and_no_model_calls(self):
        self.queue(); child = self.worker()
        self.await_state(lambda s: (s['automation'] or {}).get('stage') == 'apply_reconciliation_waiting')
        request(self.paths, 'stop'); self.assertEqual(child.wait(timeout=15), 0)
        self.assertEqual(self.calls(), [])
        with LedgerContext(self.paths, self.config) as ledger: self.assertIsNotNone(validate_history(ledger))

    def test_restart_preserves_pause_and_pending_intent(self):
        self.queue(); child = self.worker()
        self.await_state(lambda s: (s['automation'] or {}).get('stage') == 'apply_reconciliation_waiting')
        request(self.paths, 'pause'); self.await_state(lambda s: s['phase'] == 'paused' and not s['active_job'])
        request(self.paths, 'stop'); self.assertEqual(child.wait(timeout=15), 0)
        self.settings(thread_status='idle', mode='no_work'); self.worker()
        self.await_state(lambda s: s['phase'] == 'paused' and not s['active_job'])
        self.assertEqual(self.calls(), [])

    def test_unknown_activity_fails_closed_without_model(self):
        self.queue(); self.settings(thread_status='systemError', mode='no_work'); self.worker()
        state = self.await_state(lambda s: s['phase'] == 'paused' and s['runtime_error'])
        self.assertEqual(state['runtime_error'], 'apply_reconciliation_thread_unknown'); self.assertEqual(self.calls(), [])

    def test_disk_gate_prevents_recovery_dispatch_and_retains_pending(self):
        self.queue()
        from specroad_control.local import write_private
        write_private(self.paths.config.with_suffix('.limits.toml'), b'format_version = 1\nmin_free_gb = 1000000\n')
        child = self.worker()
        self.assertEqual(child.wait(timeout=15), 0); self.assertEqual(self.calls(), [])
        with LedgerContext(self.paths, self.config) as ledger:
            self.assertIsNotNone(validate_history(ledger)); self.assertEqual(ledger.current()['sha'], self.seed['sha256'])
