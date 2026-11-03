"""Real isolated worker and lifecycle IPC around a deferred Apply proof."""
from specroad_control.apply_reconcile import enqueue, validate_history
from specroad_control.ipc import request
from specroad_control.local import json_write
from codex_control_tests.apply_reconcile_support import ReconcileCase
from codex_control_tests.test_deferred_handover import DeferredCase
from codex_control_tests.test_recovery import LedgerContext


class ApplyReconcileWorkerTests(ReconcileCase):
    worker = DeferredCase.worker
    await_state = DeferredCase.await_state
    calls = DeferredCase.calls

    def queue(self, *, running=True):
        if running:
            import json
            state = json.loads(self.paths.state_file.read_text())
            json_write(self.paths.state_file, {**state, 'desired': 'running', 'phase': 'idle'})
        self.settings(thread_status='active', mode='no_work')
        enqueue(self.paths, self.final['path'])

    def test_worker_waits_for_current_chat_then_advances_and_dispatches_once(self):
        self.queue(); self.worker()
        self.await_state(lambda s: (s['automation'] or {}).get('stage') == 'apply_reconciliation_waiting')
        self.assertEqual(self.calls(), [])
        self.settings(thread_status='idle', mode='no_work')
        self.await_state(lambda s: (s['automation'] or {}).get('stage') == 'no_work' and not s['active_job'], timeout=30)
        self.assertEqual(len(self.calls()), 1)
        with LedgerContext(self.paths, self.config) as ledger:
            self.assertEqual(ledger.current()['sha'], self.final['sha256'])

    def test_existing_pause_prevents_observation_and_adoption_until_resume(self):
        self.queue(running=False); self.worker()
        self.await_state(lambda s: s['phase'] == 'paused' and not s['active_job'])
        self.assertEqual(self.calls(), [])
        with LedgerContext(self.paths, self.config) as ledger:
            self.assertEqual(ledger.current()['sha'], self.seed['sha256'])
        self.settings(thread_status='idle', mode='no_work')
        request(self.paths, 'resume')
        self.await_state(lambda s: (s['automation'] or {}).get('stage') == 'no_work' and not s['active_job'], timeout=30)
        self.assertEqual(len(self.calls()), 1)

    def test_stop_leaves_pending_request_durable_and_starts_no_model(self):
        self.queue(); child = self.worker()
        self.await_state(lambda s: (s['automation'] or {}).get('stage') == 'apply_reconciliation_waiting')
        request(self.paths, 'stop')
        self.assertEqual(child.wait(timeout=15), 0)
        self.assertEqual(self.calls(), [])
        with LedgerContext(self.paths, self.config) as ledger:
            self.assertIsNotNone(validate_history(ledger))

    def test_pause_while_waiting_survives_stop_and_restart(self):
        self.queue(); child = self.worker()
        self.await_state(lambda s: (s['automation'] or {}).get('stage') == 'apply_reconciliation_waiting')
        request(self.paths, 'pause')
        self.await_state(lambda s: s['phase'] == 'paused' and not s['active_job'])
        request(self.paths, 'stop'); self.assertEqual(child.wait(timeout=15), 0)
        self.settings(thread_status='idle', mode='no_work')
        self.worker(); self.await_state(lambda s: s['phase'] == 'paused' and not s['active_job'])
        self.assertEqual(self.calls(), [])

    def test_unknown_thread_status_blocks_worker_without_loop_or_model(self):
        self.queue(); self.settings(thread_status='systemError', mode='no_work'); self.worker()
        state = self.await_state(lambda s: s['phase'] == 'paused' and s['runtime_error'])
        self.assertEqual(state['runtime_error'], 'apply_reconciliation_thread_unknown')
        self.assertEqual(self.calls(), [])
