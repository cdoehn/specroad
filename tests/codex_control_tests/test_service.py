import subprocess
from unittest.mock import patch
from specroad_control import service
from specroad_control.errors import ControlError
from specroad_control.local import read_private, write_private
from codex_control_tests.support import LocalCase

class ServiceTests(LocalCase):
    def fake_manager(self):
        self.calls = []
        def command(args):
            self.calls.append(args)
            if args[0] == 'show':
                return subprocess.CompletedProcess(args, 0, 'LoadState=loaded\nActiveState=inactive\nUnitFileState=static\nFragmentPath=\n', '')
            return subprocess.CompletedProcess(args, 0, '', '')
        p = patch.object(service, 'command', side_effect=command)
        p.start(); self.addCleanup(p.stop)

    def test_install_neither_starts_nor_enables(self):
        self.fake_manager()
        result = service.install(self.paths)
        self.assertTrue(result['installed']); self.assertFalse(result['started'])
        self.assertFalse(result['autostart'])
        self.assertEqual([a[0] for a in self.calls], ['show', 'daemon-reload'])
        config = read_private(self.paths.config)
        service.install(self.paths)
        self.assertEqual(read_private(self.paths.config), config)

    def test_start_only_addresses_own_unit(self):
        self.fake_manager(); service.install(self.paths); self.calls.clear()
        result = service.start(self.paths)
        self.assertTrue(result['start_requested'])
        self.assertEqual(self.calls[-1], ['start', service.UNIT])

    def test_stop_does_not_need_valid_config(self):
        self.fake_manager(); service.install(self.paths)
        write_private(self.paths.config, b'broken')
        result = service.stop(self.paths)
        self.assertTrue(result['graceful'])
        self.assertEqual(self.calls[-1], ['--no-block', 'stop', service.UNIT])

    def test_foreign_service_is_preserved(self):
        self.fake_manager()
        write_private(self.paths.unit, b'other unit')
        with self.assertRaises(ControlError): service.install(self.paths)
        self.assertEqual(read_private(self.paths.unit), b'other unit')

    def test_manager_failure_prevents_installation(self):
        with patch.object(service, 'command', return_value=subprocess.CompletedProcess([], 1, '', 'bus unavailable')):
            with self.assertRaises(ControlError): service.install(self.paths)
        self.assertFalse(self.paths.config.exists())
        self.assertFalse(self.paths.unit.exists())

    def test_native_systemd_unit_validation(self):
        unit = self.home / service.UNIT
        unit.write_text(service.unit_text(self.paths))
        result = subprocess.run(['/usr/bin/systemd-analyze', 'verify', str(unit)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
