"""Configuration and lifecycle boundaries for delayed automation."""
from dataclasses import replace
import json
import signal
import time
from specroad_control.config import initialize, load, render
from specroad_control.errors import ControlError
from specroad_control.ipc import request
from specroad_control.local import read_private, write_private, json_read, json_write
from specroad_control.state import read_state
from specroad_control.disk_space import set_limit
from codex_control_tests.support import LocalCase
from codex_control_tests.automation_support import AutomationCase


class DelayValidationTests(LocalCase):
    def test_invalid_delay_preserves_config(self):
        initialize(self.paths)
        original = read_private(self.paths.config)
        for value in ('true', '-1', '86400.01', 'inf', '-inf', 'nan', '"60"', '[]', '1' + '0'*400):
            raw = original.replace(b'start_delay_seconds = 60.0', ('start_delay_seconds = '+value).encode())
            write_private(self.paths.config, raw)
            with self.subTest(value=value[:32]), self.assertRaises(ControlError) as caught:
                load(self.paths)
            self.assertEqual(caught.exception.code, 'invalid_config')
            self.assertEqual(read_private(self.paths.config), raw)

    def test_old_state_and_zero_delay_are_valid_but_bad_new_status_is_preserved(self):
        child, _ = self.spawn()
        request(self.paths, 'stop'); child.wait(timeout=5)
        original = json_read(self.paths.state_file)
        old = dict(original); old.pop('start_delay')
        json_write(self.paths.state_file, old)
        self.assertEqual(read_state(self.paths), old)
        for value in (None, {}, {'seconds': 60, 'remaining_seconds': -1, 'waiting': False},
                      {'seconds': 60, 'remaining_seconds': 61, 'waiting': True},
                      {'seconds': True, 'remaining_seconds': 0, 'waiting': False},
                      {'seconds': 60, 'remaining_seconds': True, 'waiting': True},
                      {'seconds': 60, 'remaining_seconds': 1, 'waiting': 1},
                      {'seconds': 60, 'remaining_seconds': 1, 'waiting': False},
                      {'seconds': 60, 'remaining_seconds': 1, 'waiting': True}):
            changed = {**original, 'start_delay': value}
            json_write(self.paths.state_file, changed)
            raw = read_private(self.paths.state_file)
            with self.subTest(value=value), self.assertRaises(ControlError): read_state(self.paths)
            self.assertEqual(read_private(self.paths.state_file), raw)
        json_write(self.paths.state_file, original)
        self.assertEqual(read_state(self.paths), original)


class DelayBoundaryWorkerTests(AutomationCase):
    def configure_delay(self, seconds):
        self.config = replace(self.config, start_delay_seconds=seconds)
        write_private(self.paths.config, render(self.config).encode())

    def test_sigterm_during_delay_has_no_model_or_ledger_claim(self):
        self.configure_delay(60)
        history = (self.paths.state/'automation.sqlite3').read_bytes()
        child, reply = self.spawn()
        self.assertTrue(reply['state']['start_delay']['waiting'])
        child.send_signal(signal.SIGTERM)
        self.assertEqual(child.wait(timeout=5), 0)
        self.assertFalse((self.codex_home/'calls.jsonl').exists())
        self.assertEqual((self.paths.state/'automation.sqlite3').read_bytes(), history)

    def test_restart_keeps_pause_and_uses_full_new_deadline(self):
        self.configure_delay(60)
        child, _ = self.spawn()
        request(self.paths, 'pause'); request(self.paths, 'stop'); child.wait(timeout=5)
        # A saved zero is diagnostic only, never authority to skip a new delay.
        self.assertEqual(json_read(self.paths.state_file)['start_delay']['remaining_seconds'], 0)
        second, reply = self.spawn()
        self.assertEqual(reply['state']['phase'], 'paused')
        self.assertGreater(reply['state']['start_delay']['remaining_seconds'], 50)
        self.assertTrue(request(self.paths,'resume')['state']['start_delay']['waiting'])
        self.assertFalse((self.codex_home/'calls.jsonl').exists())
        request(self.paths,'stop'); self.assertEqual(second.wait(timeout=5), 0)

    def test_pause_outlives_deadline_and_resume_does_not_restart_it(self):
        self.configure_delay(60)
        # Preserve a deliberate pause before starting the timed worker.
        child, _ = self.spawn()
        request(self.paths,'pause'); request(self.paths,'stop'); child.wait(timeout=5)
        self.configure_delay(.4)
        second, _ = self.spawn()
        until = time.monotonic()+10
        while request(self.paths,'status')['state']['start_delay']['waiting']:
            self.assertLess(time.monotonic(), until); time.sleep(.02)
        self.assertEqual(request(self.paths,'status')['state']['phase'], 'paused')
        self.assertFalse((self.codex_home/'calls.jsonl').exists())
        self.assertFalse(request(self.paths,'resume')['state']['start_delay']['waiting'])
        request(self.paths,'stop'); self.assertEqual(second.wait(timeout=5), 0)

    def test_storage_stop_precedes_long_delay(self):
        self.configure_delay(60)
        set_limit(self.paths, 10)
        import subprocess, sys
        script = "import specroad_control.disk_space as disk\ndisk.sample = lambda *_: [{'device': 1, 'paths': ['/isolated'], 'free_bytes': 0}]\nfrom specroad_control.cli import main\nraise SystemExit(main(['run']))\n"
        completed = subprocess.run([sys.executable,'-B','-c',script],
                                   cwd=self.paths.home/'releases'/('a'*40),
                                   capture_output=True, text=True, timeout=10)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        saved = json_read(self.paths.state_file)
        self.assertEqual((saved['phase'],saved['stop_reason']), ('stopped','low_disk_space'))
        self.assertFalse((self.codex_home/'calls.jsonl').exists())
