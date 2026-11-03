"""Real isolated worker and IPC; only capacity measurements and model/Core are doubles."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from specroad_control.disk_space import GB, set_limit
from specroad_control.errors import ControlError
from specroad_control.ipc import request
from specroad_control.local import REPO, json_read
from codex_control_tests.automation_support import AutomationCase


WORKER = '''
import json, os
from pathlib import Path
import specroad_control.disk_space as storage
import specroad_control.daemon as daemon
from specroad_control.cli import main
daemon.CHECK_SECONDS = 0.05
def measured(config, paths):
    value = json.loads((config.codex_home/'disk-test.json').read_text())
    if value.get('error'): raise OSError('isolated unavailable disk')
    return [{'device': 1, 'paths': ['/isolated-work-volume'], 'free_bytes': value['free']}]
storage.sample = measured
raise SystemExit(main(['run']))
'''


class DiskSpaceWorkerTests(AutomationCase):
    def setUp(self):
        super().setUp()
        set_limit(self.paths, 10)
        self.capacity(20 * GB)
        self.settings(mode='patch')

    def capacity(self, value, *, error=False):
        path = self.codex_home / 'disk-test.json'
        temporary = path.with_suffix('.partial')
        temporary.write_text(json.dumps({'free': value, 'error': error})); temporary.replace(path)

    def worker(self):
        log = tempfile.TemporaryFile(); self.addCleanup(log.close)
        child = subprocess.Popen([sys.executable, '-B', '-c', WORKER], cwd=self.paths.home / 'releases' / ('a' * 40),
                                 env=dict(os.environ), stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        def finish():
            if child.poll() is None:
                (self.codex_home / 'release').write_text('yes')
                child.terminate(); child.wait(timeout=15)
        self.addCleanup(finish)
        self.child, self.log = child, log
        return child

    def await_state(self, predicate, timeout=15):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            if self.child.poll() is not None:
                state = json_read(self.paths.state_file)
                if state and predicate(state): return state
                self.log.seek(0); self.fail('Isolated worker exited: ' + self.log.read().decode())
            try:
                state = request(self.paths, 'status')['state']
                if predicate(state): return state
            except ControlError as exc:
                if exc.code != 'not_running': raise
            time.sleep(.02)
        self.fail('Expected storage/lifecycle state was not reached.')

    def calls(self):
        path = self.codex_home / 'calls.jsonl'
        return len(path.read_text().splitlines()) if path.exists() else 0

    def test_low_space_at_start_stops_before_first_model(self):
        self.capacity(GB); child = self.worker()
        self.assertEqual(child.wait(timeout=15), 0)
        state = json_read(self.paths.state_file)
        self.assertEqual((state['phase'], state['stop_reason']), ('stopped', 'low_disk_space'))
        self.assertEqual(state['disk_space']['min_free_bytes'], 10 * GB)
        self.assertEqual(self.calls(), 0)

    def test_idle_wait_observes_space_without_exchange_events(self):
        child = self.worker()
        self.await_state(lambda s: (s['automation'] or {}).get('stage') == 'waiting_result' and not s['active_job'])
        self.capacity(GB)
        self.assertEqual(child.wait(timeout=15), 0)
        self.assertEqual(json_read(self.paths.state_file)['stop_reason'], 'low_disk_space')
        self.assertEqual(self.calls(), 1)

    def test_active_model_finishes_normally_then_worker_stops(self):
        self.settings(mode='patch', slow=True); child = self.worker()
        self.await_state(lambda s: s['active_job'] and (self.codex_home / 'started').exists())
        self.capacity(GB)
        state = self.await_state(lambda s: s['phase'] == 'stopping')
        self.assertEqual(state['stop_reason'], 'low_disk_space')
        self.assertIsNone(child.poll())
        with self.assertRaises(ControlError):
            reply = request(self.paths, 'resume')
            if not reply.get('ok'): raise ControlError(reply['error'], 'resume rejected')
        self.capacity(30 * GB)
        (self.codex_home / 'release').write_text('yes')
        self.assertEqual(child.wait(timeout=15), 0)
        self.assertEqual(self.calls(), 1)
        self.assertEqual(json_read(self.paths.state_file)['phase'], 'stopped')

    def test_disk_failure_stops_without_new_model(self):
        self.capacity(0, error=True); child = self.worker()
        self.assertEqual(child.wait(timeout=15), 0)
        self.assertEqual(json_read(self.paths.state_file)['stop_reason'], 'disk_space_unavailable')
        self.assertEqual(self.calls(), 0)

    def test_explicit_restart_rechecks_and_can_continue_after_space_is_available(self):
        self.capacity(GB); child = self.worker(); self.assertEqual(child.wait(timeout=15), 0)
        self.capacity(20 * GB); self.worker()
        state = self.await_state(lambda s: (s['automation'] or {}).get('stage') == 'waiting_result' and not s['active_job'])
        self.assertIsNone(state['stop_reason']); self.assertEqual(self.calls(), 1)

    def test_existing_pause_stays_paused_when_space_is_healthy(self):
        self.settings(mode='no_work'); child = self.worker()
        self.await_state(lambda s: s['phase'] == 'paused' and not s['active_job'])
        self.capacity(15 * GB)
        state = request(self.paths, 'status')['state']
        self.assertEqual(state['phase'], 'paused')
        self.assertEqual(self.calls(), 1)
        self.assertIsNone(child.poll())

    def test_paused_worker_also_stops_on_low_space(self):
        self.settings(mode='no_work'); child = self.worker()
        self.await_state(lambda s: s['phase'] == 'paused' and not s['active_job'])
        self.capacity(GB)
        self.assertEqual(child.wait(timeout=15), 0)
        state = json_read(self.paths.state_file)
        self.assertEqual(state['desired'], 'paused')
        self.assertEqual(state['stop_reason'], 'low_disk_space')
