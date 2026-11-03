"""Evidence and lifecycle boundaries remain intact when operating limits change."""
from dataclasses import replace
import io
import json
import threading
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import redirect_stdout, redirect_stderr

from specroad_control.automation import Gate
from specroad_control.cli import main
from specroad_control.disk_space import DiskGuard, GB, limits_path, minimum_bytes, read_limits, set_limit, sample
from specroad_control.errors import ControlError
from specroad_control.local import write_private, read_private
from codex_control_tests.automation_support import AutomationCase
from codex_control_tests.apply_reconcile_support import ReconcileCase
from codex_control_tests.test_recovery import LedgerContext
from codex_control_tests.test_disk_space import volumes


class StorageBoundaryTests(AutomationCase):
    def setUp(self):
        super().setUp()
        set_limit(self.paths, 10)

    def test_decimal_conversion_does_not_add_a_byte_for_binary_float_noise(self):
        self.assertEqual(minimum_bytes(0.000000127), 127)
        self.assertEqual(minimum_bytes(0.0000001271), 128)
        self.assertEqual(minimum_bytes(10), 10_000_000_000)

    def test_filesystem_switch_during_measurement_is_not_accepted(self):
        info = SimpleNamespace(f_bavail=10000, f_frsize=4096, f_bsize=4096)
        actual_device = self.home.stat().st_dev
        with patch('specroad_control.disk_space.locations', return_value=[self.home]), \
                patch('specroad_control.disk_space.existing', return_value=(self.home, actual_device + 1)), \
                patch('specroad_control.disk_space.os.statvfs', return_value=info):
            with self.assertRaises(ControlError) as caught: DiskGuard(self.config, self.paths).require()
        self.assertEqual(caught.exception.code, 'disk_space_unavailable')

    def test_invalid_workspace_is_reported_as_a_storage_stop(self):
        with patch('specroad_control.disk_space.sample', side_effect=ControlError('invalid_thread_workspace', 'changed')):
            with self.assertRaises(ControlError) as caught: DiskGuard(self.config, self.paths).require()
        self.assertEqual(caught.exception.code, 'disk_space_unavailable')
        self.assertEqual(caught.exception.details['disk_space']['measurement_error'], 'invalid_thread_workspace')

    def test_lowest_observation_on_shared_volume_wins(self):
        def vfs(path):
            return SimpleNamespace(f_bavail=1 if path == self.dev else 100, f_frsize=GB, f_bsize=GB)
        with patch('specroad_control.disk_space.locations', return_value=[self.home, self.dev]), \
                patch('specroad_control.disk_space.os.statvfs', side_effect=vfs):
            measured = sample(self.config, self.paths)
        self.assertEqual(len(measured), 1)
        self.assertEqual(measured[0]['free_bytes'], GB)

    def test_guard_tracks_new_workspace_after_handover_without_clearing_stop(self):
        guard = DiskGuard(self.config, self.paths)
        new = replace(self.config, thread_cwd=self.dev.parent)
        with patch('specroad_control.disk_space.sample', return_value=volumes(GB)):
            with self.assertRaises(ControlError): guard.require()
        guard.rebind(new)
        self.assertEqual(guard.config, new)
        with patch('specroad_control.disk_space.sample', return_value=volumes(50 * GB)) as measured:
            with self.assertRaises(ControlError): guard.require()
        measured.assert_not_called()

    def test_new_workspace_is_used_on_next_healthy_measurement(self):
        guard = DiskGuard(self.config, self.paths)
        new = replace(self.config, thread_cwd=self.dev.parent)
        guard.rebind(new)
        with patch('specroad_control.disk_space.sample', return_value=volumes(20 * GB)) as measured:
            guard.require()
        self.assertEqual(measured.call_args.args[0], new)

    def test_status_copy_cannot_release_a_latched_stop(self):
        guard = DiskGuard(self.config, self.paths)
        with patch('specroad_control.disk_space.sample', return_value=volumes(GB)):
            with self.assertRaises(ControlError): guard.require()
        status = guard.snapshot(); status['filesystems'][0]['free_bytes'] = 100 * GB
        status['sufficient'] = True
        self.assertFalse(guard.snapshot()['sufficient'])
        self.assertEqual(guard.snapshot()['filesystems'][0]['free_bytes'], GB)

    def test_background_observation_latches_before_next_dispatch_gate(self):
        guard = DiskGuard(self.config, self.paths); gate = Gate(guard); calls = []
        with patch('specroad_control.disk_space.sample', return_value=volumes(GB)):
            errors = []
            def observe():
                try: guard.require()
                except ControlError as exc: errors.append(exc.code)
            thread = threading.Thread(target=observe); thread.start(); thread.join(timeout=2)
            self.assertFalse(thread.is_alive()); self.assertEqual(errors, ['low_disk_space'])
        with patch('specroad_control.disk_space.sample', return_value=volumes(20 * GB)):
            with self.assertRaises(ControlError): gate.enter(lambda: calls.append('dispatched'))
        self.assertEqual(calls, [])

    def test_cli_can_set_limit_but_cannot_apply_setup_arguments(self):
        before = self.paths.config.read_bytes(); output = io.StringIO()
        with redirect_stdout(output): self.assertEqual(main(['disk-space', '--min-free-gb', '15']), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result['min_free_bytes'], 15 * GB)
        self.assertFalse(result['service_started'] or result['model_called'])
        self.assertEqual(self.paths.config.read_bytes(), before)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(['start', '--min-free-gb', '15'])
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(['disk-space', '--min-free-gb', '15', '--thread-id', self.thread])

    def test_status_command_reports_low_space_without_starting_anything(self):
        output = io.StringIO()
        with patch('specroad_control.disk_space.sample', return_value=volumes(GB)), redirect_stdout(output):
            self.assertEqual(main(['disk-space']), 0)
        result = json.loads(output.getvalue())
        self.assertFalse(result['sufficient']); self.assertEqual(result['error'], 'low_disk_space')
        self.assertFalse((self.codex_home / 'calls.jsonl').exists())

    def test_setting_can_be_changed_without_loading_broken_main_configuration(self):
        write_private(self.paths.config, b'preserve invalid main config')
        self.assertTrue(set_limit(self.paths, 12)['saved'])
        self.assertEqual(self.paths.config.read_bytes(), b'preserve invalid main config')

    def test_unsafe_limits_file_is_not_overwritten(self):
        path = limits_path(self.paths); before = path.read_bytes(); path.chmod(0o644)
        with self.assertRaises(ControlError): set_limit(self.paths, 15)
        self.assertEqual(path.read_bytes(), before)

    def test_limits_symlink_is_not_followed_or_replaced(self):
        path = limits_path(self.paths); path.unlink()
        target = self.home / 'private-target'; write_private(target, b'preserve')
        path.symlink_to(target)
        with self.assertRaises(ControlError): read_limits(self.paths)
        with self.assertRaises(ControlError): set_limit(self.paths, 15)
        self.assertEqual(read_private(target), b'preserve'); self.assertTrue(path.is_symlink())


