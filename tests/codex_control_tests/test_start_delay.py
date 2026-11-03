"""Deadline and real isolated worker behavior; never a live model or service."""
from dataclasses import replace
import time
import unittest
from unittest.mock import patch
from specroad_control.config import initialize, load, render
from specroad_control.daemon import StartDelay
from specroad_control.ipc import request
from specroad_control.local import read_private, write_private, json_read
from codex_control_tests.support import LocalCase
from codex_control_tests.automation_support import AutomationCase, read_package


class DelayClockTests(unittest.TestCase):
    def test_default_length_boundary_and_later_scheduling(self):
        now = [100.0]
        delay = StartDelay(60, clock=lambda: now[0])
        self.assertEqual(delay.snapshot(), {'seconds': 60, 'remaining_seconds': 60, 'waiting': True})
        now[0] = 159.999
        self.assertFalse(delay.ready())
        self.assertEqual(delay.due(110), 160)
        self.assertEqual(delay.due(180), 180)
        now[0] = 160
        self.assertTrue(delay.ready())
        now[0] = 200
        self.assertEqual(delay.snapshot()['remaining_seconds'], 0)

    def test_wall_clock_change_does_not_open_delay(self):
        now = [200.0]
        delay = StartDelay(60, clock=lambda: now[0])
        with patch('time.time', return_value=1e12):
            self.assertFalse(delay.ready())
            self.assertEqual(delay.remaining(), 60)

    def test_zero_and_stop_have_no_wait(self):
        self.assertTrue(StartDelay(0).ready())
        self.assertFalse(StartDelay(60).snapshot(stopping=True)['waiting'])


class DelayConfigTests(LocalCase):
    def test_new_and_existing_configuration_default_to_sixty_without_rewrite(self):
        self.assertEqual(initialize(self.paths).start_delay_seconds, 60)
        old = read_private(self.paths.config).replace(b'start_delay_seconds = 60.0\n', b'')
        write_private(self.paths.config, old)
        self.assertEqual(load(self.paths).start_delay_seconds, 60)
        self.assertEqual(read_private(self.paths.config), old)

    def test_explicit_values_roundtrip(self):
        initial = initialize(self.paths)
        for value in (0, 0.25, 60, 86400):
            with self.subTest(value=value):
                write_private(self.paths.config, render(replace(initial, start_delay_seconds=value)).encode())
                self.assertEqual(load(self.paths).start_delay_seconds, value)


class StartDelayWorkerTests(AutomationCase):
    def configure_delay(self, seconds):
        self.config = replace(self.config, start_delay_seconds=seconds)
        write_private(self.paths.config, render(self.config).encode())

    def state(self):
        return request(self.paths, 'status')['state']

    def calls(self):
        path = self.codex_home / 'calls.jsonl'
        return len(path.read_text().splitlines()) if path.exists() else 0

    def wait_for(self, predicate):
        until = time.monotonic() + 10
        while time.monotonic() < until:
            if predicate(): return
            time.sleep(.02)
        self.fail('Expected worker transition did not occur')

    def test_default_wait_preserves_history_and_accepts_pause_resume_stop(self):
        original = read_private(self.paths.config).replace(b'start_delay_seconds = 0\n', b'')
        write_private(self.paths.config, original)
        history = (self.paths.state / 'automation.sqlite3').read_bytes()
        child, reply = self.spawn()
        self.assertEqual(reply['state']['start_delay']['seconds'], 60)
        self.assertTrue(reply['state']['start_delay']['waiting'])
        self.assertFalse(reply['state']['active_job'])
        for index in range(4):
            (self.exchange / ('wake-' + str(index))).write_text('event')
            self.assertEqual(request(self.paths, 'pause')['state']['phase'], 'paused')
            self.assertTrue(request(self.paths, 'resume')['state']['start_delay']['waiting'])
        self.assertEqual(self.calls(), 0)
        self.assertEqual((self.paths.state / 'automation.sqlite3').read_bytes(), history)
        request(self.paths, 'stop')
        self.assertEqual(child.wait(timeout=5), 0)
        self.assertEqual(json_read(self.paths.state_file)['phase'], 'stopped')
        self.assertFalse(json_read(self.paths.state_file)['start_delay']['waiting'])
        self.assertEqual(read_private(self.paths.config), original)

    def test_expiry_dispatches_and_does_not_delay_every_followup(self):
        self.configure_delay(.3)
        self.settings(mode='patch')
        before = time.monotonic()
        child, _ = self.spawn()
        self.wait_for(lambda: self.calls() == 1 and not self.state()['active_job'])
        self.assertGreaterEqual(time.monotonic() - before, .3)
        self.assertFalse(self.state()['start_delay']['waiting'])
        patch = read_package(next(self.exchange.glob('dev-*.zip')))
        self.result('followup.zip', previous=self.seed, patch_sha=patch['sha256'])
        self.wait_for(lambda: self.calls() == 2 and not self.state()['active_job'])
        self.assertEqual(self.state()['start_delay']['remaining_seconds'], 0)
        request(self.paths, 'stop')
        self.assertEqual(child.wait(timeout=5), 0)
