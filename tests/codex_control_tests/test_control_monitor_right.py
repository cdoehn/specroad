"""Bounded independent reads, stale fallback and namespace checks."""
import json
import threading
import time
from unittest.mock import patch
from specroad_control import monitor_data
from specroad_control.errors import ControlError
from specroad_control.local import Paths, json_write
from specroad_control.monitor import Refresh, once
from specroad_control.status_wire import encoded
from codex_control_tests.automation_support import AutomationCase


class MonitorGuards(AutomationCase):
    def test_one_hung_instance_does_not_block_another_or_exit(self):
        second = Paths.discover(instance='dev2')
        release = threading.Event()
        completed = threading.Event()
        calls = []
        def collector(path):
            calls.append(path.instance)
            if path.instance == 'default':
                release.wait(3)
            else:
                completed.set()
            return {'instance': path.instance, 'state': {}, 'stale': False, 'errors': {}}
        refresh = Refresh([self.paths, second], collector=collector, interval=20, timeout=0.1)
        try:
            refresh.poll()
            self.assertTrue(completed.wait(2))
            deadline = time.monotonic()+2
            while 'dev2' in refresh.pending and time.monotonic() < deadline:
                time.sleep(0.01)
                refresh.poll()
            time.sleep(0.11)
            refresh.poll()
            refresh.poll(force=True)
            self.assertEqual(calls.count('default'), 1)
            rows = {row['instance']: row for row in refresh.snapshot()['instances']}
            self.assertTrue(rows['default']['stale'])
            self.assertFalse(rows['dev2']['stale'])
            before = time.monotonic()
            refresh.close()
            self.assertLess(time.monotonic()-before, 0.5)
        finally:
            release.set()
            refresh.close()

    def test_once_has_one_budget_and_never_claims_an_unfinished_source_is_live(self):
        release = threading.Event()
        def slow(path):
            release.wait(3)
            return {'instance': path.instance, 'stale': False, 'state': {}, 'errors': {}}
        try:
            before = time.monotonic()
            report = once([self.paths], timeout=0.1, collector=slow)
            self.assertLess(time.monotonic()-before, 1)
            self.assertTrue(report['instances'][0]['stale'])
            self.assertFalse(report['instances'][0]['worker_reachable'])
        finally:
            release.set()

    def test_late_response_stays_stale_and_snapshots_are_detached(self):
        now = [0.0]
        refresh = Refresh([self.paths], clock=lambda: now[0])
        refresh.pending['default'] = 0
        refresh.messages.put(('default', {'instance': 'default', 'state': {'phase': 'working'},
                                         'stale': False, 'errors': {}}))
        now[0] = 6
        refresh.poll()
        report = refresh.snapshot()
        self.assertTrue(report['instances'][0]['stale'])
        report['instances'][0]['state']['phase'] = 'changed'
        self.assertEqual(refresh.snapshot()['instances'][0]['state']['phase'], 'working')
        refresh.close()

    def test_bad_socket_reply_and_corrupt_snapshot_are_reported_without_repair(self):
        json_write(self.paths.state_file, {'broken': True})
        before = self.paths.state_file.read_bytes()
        with patch.object(monitor_data, 'request', return_value={'state': 'bad'}), \
                patch.object(monitor_data, 'systemd', side_effect=ControlError('systemd_unavailable', 'offline')):
            result = monitor_data.collect(self.paths)
        self.assertTrue(result['stale'])
        self.assertEqual(result['errors']['ipc'], 'protocol_error')
        self.assertEqual(result['errors']['state'], 'invalid_state')
        self.assertEqual(self.paths.state_file.read_bytes(), before)

    def test_cross_instance_reply_cannot_be_shown_as_live(self):
        second = Paths.discover(instance='dev2')
        with patch.object(monitor_data, 'request', return_value={'state': {'instance': 'default'}}), \
                patch.object(monitor_data, 'systemd', return_value={}):
            result = monitor_data.collect(second)
        self.assertTrue(result['stale'])
        self.assertEqual(result['errors']['ipc'], 'wrong_scope')
        self.assertFalse(second.home.exists())

    def test_invalid_discovered_instance_does_not_hide_other_instances(self):
        container = self.paths.home/'instances'
        container.mkdir(mode=0o700)
        (container/'dev2').mkdir(mode=0o700)
        (container/'bad').symlink_to(self.home)
        paths, errors = monitor_data.discover(all_instances=True)
        self.assertEqual([p.instance for p in paths], ['default', 'dev2'])
        self.assertEqual(errors[0]['instance'], 'bad')

    def test_status_wire_allows_details_but_refuses_unbounded_output(self):
        value = {'ok': True, 'state': {'detail': 'x'*12000}}
        self.assertEqual(json.loads(encoded(value)), value)
        self.assertEqual(json.loads(encoded({'ok': True, 'state': 'x'*65536}))['error'], 'status_too_large')

    def test_systemd_reader_only_shows_the_selected_unit_with_a_deadline(self):
        second = Paths.discover(instance='dev2')
        reply = type('Reply', (), {'returncode': 0, 'stdout': 'LoadState=loaded\nFragmentPath=' + str(second.unit) + '\n'})()
        with patch.object(monitor_data.subprocess, 'run', return_value=reply) as call:
            monitor_data.systemd(second)
        self.assertEqual(call.call_args.args[0][2:4], ['show', second.unit.name])
        self.assertLessEqual(call.call_args.kwargs['timeout'], 1)


    def test_open_sqlite_sidecars_produce_a_source_error_without_recovery(self):
        from specroad_control.monitor_history import history
        from specroad_control.local import write_private
        sidecar = self.paths.state/'automation.sqlite3-journal'
        write_private(sidecar, b'pending-writer')
        with self.assertRaises(ControlError) as caught:
            history(self.paths, self.config)
        self.assertEqual(caught.exception.code, 'history_busy')
        self.assertEqual(sidecar.read_bytes(), b'pending-writer')

    def test_malformed_live_lifecycle_is_not_presented_as_fresh(self):
        with patch.object(monitor_data, 'request', return_value={'state': {'phase': []}}), \
                patch.object(monitor_data, 'systemd', return_value={}):
            result = monitor_data.collect(self.paths)
        self.assertTrue(result['stale'])
        self.assertEqual(result['errors']['ipc'], 'invalid_state')
