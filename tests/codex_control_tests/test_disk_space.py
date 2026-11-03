"""Storage limits and final dispatch gating, independent of host free capacity."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from specroad_control.automation import Engine, Gate
from specroad_control.disk_space import DiskGuard, GB, limits_path, read_limits, set_limit, sample, locations
from specroad_control.errors import ControlError
from specroad_control.local import write_private, lock
from codex_control_tests.automation_support import AutomationCase, FakeCodex, FakeCore
from codex_control_tests.test_recovery import LedgerContext


def volumes(free):
    return [{'device': 1, 'paths': ['/test-volume'], 'free_bytes': free}]


class DiskSpaceTests(AutomationCase):
    def setUp(self):
        super().setUp()
        limits_path(self.paths).unlink()  # Test the product's default, not the general fixture's tiny limit.

    def guard(self):
        return DiskGuard(self.config, self.paths)

    def test_default_is_ten_decimal_gb_without_creating_configuration(self):
        result = read_limits(self.paths)
        self.assertEqual(result['min_free_gb'], 10)
        self.assertEqual(result['min_free_bytes'], 10_000_000_000)
        self.assertFalse(result['configured'])
        self.assertFalse(limits_path(self.paths).exists())

    def test_explicit_setting_roundtrips_and_keeps_main_config_and_history_bytes(self):
        before = {p: p.read_bytes() for p in (self.paths.config, self.paths.state / 'automation.sqlite3')}
        answer = set_limit(self.paths, 12.5)
        self.assertEqual(answer['min_free_bytes'], 12_500_000_000)
        self.assertTrue(answer['configured'] and answer['saved'])
        self.assertFalse(answer['service_started'] or answer['model_called'])
        self.assertEqual({p: p.read_bytes() for p in before}, before)
        self.assertEqual(limits_path(self.paths).stat().st_mode & 0o777, 0o600)

    def test_fractional_byte_limit_rounds_up(self):
        set_limit(self.paths, 0.0000000011)
        self.assertEqual(read_limits(self.paths)['min_free_bytes'], 2)

    def test_invalid_limits_do_not_replace_prior_value(self):
        set_limit(self.paths, 10)
        before = limits_path(self.paths).read_bytes()
        for value in (0, -1, True, False, '10', float('nan'), float('inf'), 1000001, None):
            with self.subTest(value=value), self.assertRaises(ControlError): set_limit(self.paths, value)
            self.assertEqual(limits_path(self.paths).read_bytes(), before)

    def test_closed_configuration_contract(self):
        for raw in (b'broken', b'format_version=2\nmin_free_gb=10\n',
                    b'format_version=1\nmin_free_gb=true\n', b'format_version=1\nmin_free_gb=10\nextra=1\n'):
            write_private(limits_path(self.paths), raw)
            with self.subTest(raw=raw), self.assertRaises(ControlError): read_limits(self.paths)

    def test_running_worker_lock_prevents_setting(self):
        with lock(self.paths.state / 'worker.lock'), self.assertRaises(ControlError): set_limit(self.paths, 20)
        self.assertFalse(limits_path(self.paths).exists())

    def test_exact_boundary_is_sufficient(self):
        with patch('specroad_control.disk_space.sample', return_value=volumes(10 * GB)):
            self.assertTrue(self.guard().require()['sufficient'])

    def test_one_byte_below_boundary_stops(self):
        with patch('specroad_control.disk_space.sample', return_value=volumes(10 * GB - 1)):
            with self.assertRaises(ControlError) as caught: self.guard().require()
        self.assertEqual(caught.exception.code, 'low_disk_space')
        self.assertEqual(caught.exception.details['disk_space']['filesystems'][0]['free_bytes'], 10 * GB - 1)

    def test_any_required_volume_can_stop_automation(self):
        separate = volumes(50 * GB) + [{'device': 2, 'paths': ['/exchange'], 'free_bytes': GB}]
        with patch('specroad_control.disk_space.sample', return_value=separate):
            with self.assertRaises(ControlError): self.guard().require()

    def test_stop_latches_even_when_space_returns(self):
        guard = self.guard()
        with patch('specroad_control.disk_space.sample', side_effect=[volumes(GB), volumes(50 * GB)]):
            with self.assertRaises(ControlError): guard.require()
            with self.assertRaises(ControlError): guard.require()

    def test_explicit_new_worker_rechecks_space_after_previous_stop(self):
        with patch('specroad_control.disk_space.sample', return_value=volumes(GB)):
            with self.assertRaises(ControlError): self.guard().require()
        with patch('specroad_control.disk_space.sample', return_value=volumes(50 * GB)):
            self.assertTrue(self.guard().require()['sufficient'])

    def test_measurement_error_fails_closed(self):
        for error in (PermissionError(), FileNotFoundError(), OSError('stat failed')):
            with self.subTest(error=type(error).__name__), patch('specroad_control.disk_space.sample', side_effect=error):
                with self.assertRaises(ControlError) as caught: self.guard().require()
                self.assertEqual(caught.exception.code, 'disk_space_unavailable')

    def test_no_measurement_is_not_success(self):
        with patch('specroad_control.disk_space.sample', return_value=[]):
            with self.assertRaises(ControlError): self.guard().require()

    def test_final_gate_blocks_claim_and_model_when_space_falls_after_preflight(self):
        guard = self.guard()
        codex = FakeCodex(self, 'no_work')
        with patch('specroad_control.disk_space.sample', return_value=volumes(20 * GB)):
            guard.require()
        with Engine(self.config, self.paths, Gate(guard), core=FakeCore(), codex=codex) as engine:
            with patch('specroad_control.disk_space.sample', return_value=volumes(GB)):
                with self.assertRaises(ControlError): engine.tick()
        self.assertEqual(codex.calls, 0)
        with LedgerContext(self.paths, self.config) as ledger:
            self.assertEqual(ledger.current()['stage'], 'ready')
            self.assertIsNone(ledger.current()['error'])

    def test_closed_lifecycle_gate_never_calls_commit(self):
        guard = self.guard(); gate = Gate(guard); gate.set(False); called = []
        self.assertFalse(gate.enter(lambda: called.append(True)))
        self.assertEqual(called, [])
        self.assertIsNone(guard.snapshot()['checked_at'])

    def test_available_blocks_exclude_root_reserve_and_share_volume(self):
        fake = SimpleNamespace(f_bavail=5, f_bfree=500, f_frsize=4096, f_bsize=4096)
        with patch('specroad_control.disk_space.os.statvfs', return_value=fake):
            result = sample(self.config, self.paths)
        self.assertTrue(all(item['free_bytes'] == 5 * 4096 for item in result))
        self.assertEqual(len(result), len({item['device'] for item in result}))
        self.assertIn(str(self.exchange), [p for item in result for p in item['paths']])

    def test_separate_apply_and_state_volumes_are_measured(self):
        wanted = locations(self.config, self.paths)
        self.assertIn(self.config.repository.parent / 'specroad-apply', wanted)
        self.assertIn(self.paths.state, wanted)
        self.assertIn(Path('/var/tmp'), wanted)
        self.assertNotIn(self.paths.runtime, wanted)

    def test_uncreated_child_uses_its_existing_parent_filesystem(self):
        from specroad_control.disk_space import existing
        path, device = existing(self.home / 'not-created/child')
        self.assertEqual(path, self.home)
        self.assertEqual(device, self.home.stat().st_dev)

    def test_bad_statvfs_counters_do_not_authorize(self):
        for fake in (SimpleNamespace(f_bavail=-1, f_frsize=4096, f_bsize=4096),
                     SimpleNamespace(f_bavail=100, f_frsize=0, f_bsize=0)):
            with patch('specroad_control.disk_space.os.statvfs', return_value=fake):
                with self.assertRaises(ControlError): self.guard().require()
