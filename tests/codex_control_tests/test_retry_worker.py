"""Actual worker + Unix WebSocket fixture: timers, pause and controlled stop."""
from dataclasses import replace
import json
import time
from specroad_control.config import render
from specroad_control.daemon import request
from specroad_control.local import write_private
from codex_control_tests.automation_support import AutomationCase
from codex_control_tests.retry_support import initialize_git
from codex_control_tests.worker_observation import wait_stage


class RetryWorkerTests(AutomationCase):
    def setUp(self):
        super().setUp();initialize_git(self.dev)
        self.config=replace(self.config,transport='app-server-proxy',retry_delays_seconds=(3,))
        write_private(self.paths.config,render(self.config).encode())
        self.settings(overload=True)

    def wait_stage(self, stage, seconds=10):
        return wait_stage(self.paths, self.last_worker_process, self.last_worker_log,
                          stage, seconds)

    def calls(self):
        return len((self.codex_home/'calls.jsonl').read_text().splitlines())

    def test_worker_wakes_for_due_retry_without_any_new_exchange_event(self):
        child,_=self.spawn();self.wait_stage('retry_wait')
        self.settings(mode='no_work')
        state=self.wait_stage('no_work')
        self.assertEqual(self.calls(),2)
        self.assertEqual(state['automation']['retry_attempt'],1)
        request(self.paths,'stop');self.assertEqual(child.wait(timeout=5),0)

    def test_pause_prevents_due_model_and_resume_keeps_attempt_budget(self):
        child,_=self.spawn();first=self.wait_stage('retry_wait')
        request(self.paths,'pause');self.settings(mode='no_work')
        remaining=max(0,first['automation']['retry_at']-time.time())
        time.sleep(remaining+.15)
        self.assertEqual(self.calls(),1)
        self.assertEqual(request(self.paths,'status')['state']['desired'],'paused')
        request(self.paths,'resume');self.wait_stage('no_work')
        self.assertEqual(self.calls(),2)
        request(self.paths,'stop');self.assertEqual(child.wait(timeout=5),0)

    def test_stop_during_backoff_does_not_wait_for_timer_or_start_model(self):
        child,_=self.spawn();self.wait_stage('retry_wait')
        request(self.paths,'stop');self.assertEqual(child.wait(timeout=5),0)
        self.assertEqual(self.calls(),1)