class StorageRecoveryTests(ReconcileCase):
    def test_setting_limit_preserves_queued_recovery_and_bound_main_config(self):
        from specroad_control.apply_reconcile import enqueue
        from specroad_control.apply_reconcile_history import validate_history
        enqueue(self.paths, self.final['path'])
        files = [self.paths.config, self.paths.state / 'automation.sqlite3', *self.directory.iterdir()]
        before = {p: p.read_bytes() for p in files}
        set_limit(self.paths, 10)
        self.assertEqual({p: p.read_bytes() for p in files}, before)
        with LedgerContext(self.paths, self.config) as ledger:
            self.assertIsNotNone(validate_history(ledger))
            self.assertEqual(ledger.current()['sha'], self.seed['sha256'])
        self.assertFalse((self.codex_home / 'calls.jsonl').exists())

    def test_low_space_at_recovery_gate_does_not_advance_or_consume_request(self):
        from specroad_control.apply_reconcile import enqueue
        from specroad_control.apply_reconcile_history import validate_history
        from specroad_control.automation import Engine
        from codex_control_tests.apply_reconcile_support import ReconcileCore
        from codex_control_tests.automation_support import FakeCodex
        enqueue(self.paths, self.final['path']); set_limit(self.paths, 10)
        guard = DiskGuard(self.config, self.paths); codex = FakeCodex(self); codex.activity = lambda: 'idle'
        with Engine(self.config, self.paths, Gate(guard), core=ReconcileCore(), codex=codex) as engine:
            with patch('specroad_control.disk_space.sample', return_value=volumes(GB)):
                with self.assertRaises(ControlError): engine.tick()
        with LedgerContext(self.paths, self.config) as ledger:
            self.assertIsNotNone(validate_history(ledger))
            self.assertEqual(ledger.current()['sha'], self.seed['sha256'])
            self.assertEqual(ledger.request_contract()['clarifications_remaining'], 2)
        self.assertEqual(codex.calls, 0)
