"""Restart races preserve old work and publish only one current execution cycle."""
from contextlib import closing
from dataclasses import replace
from unittest.mock import Mock, patch

from codex_control_tests.automation_support import AutomationCase, package
from codex_control_tests.test_start_current import configure_start_case
from specroad_control import start_current, handover_queue, service
from specroad_control.config import render
from specroad_control.errors import ControlError
from specroad_control.job_contract import scope
from specroad_control.ledger import Ledger
from specroad_control.local import json_read, json_write, read_private, write_private, lock


class StartRightTests(AutomationCase):
    setUp = configure_start_case
    def request(self):
        return start_current.enqueue(self.paths, self.config)

    def test_pause_after_capture_reuses_the_native_source_and_preserves_old_ledger(self):
        original = self.paths.ledger.read_bytes()
        self.request()
        self.core.checkpoint.side_effect = lambda: (self.engine.gate.set(False) or self.fresh)
        self.engine.tick()
        self.core.checkpoint.side_effect = None
        self.engine.gate.set(True)
        self.engine.tick()
        self.assertEqual(self.core.checkpoint.call_count, 1)
        self.assertEqual((self.paths.state / 'automation.sqlite3').read_bytes(), original)

    def test_failed_finalization_preserves_original_handover_bytes_and_never_refills(self):
        request = self.request()
        old = b'{"old": "opaque deferred request"}\n'
        write_private(self.paths.state / 'thread-handover-request.json', old)
        with patch.object(start_current, '_finish', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                self.engine.tick()
        cycle = start_current.active_cycle(self.paths)
        with closing(Ledger(self.paths.ledger, scope(self.config))) as ledger:
            ledger.db.execute('UPDATE clarification_budgets SET remaining=19')
        self.engine.tick()
        self.assertEqual(start_current.active_cycle(self.paths), cycle)
        self.assertIsNone(start_current.pending(self.paths))
        saved = self.paths.state / 'start-requests' / request['id'] / 'superseded'
        self.assertEqual(read_private(saved / 'thread-handover-request.json'), old)
        with closing(Ledger(self.paths.ledger, scope(self.config))) as ledger:
            self.assertEqual(ledger.request_contract()['clarifications_remaining'], 19)
        self.assertEqual(self.core.checkpoint.call_count, 1)

    def test_queued_foreign_package_waits_without_dispatching_another_developer(self):
        patch_path = self.exchange / 'foreign.zip'
        original = package(patch_path, {'kind': 'patch', 'binding': self.fresh['binding']})
        self.request()
        self.assertIn('retry_after', self.engine.tick())
        self.assertEqual(self.engine.summary()['start_wait_reason'], 'pending_patch')
        self.assertIsNone(start_current.active_cycle(self.paths))
        self.assertEqual(self.codex.calls, 0)
        self.assertEqual(self.core.patch(patch_path)['sha256'], original['sha256'])

    def test_late_foreign_result_recaptures_actual_tree_before_activation(self):
        self.request()
        self.core.checkpoint.side_effect = lambda: (self.engine.gate.set(False) or self.fresh)
        self.engine.tick()
        next_source = self.result('later-current.zip', dirty=False,
            development_contract=self.fresh['development_contract'])
        self.core.checkpoint.side_effect = None
        self.core.checkpoint.return_value = next_source
        self.core.call.side_effect = lambda _op, _path: {
            'sha256': next_source['sha256'], 'binding': next_source['binding'],
            'repository_path': next_source['repository_path'], 'dirty': False}
        self.engine.gate.set(True)
        self.engine.tick()
        self.assertEqual(start_current.active_cycle(self.paths)['source_sha256'], next_source['sha256'])
        self.assertEqual(self.core.checkpoint.call_count, 2)
        self.assertTrue(list((self.paths.state / 'start-requests').rglob(self.fresh['sha256'] + '.json')))

    def test_line_change_does_not_dispatch_from_another_scope(self):
        self.request()
        self.engine.config = replace(self.config, repo_id='00000000-0000-4000-8000-000000000001')
        write_private(self.paths.config, render(self.engine.config).encode())
        with self.assertRaises(ControlError) as raised:
            self.engine.tick()
        self.assertEqual(raised.exception.code, 'runtime_configuration_changed')
        self.assertEqual(self.codex.calls, 0)
        self.core.checkpoint.assert_not_called()

    def test_explicit_start_supersedes_deferred_handover_without_loading_its_history(self):
        raw = b'{"broken historical handover": true}'
        write_private(self.paths.state / 'thread-handover-request.json', raw)
        with patch.object(service, 'verify_owned', return_value={'ActiveState': 'active'}), \
                patch.object(service, 'unit_text', return_value='owned'), \
                patch.object(service, 'read_private', return_value=b'owned'), \
                patch.object(service, 'checked'), patch('specroad_control.ipc.request'):
            self.assertTrue(service.start(self.paths, from_current=True)['queued'])
        self.assertEqual(handover_queue.startup(self.paths), (self.config, None))
        self.engine.tick()
        self.assertIsNotNone(start_current.active_cycle(self.paths))

    def test_operation_lock_refuses_concurrent_operator_start_without_second_request(self):
        self.request()
        original = read_private(self.paths.state / start_current.REQUEST)
        with lock(self.paths.state / 'operation.lock'):
            with self.assertRaises(ControlError):
                service.start(self.paths, from_current=True)
        self.assertEqual(read_private(self.paths.state / start_current.REQUEST), original)

    def test_status_remains_available_with_explicit_start_and_damaged_old_pointer(self):
        self.request()
        json_write(self.paths.state / start_current.ACTIVE, {'damaged': True})
        self.assertTrue(start_current.public_status(self.paths)['pending'])
        self.engine.tick()
        self.assertFalse(start_current.public_status(self.paths)['pending'])
