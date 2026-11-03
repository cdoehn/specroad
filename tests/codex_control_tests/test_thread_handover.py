"""Offline thread transfer against isolated metadata and native-reader doubles."""
from contextlib import closing
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from unittest.mock import patch
from uuid import uuid4

from specroad_control.automation import Engine, Gate
from specroad_control.commands import configure
from specroad_control.config import load
from specroad_control.errors import ControlError
from specroad_control.handover import handover
from specroad_control.job_contract import scope, new_contract
from specroad_control.ledger import Ledger
from specroad_control.local import json_write, lock, private_dir, write_private
from codex_control_tests.automation_support import AutomationCase, FakeCodex, FakeCore


class HandoverCase(AutomationCase):
    def setUp(self):
        super().setUp()
        self.target = str(uuid4())
        self.target_cwd = self.dev.parent
        self.metadata()
        self.paused = {'schema': 1, 'desired': 'paused', 'phase': 'stopped',
                       'active_job': False, 'pid': 123, 'run_id': str(uuid4()),
                       'started_at': 1.0, 'updated_at': 2.0}
        json_write(self.paths.state_file, self.paused)

    def metadata(self, *, old=None, new=None):
        self.settings(threads={self.thread: {'returned_id': self.thread, **(old or {})},
            self.target: {'returned_id': self.target, 'cwd': str(self.target_cwd), **(new or {})}})

    def transfer(self, **values):
        return handover(self.paths, thread_id=values.get('thread_id', self.target),
                        thread_cwd=values.get('thread_cwd', str(self.target_cwd)))

    def database(self, config=None):
        return Ledger(self.paths.state / 'automation.sqlite3', scope(config or self.config))

    def rows(self):
        with closing(sqlite3.connect(self.paths.state / 'automation.sqlite3')) as db, db:
            db.row_factory = sqlite3.Row
            tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'thread_handovers' ORDER BY name")]
            result = {}
            for table in tables:
                records = [dict(r) for r in db.execute('SELECT * FROM "' + table + '" ORDER BY rowid')]
                if table == 'meta':
                    for record in records:
                        record.pop('scope')
                result[table] = records
            return result

    def receipts(self):
        with closing(sqlite3.connect(self.paths.state / 'automation.sqlite3')) as db, db:
            return [json.loads(row[0]) for row in db.execute('SELECT receipt FROM thread_handovers ORDER BY rowid')]

    def files(self):
        root = self.paths.state / 'jobs'
        return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob('*') if path.is_file()}

    def assert_rejected(self, code, **values):
        old_config, old_rows = self.paths.config.read_bytes(), self.rows()
        old_state = self.paths.state_file.read_bytes()
        with self.assertRaises(ControlError) as caught:
            self.transfer(**values)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.paths.config.read_bytes(), old_config)
        self.assertEqual(self.rows(), old_rows)
        self.assertEqual(self.paths.state_file.read_bytes(), old_state)
        self.assertFalse((self.codex_home / 'calls.jsonl').exists())


