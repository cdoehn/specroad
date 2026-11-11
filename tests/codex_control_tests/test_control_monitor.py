"""Monitor data contracts; no terminal layout or prose assertions."""
import json
from unittest.mock import patch
from specroad_control import monitor_data
from specroad_control.errors import ControlError
from specroad_control.local import Paths, json_write
from codex_control_tests.automation_support import AutomationCase


class MonitorDataTests(AutomationCase):
    def read(self, reply=None, error=None):
        with patch.object(monitor_data, 'request', return_value=reply, side_effect=error) as request, \
                patch.object(monitor_data, 'systemd', return_value={'ActiveState': 'inactive'}):
            result = monitor_data.collect(self.paths)
        request.assert_called_once_with(self.paths, 'status')
        return result

    def test_live_observation_preserves_lifecycle_proof_and_budget(self):
        state = {'schema': 1, 'active_job': True, 'pid': 123, 'run_id': self.thread,
                 'started_at': 1, 'updated_at': 2, 'phase': 'working', 'desired': 'running', 'automation': {
            'stage': 'checking_dispatch', 'validation': {'phase': 'validating', 'visited': 300},
            'request_contract': {'clarifications_remaining': 2}}}
        result = self.read({'state': state})
        self.assertFalse(result['stale'])
        self.assertTrue(result['worker_reachable'])
        self.assertEqual(result['state'], state)
        self.assertEqual(result['source'], 'ipc')
        self.assertEqual(result['configured_bindings']['repo_id'], self.repo_id)

    def test_offline_file_is_explicitly_stale(self):
        state = {'schema': 1, 'phase': 'working', 'desired': 'running', 'active_job': True,
                 'pid': 123, 'run_id': self.thread, 'started_at': 1, 'updated_at': 2}
        json_write(self.paths.state_file, state)
        result = self.read(error=ControlError('not_running', 'offline'))
        self.assertTrue(result['stale'])
        self.assertFalse(result['worker_reachable'])
        self.assertEqual(result['state'], state)
        self.assertEqual(result['source'], 'state-file')

    def test_monitor_does_not_modify_state_history_or_create_locks(self):
        def files():
            return {str(p): p.read_bytes() for p in self.paths.home.rglob('*') if p.is_file()}
        before = files()
        self.read({'state': {'phase': 'paused'}})
        self.read(error=ControlError('not_running', 'offline'))
        self.assertEqual(files(), before)

    def test_all_discovery_is_read_only_and_separates_instances(self):
        second = Paths.discover(instance='dev2')
        json_write(second.state_file, {'fixture': True})
        paths, errors = monitor_data.discover(all_instances=True)
        self.assertEqual([p.instance for p in paths], ['default', 'dev2'])
        self.assertEqual(errors, [])
        self.assertFalse(second.config.exists())


    def test_persisted_budget_and_job_are_read_without_opening_live_sqlite(self):
        from specroad_control.ledger import Ledger
        from specroad_control.job_contract import scope, new_contract
        ledger = Ledger(self.paths.state/'automation.sqlite3', scope(self.config))
        ledger.bind_contract(new_contract(2, version=4))
        ledger.close()
        before = (self.paths.state/'automation.sqlite3').read_bytes()
        from specroad_control import monitor_history
        native = monitor_history.sqlite3.connect
        with patch.object(monitor_history.sqlite3, 'connect', wraps=native) as opened:
            value = monitor_history.history(self.paths, self.config)
        self.assertEqual(opened.call_args.args, (':memory:',))
        self.assertEqual(value['clarification_budgets']['remaining'], 2)
        self.assertEqual(value['job']['sha'], self.seed['sha256'])
        self.assertEqual((self.paths.state/'automation.sqlite3').read_bytes(), before)
