import configparser
import contextlib
import io
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from unittest.mock import patch
from specroad_control import cli, service
from specroad_control.config import initialize, load
from specroad_control.daemon import read_state, request, scope
from specroad_control.errors import ControlError
from specroad_control.local import Paths, REPO, decode_object, json_read, json_write, outside, private_dir, read_private, write_private
from codex_control_tests.support import LocalCase

class RobustnessTests(LocalCase):
    def invoke_worker_once(self):
        return subprocess.run([sys.executable, '-B', str(self.paths.home / 'releases' / ('a' * 40) / 'control'), 'run'], capture_output=True, text=True, timeout=5)

    def test_unknown_config_keys_rejected_without_disclosing_values(self):
        initialize(self.paths)
        original = read_private(self.paths.config)
        write_private(self.paths.config, original + b'private_typo = "SECRET_SENTINEL"\n')
        with self.assertRaises(ControlError) as caught: load(self.paths)
        self.assertEqual(caught.exception.code, 'invalid_config')
        self.assertNotIn('SECRET_SENTINEL', str(caught.exception))

    def test_format_boolean_is_not_version_one(self):
        initialize(self.paths)
        write_private(self.paths.config, read_private(self.paths.config).replace(b'format_version = 1', b'format_version = true'))
        with self.assertRaises(ControlError): load(self.paths)

    def test_session_must_be_empty_or_canonical_uuid(self):
        initialize(self.paths)
        original = read_private(self.paths.config)
        for value in ('--last', 'latest', 'wrong\nthread', 'A0B8C656-1234-4567-ABCD-001122334455'):
            candidate = original.replace(b'session_id = ""', ('session_id = '+json.dumps(value)).encode())
            write_private(self.paths.config, candidate)
            with self.subTest(value=value), self.assertRaises(ControlError): load(self.paths)
        value = 'a0b8c656-1234-7567-abcd-001122334455'
        write_private(self.paths.config, original.replace(b'session_id = ""', ('session_id = '+json.dumps(value)).encode()))
        self.assertEqual(load(self.paths).session_id, value)  # UUIDs need not be v4.

    def test_overlapping_repository_and_exchange_rejected(self):
        initialize(self.paths)
        value = 'format_version = 1\n[develop]\nrepository = "/tmp/dev"\nsession_id = ""\n[patchharbor]\nexchange = "/tmp/dev/exchange"\n'
        write_private(self.paths.config, value.encode())
        with self.assertRaises(ControlError): load(self.paths)

    def test_config_and_state_outside_configured_dev(self):
        initialize(self.paths)
        value = 'format_version = 1\n[develop]\nrepository = '+json.dumps(str(self.home))+'\nsession_id = ""\n[patchharbor]\nexchange = "/tmp/separate-exchange"\n'
        write_private(self.paths.config, value.encode())
        with self.assertRaises(ControlError) as caught: load(self.paths)
        self.assertEqual(caught.exception.code, 'local_path_in_repository')

    def test_relative_control_home_is_rejected(self):
        with patch.dict(os.environ, {'SPECROAD_CONTROL_HOME': 'relative'}):
            with self.assertRaises(ControlError): Paths.discover()

    def test_oversized_and_hardlinked_private_files_rejected(self):
        write_private(self.paths.config, b'x'*65537)
        with self.assertRaises(ControlError): read_private(self.paths.config)
        self.paths.config.unlink()
        write_private(self.paths.config, b'original')
        os.link(self.paths.config, self.paths.config.parent/'other-link')
        with self.assertRaises(ControlError): read_private(self.paths.config)

    def test_duplicate_json_and_non_finite_values_rejected(self):
        for data in (b'{"desired":"running","desired":"paused"}', b'{"n":NaN}', b'[]', b'{} trailing'):
            with self.subTest(data=data), self.assertRaises(ValueError): decode_object(data)

    def test_corrupted_state_is_preserved_and_prevents_start(self):
        initialize(self.paths)
        write_private(self.paths.state_file, b'{"invalid":')
        result = self.invoke_worker_once()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(read_private(self.paths.state_file), b'{"invalid":')
        self.assertFalse(self.paths.socket.exists())

    def test_unresolved_work_is_not_replayed(self):
        child, reply = self.spawn()
        request(self.paths, 'stop'); child.wait(timeout=5)
        previous = reply['state']; previous.update(phase='working', active_job=True)
        json_write(self.paths.state_file, previous)
        result = self.invoke_worker_once()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['error'], 'unresolved_job')
        self.assertEqual(json_read(self.paths.state_file), previous)

    def test_invalid_state_schema_and_phase_are_rejected(self):
        child, reply = self.spawn(); request(self.paths, 'stop'); child.wait(timeout=5)
        for delta in ({'schema': True}, {'active_job': 'no'}, {'updated_at': float('inf')},
                      {'pid': True}, {'run_id': 'unknown'}, {'phase': 'working', 'active_job': False}):
            previous = {**reply['state'], **delta}
            json_write(self.paths.state_file, previous)
            with self.subTest(delta=delta), self.assertRaises(ControlError): read_state(self.paths)

    def test_stale_socket_can_be_recovered(self):
        private_dir(self.paths.runtime)
        with socket.socket(socket.AF_UNIX) as old:
            old.bind(str(self.paths.socket))
            self.paths.socket.chmod(0o600)
        child, reply = self.spawn()
        self.assertEqual(reply['state']['phase'], 'idle')
        request(self.paths, 'stop'); self.assertEqual(child.wait(timeout=5), 0)

    def test_existing_live_socket_not_removed(self):
        initialize(self.paths); private_dir(self.paths.runtime)
        with socket.socket(socket.AF_UNIX) as live:
            live.bind(str(self.paths.socket)); live.listen()
            original = self.paths.socket.stat().st_ino
            result = self.invoke_worker_once()
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.paths.socket.stat().st_ino, original)

    def test_foreign_regular_socket_path_not_removed(self):
        initialize(self.paths); private_dir(self.paths.runtime)
        write_private(self.paths.socket, b'keep')
        result = self.invoke_worker_once()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(read_private(self.paths.socket), b'keep')

    def test_malformed_and_reset_clients_do_not_kill_worker(self):
        child, _ = self.spawn()
        bad = [b'[]\n', b'{}\n', b'NOT_JSON\n', b'{"command":"status","command":"stop"}\n', b'x'*4100+b'\n']
        for data in bad:
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(2); client.connect(str(self.paths.socket)); client.sendall(data)
                response = json.loads(client.recv(8192))
                self.assertFalse(response['ok'])
            self.assertIsNone(child.poll())
        with socket.socket(socket.AF_UNIX) as client:
            client.connect(str(self.paths.socket))
        self.assertTrue(request(self.paths, 'status')['ok'])

    def test_slow_client_cannot_hold_graceful_stop(self):
        child, _ = self.spawn()
        with socket.socket(socket.AF_UNIX) as client:
            client.connect(str(self.paths.socket)); client.sendall(b'{')
            child.send_signal(signal.SIGTERM)
            self.assertEqual(child.wait(timeout=3), 0)

    def test_wrong_config_scope_cannot_pause_worker(self):
        child, _ = self.spawn()
        other = Paths(self.home/'other.toml', self.paths.state, self.paths.runtime, self.paths.unit)
        with self.assertRaises(ControlError) as caught: request(other, 'pause')
        self.assertEqual(caught.exception.code, 'wrong_scope')
        self.assertEqual(request(self.paths, 'status')['state']['phase'], 'idle')
        self.assertIsNone(child.poll())

    def test_status_distinguishes_saved_state_from_live_state(self):
        child, _ = self.spawn(); request(self.paths, 'stop'); child.wait(timeout=5)
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture), patch.object(service, 'inspect', side_effect=ControlError('systemd_unavailable', 'Unavailable')):
            code = cli.main(['status'])
        result = json.loads(capture.getvalue())
        self.assertEqual(code, 0)
        self.assertFalse(result['worker_reachable']); self.assertIsNone(result['state'])
        self.assertEqual(result['last_state']['phase'], 'stopped')

    def test_service_policy_is_machine_contract_not_presentation(self):
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        parser.read_string(service.unit_text(self.paths))
        values = parser['Service']
        self.assertEqual(values['Restart'], 'no')
        self.assertEqual(values['KillMode'], 'mixed')
        self.assertEqual(values['SendSIGKILL'], 'no')
        self.assertEqual(values['TimeoutStopSec'], 'infinity')
        self.assertFalse(parser.has_section('Install'))
        self.assertNotIn('ExecStop', values)  # No asynchronous ExecStop followed by child termination.

    def test_unit_overrides_and_foreign_fragments_rejected(self):
        for extra in ({'DropInPaths': '/tmp/override.conf'}, {'UnitFileState': 'enabled'},
                      {'FragmentPath': '/usr/lib/systemd/user/specroad-control.service'}):
            with self.subTest(extra=extra), self.assertRaises(ControlError):
                service.verify_properties(self.paths, {'LoadState': 'loaded', **extra})

    def test_unit_path_injection_is_rejected_or_escaped(self):
        with self.assertRaises(ControlError): service.quoted('/tmp/x\nExecStart=bad')
        # Machine-readable systemd escaping, not console/UI assertions.
        escaped = service.quoted('/tmp/$HOME/%h/"x"', command_line=True)
        self.assertEqual(escaped, '"/tmp/$$HOME/%%h/\\"x\\""')

    def test_unit_pins_empty_runtime_environment(self):
        with patch.dict(os.environ, {'XDG_RUNTIME_DIR': ''}):
            paths = Paths.discover()
            self.assertEqual(paths.runtime, paths.home/'run')
            self.assertIn('Environment="SPECROAD_CONTROL_HOME='+str(paths.home)+'"', service.unit_text(paths))

    def test_start_while_stopping_is_not_queued(self):
        props = {'LoadState': 'loaded', 'ActiveState': 'inactive', 'UnitFileState': 'static'}
        with patch.object(service, 'inspect', return_value=props), patch.object(service, 'checked') as calls:
            service.install(self.paths)
            props['ActiveState'] = 'deactivating'; calls.reset_mock()
            with self.assertRaises(ControlError) as caught: service.start(self.paths)
            self.assertEqual(caught.exception.code, 'stopping')
            calls.assert_not_called()

    def test_reinstall_owned_inactive_unit_preserves_configuration(self):
        props = {'LoadState': 'loaded', 'ActiveState': 'inactive', 'UnitFileState': 'static'}
        with patch.object(service, 'inspect', return_value=props), patch.object(service, 'checked'):
            service.install(self.paths)
            config = read_private(self.paths.config)
            write_private(self.paths.unit, service.OWNER.encode()+b'[Service]\nExecStart=/old/location\n')
            service.install(self.paths)
            self.assertEqual(read_private(self.paths.unit), service.unit_text(self.paths).encode())
            self.assertEqual(read_private(self.paths.config), config)

    def test_install_does_not_change_active_service(self):
        props = {'LoadState': 'loaded', 'ActiveState': 'active', 'UnitFileState': 'static'}
        with patch.object(service, 'inspect', return_value=props), patch.object(service, 'checked') as calls:
            with self.assertRaises(ControlError): service.install(self.paths)
            calls.assert_not_called()
        self.assertFalse(self.paths.config.exists())
