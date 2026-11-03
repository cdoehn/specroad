"""Real isolated worker: wait persists without pausing or a second model call."""
import json
import time
from dataclasses import replace
from specroad_control.config import render
from specroad_control.daemon import request
from specroad_control.job_contract import scope
from specroad_control.ledger import Ledger
from specroad_control.local import write_private
from codex_control_tests.automation_support import AutomationCase
from codex_control_tests.retry_support import initialize_git


class WaitWorkerTests(AutomationCase):
    def setUp(self):
        super().setUp()
        initialize_git(self.dev)
        self.config = replace(self.config, transport='app-server-proxy', retry_delays_seconds=(1,))
        write_private(self.paths.config, render(self.config).encode())
        self.settings(overload=True, partial_overload=True, pending_overload=True)

    def wait_stage(self, stage, seconds=40):
        end = time.monotonic()+seconds
        while time.monotonic() < end:
            state = request(self.paths, 'status')['state']
            if (state.get('automation') or {}).get('stage') == stage and not state['active_job']:
                return state
            time.sleep(.03)
        self.fail('Worker did not reach the requested stage')

    def calls(self):
        return len((self.codex_home/'calls.jsonl').read_text().splitlines())

    def finish(self):
        for turn in self.codex_daemon.server.history.values():
            for item in turn.get('items', []):
                if item.get('status') == 'inProgress':
                    item.update(status='completed', exitCode=0, durationMs=200, aggregatedOutput='finished')
        self.settings(mode='no_work')

    def wait_record(self):
        ledger = Ledger(self.paths.state/'automation.sqlite3', scope(self.config))
        try:
            return ledger.overload_wait()
        finally:
            ledger.close()

    def test_worker_automatically_continues_after_background_finishes(self):
        child, _ = self.spawn()
        first = self.wait_stage('overload_wait')
        self.assertEqual(first['desired'], 'running')
        self.assertEqual(self.calls(), 1)
        self.finish()
        # No Exchange event or operator restart is needed to wake this worker.
        self.wait_stage('no_work')
        self.assertEqual(self.calls(), 2)
        self.assertIsNone(child.poll())
        self.assertEqual((self.dev/'partial.txt').read_text(), 'preserved local work')
        request(self.paths, 'stop'); self.assertEqual(child.wait(timeout=5), 0)

    def test_controlled_stop_keeps_background_running_and_checkpoint(self):
        child, _ = self.spawn(); self.wait_stage('overload_wait')
        saved = self.wait_record()
        request(self.paths, 'stop'); self.assertEqual(child.wait(timeout=5), 0)
        self.assertEqual(self.wait_record(), saved)
        self.assertEqual(self.calls(), 1)
        self.assertTrue(any(item.get('status') == 'inProgress'
            for turn in self.codex_daemon.server.history.values() for item in turn['items']))

    def test_paused_restart_preserves_wait_without_new_model(self):
        child, _ = self.spawn(); self.wait_stage('overload_wait')
        saved = self.wait_record()
        request(self.paths, 'pause')
        request(self.paths, 'stop'); self.assertEqual(child.wait(timeout=5), 0)
        child, state = self.spawn()
        self.assertEqual(state['state']['desired'], 'paused')
        self.assertEqual(self.wait_record(), saved)
        self.assertEqual(self.calls(), 1)
        request(self.paths, 'stop'); self.assertEqual(child.wait(timeout=5), 0)

    def test_unpaused_restart_resumes_wait_without_replaying_failed_turn(self):
        child, _ = self.spawn(); self.wait_stage('overload_wait')
        saved = self.wait_record()
        request(self.paths, 'stop'); self.assertEqual(child.wait(timeout=5), 0)
        child, _ = self.spawn()
        state = self.wait_stage('overload_wait')
        self.assertEqual(state['desired'], 'running')
        self.assertEqual(state['automation']['overload_check_at'], saved['next_at'])
        self.assertEqual(self.calls(), 1)
        request(self.paths, 'stop'); self.assertEqual(child.wait(timeout=5), 0)
