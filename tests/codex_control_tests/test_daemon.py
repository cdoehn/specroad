import json
import signal
import subprocess
import sys
from specroad_control.config import initialize
from specroad_control.daemon import request
from specroad_control.errors import ControlError
from specroad_control.local import REPO, json_read
from codex_control_tests.support import LocalCase

class DaemonTests(LocalCase):
    def test_real_worker_pause_resume_and_stop(self):
        child, reply = self.spawn()
        self.assertEqual(reply['state']['phase'], 'idle')
        self.assertFalse(reply['state']['development_enabled'])
        self.assertEqual(request(self.paths, 'pause')['state']['phase'], 'paused')
        self.assertEqual(request(self.paths, 'resume')['state']['phase'], 'idle')
        request(self.paths, 'stop')
        self.assertEqual(child.wait(timeout=5), 0)
        self.assertEqual(json_read(self.paths.state_file)['phase'], 'stopped')
        self.assertFalse(self.paths.socket.exists())

    def test_pause_survives_manual_restart(self):
        child, _ = self.spawn()
        request(self.paths, 'pause'); request(self.paths, 'stop'); child.wait(timeout=5)
        second, reply = self.spawn()
        self.assertEqual(reply['state']['phase'], 'paused')
        request(self.paths, 'stop'); self.assertEqual(second.wait(timeout=5), 0)

    def test_sigterm_is_graceful(self):
        child, _ = self.spawn()
        child.send_signal(signal.SIGTERM)
        self.assertEqual(child.wait(timeout=5), 0)
        self.assertEqual(json_read(self.paths.state_file)['phase'], 'stopped')

    def test_second_process_cannot_steal_first_state(self):
        first, reply = self.spawn()
        attempt = subprocess.run([sys.executable, '-B', str(self.paths.home / 'releases' / ('a' * 40) / 'control'), 'run'], capture_output=True, text=True, timeout=5)
        self.assertNotEqual(attempt.returncode, 0)
        self.assertEqual(request(self.paths, 'status')['state']['run_id'], reply['state']['run_id'])
        self.assertIsNone(first.poll())

    def test_worker_not_running_is_explicit(self):
        with self.assertRaises(ControlError) as caught: request(self.paths, 'status')
        self.assertEqual(caught.exception.code, 'not_running')