class ThreadHandoverTests(HandoverCase):
    def test_ready_transfer_keeps_all_existing_rows_and_pause(self):
        before, paused = self.rows(), self.paths.state_file.read_bytes()
        reply = self.transfer()
        self.assertTrue(reply['handed_over'])
        self.assertFalse(reply['model_called'])
        self.assertFalse(reply['service_started'])
        self.assertEqual(self.rows(), before)
        self.assertEqual(self.paths.state_file.read_bytes(), paused)
        config = load(self.paths)
        self.assertEqual(config, replace(self.config, session_id=self.target, thread_cwd=self.target_cwd))
        history = self.database(config)
        history.close()
        receipts = self.receipts()
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]['from_thread_id'], self.thread)
        self.assertEqual(receipts[0]['to_thread_id'], self.target)
        self.assertFalse((self.paths.state / 'thread-handover-pending.json').exists())
        methods = {doc.get('method') for doc in self.codex_daemon.server.requests}
        self.assertLessEqual(methods, {'initialize', 'initialized', 'thread/read'})
        self.assertFalse((self.codex_home / 'calls.jsonl').exists())

    def test_waiting_result_keeps_attempt_and_reduced_budget_then_dispatches_followup(self):
        history = self.database()
        history.bind_contract(new_contract(1, allowed=False))
        history.close()
        first = FakeCodex(self)
        with Engine(self.config, self.paths, Gate(), core=FakeCore(), codex=first) as engine:
            engine.tick()
            output = engine.exchange.patches(self.seed)[0]
        before, files = self.rows(), self.files()
        self.assertEqual(before['jobs'][0]['stage'], 'waiting_result')
        self.assertEqual(self.transfer()['current_stage'], 'waiting_result')
        self.assertEqual(self.rows(), before)
        self.assertEqual(self.files(), files)
        following = self.result('following.zip', previous=self.seed, patch_sha=output['sha256'])
        config = load(self.paths)
        second = FakeCodex(self, 'no_work')
        with Engine(config, self.paths, Gate(), core=FakeCore(), codex=second) as engine:
            engine.tick()
        self.assertEqual(second.calls, 1)
        history = self.database(config)
        try:
            self.assertEqual(history.current()['sha'], following['sha256'])
            self.assertEqual(history.current()['stage'], 'no_work')
            self.assertEqual(history.request_contract(), new_contract(1, allowed=False))
        finally:
            history.close()
        attempt = json.loads((self.paths.state/'jobs'/following['sha256']/'attempt.json').read_text())
        self.assertEqual(attempt['thread_id'], self.target)
        for path, raw in files.items():
            self.assertEqual((self.paths.state/'jobs'/path).read_bytes(), raw)

    def test_no_work_and_repeated_identical_transfer_do_not_create_jobs(self):
        with Engine(self.config, self.paths, Gate(), core=FakeCore(), codex=FakeCodex(self, 'no_work')) as engine:
            engine.tick()
        before = self.rows()
        self.transfer()
        self.assertEqual(self.rows(), before)
        self.assertTrue(self.transfer()['already_configured'])
        self.assertEqual(len(self.receipts()), 1)
        self.assertEqual(self.rows(), before)

    def test_exact_dev_directory_is_also_supported(self):
        self.target_cwd = self.dev
        self.metadata()
        self.transfer()
        self.assertEqual(load(self.paths).thread_cwd, self.dev)

    def test_active_original_thread_is_rejected(self):
        self.metadata(old={'thread_status': 'active'})
        self.assert_rejected('dev_thread_busy')

    def test_active_new_thread_is_rejected(self):
        self.metadata(new={'thread_status': 'active'})
        self.assert_rejected('dev_thread_busy')

    def test_unknown_or_missing_target_is_rejected(self):
        self.metadata(new={'missing': True})
        self.assert_rejected('codex_request_rejected')

    def test_wrong_thread_identity_is_rejected(self):
        self.metadata(new={'returned_id': str(uuid4())})
        self.assert_rejected('wrong_thread')

    def test_unrelated_thread_cwd_is_rejected(self):
        self.metadata(new={'cwd': str(self.exchange)})
        self.assert_rejected('wrong_thread_repository')

    def test_relative_or_unrelated_requested_directory_is_rejected(self):
        for cwd in ('specroad-codex', str(self.exchange), str(self.dev.parent.parent)):
            with self.subTest(cwd=cwd):
                self.assert_rejected('invalid_handover_target', thread_cwd=cwd)

    def test_running_or_uncertain_work_is_not_reassigned(self):
        for stage in ('running', 'uncertain', 'retry_wait', 'overload_wait'):
            with self.subTest(stage=stage):
                with closing(sqlite3.connect(self.paths.state/'automation.sqlite3')) as db, db:
                    db.execute('UPDATE jobs SET stage=?', (stage,))
                self.assert_rejected('handover_job_unresolved')

    def test_ready_with_existing_attempt_directory_is_rejected(self):
        private_dir(self.paths.state/'jobs'/self.seed['sha256'])
        self.assert_rejected('handover_attempt_present')

    def test_held_worker_lock_is_rejected(self):
        with lock(self.paths.state/'worker.lock'):
            self.assert_rejected('already_running')

    def test_missing_native_source_is_not_replaced_with_latest_result(self):
        Path(self.seed['path']).unlink()
        self.result('newer.zip')
        self.assert_rejected('source_result_missing')

    def test_configure_still_cannot_change_existing_scope(self):
        before = self.rows()
        with self.assertRaises(ControlError) as caught:
            configure(self.paths, thread_id=self.target)
        self.assertEqual(caught.exception.code, 'ledger_scope_mismatch')
        self.assertEqual(self.rows(), before)

    def test_config_write_failure_requires_explicit_identical_completion(self):
        before, config = self.rows(), self.paths.config.read_bytes()
        def fail_config(path, data, **kw):
            if path == self.paths.config:
                raise OSError('injected crash after scope commit')
            return write_private(path, data, **kw)
        with patch('specroad_control.handover.write_private', side_effect=fail_config):
            with self.assertRaises(OSError):
                self.transfer()
        self.assertEqual(self.rows(), before)
        self.assertEqual(self.paths.config.read_bytes(), config)
        with self.assertRaises(ControlError) as caught:
            load(self.paths)
        self.assertEqual(caught.exception.code, 'handover_pending')
        self.assertTrue(self.transfer()['resumed_handover'])
        self.assertEqual(self.rows(), before)
        self.assertEqual(len(self.receipts()), 1)
        self.assertEqual(load(self.paths).session_id, self.target)

    def test_two_transfers_append_linked_receipts_without_reset(self):
        before = self.rows()
        self.transfer()
        self.thread = self.target
        self.target = str(uuid4())
        self.metadata(old={'cwd': str(self.target_cwd)})
        self.transfer()
        receipts = self.receipts()
        self.assertEqual(len(receipts), 2)
        canonical = json.dumps(receipts[0], sort_keys=True, separators=(',', ':')).encode()
        self.assertEqual(receipts[1]['previous_sha256'], sha256(canonical).hexdigest())
        self.assertEqual(receipts[1]['from_thread_id'], receipts[0]['to_thread_id'])
        self.assertEqual(self.rows(), before)
