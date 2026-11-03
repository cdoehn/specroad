"""Interruption, metadata, receipt and lock boundaries of explicit handover."""
from contextlib import closing, contextmanager, redirect_stdout, redirect_stderr
from dataclasses import replace
from hashlib import sha256
import io
import json
from pathlib import Path
import sqlite3
from specroad_control.toml_compat import tomllib
from unittest.mock import patch
from uuid import uuid4

from specroad_control.automation import Engine, Gate
from specroad_control.cli import main
from specroad_control.codex import Codex
from specroad_control.codex_proxy import Proxy
from specroad_control.commands import configure, check, probe, recover, offline
from specroad_control.config import load, render, initialize
from specroad_control.daemon import run
from specroad_control.errors import ControlError
from specroad_control.local import json_write, lock, private_dir, write_private
from specroad_control.service import start
from codex_control_tests.automation_support import FakeCore
from codex_control_tests.test_thread_handover import HandoverCase


class ThreadHandoverGuardTests(HandoverCase):
    def pending(self, *, after_scope=False):
        if after_scope:
            def stop(path, data, **kw):
                if path == self.paths.config:
                    raise OSError('simulated crash after scope')
                return write_private(path, data, **kw)
            guard = patch('specroad_control.handover.write_private', side_effect=stop)
        else:
            guard = patch('specroad_control.handover.commit_history', side_effect=OSError('simulated crash before scope'))
        with guard, self.assertRaises(OSError):
            self.transfer()
        return self.paths.state/'thread-handover-pending.json'

    def test_intent_only_interruption_can_finish_identical_transfer(self):
        before, config = self.rows(), self.paths.config.read_bytes()
        self.pending()
        self.assertEqual(self.rows(), before)
        self.assertEqual(self.paths.config.read_bytes(), config)
        history = self.database()
        history.close()
        self.assertTrue(self.transfer()['resumed_handover'])
        self.assertEqual(self.rows(), before)
        self.assertEqual(len(self.receipts()), 1)

    def test_interruption_after_config_write_keeps_one_receipt(self):
        original = Path.unlink
        def stop(path, *args, **kw):
            if path.name == 'thread-handover-pending.json':
                raise OSError('simulated crash before journal removal')
            return original(path, *args, **kw)
        before = self.rows()
        with patch.object(Path, 'unlink', stop), self.assertRaises(OSError):
            self.transfer()
        self.assertEqual(tomllib.loads(self.paths.config.read_text())['develop']['session_id'], self.target)
        self.assertTrue(self.transfer()['resumed_handover'])
        self.assertEqual(len(self.receipts()), 1)
        self.assertEqual(self.rows(), before)

    def test_failed_sqlite_transaction_preserves_scope_and_receipt_absence(self):
        with closing(sqlite3.connect(self.paths.state/'automation.sqlite3')) as db, db:
            db.execute("CREATE TRIGGER refuse_scope BEFORE UPDATE OF scope ON meta BEGIN SELECT RAISE(ABORT,'injected'); END")
        before = self.paths.config.read_bytes()
        with self.assertRaises(ControlError) as caught:
            self.transfer()
        self.assertEqual(caught.exception.code, 'invalid_handover_history')
        self.assertEqual(self.paths.config.read_bytes(), before)
        history = self.database()
        try:
            self.assertFalse(history.db.execute("SELECT 1 FROM sqlite_master WHERE name='thread_handovers'").fetchone())
        finally:
            history.close()
        self.assertTrue((self.paths.state/'thread-handover-pending.json').exists())

    def test_pending_handover_blocks_all_ordinary_mutating_or_dispatch_operations(self):
        self.pending()
        calls = [('configure', lambda: configure(self.paths, thread_id=self.thread)),
                 ('start', lambda: start(self.paths)), ('check', lambda: check(self.paths)),
                 ('probe', lambda: probe(self.paths)), ('recover', lambda: recover(self.paths))]
        for label, call in calls:
            with self.subTest(call=label), self.assertRaises(ControlError) as caught:
                call()
            self.assertEqual(caught.exception.code, 'handover_pending')
        self.assertFalse((self.codex_home/'calls.jsonl').exists())

    def test_pending_handover_keeps_readonly_status_available(self):
        self.pending()
        output = io.StringIO()
        with patch('specroad_control.cli.service.inspect', return_value={'active': False}), redirect_stdout(output):
            code = main(['status'])
        reply = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertTrue(reply['ok'])
        self.assertFalse(reply['worker_reachable'])
        self.assertEqual(reply['last_state'], self.paused)

    def test_pending_handover_never_recreates_missing_configuration(self):
        self.pending()
        self.paths.config.unlink()
        with self.assertRaises(ControlError) as caught:
            initialize(self.paths)
        self.assertEqual(caught.exception.code, 'handover_pending')
        self.assertFalse(self.paths.config.exists())

    def test_offline_operations_read_configuration_after_handover_lock(self):
        journal = self.paths.state/'thread-handover-pending.json'
        @contextmanager
        def begin(paths):
            with offline(paths):
                json_write(journal, {'test': 'handover completed lock acquisition first'})
                yield
        for action in (check, probe, recover):
            with self.subTest(action=action.__name__):
                with patch('specroad_control.commands.offline', begin), self.assertRaises(ControlError) as caught:
                    action(self.paths)
                self.assertEqual(caught.exception.code, 'handover_pending')
                journal.unlink()
        self.assertFalse((self.codex_home/'calls.jsonl').exists())

    def test_worker_reads_configuration_after_worker_lock(self):
        journal = self.paths.state/'thread-handover-pending.json'
        @contextmanager
        def begin(path):
            with lock(path) as descriptor:
                if path.name == 'worker.lock':
                    json_write(journal, {'test': 'interrupted handover before worker lock'})
                yield descriptor
        state = self.paths.state_file.read_bytes()
        with patch('specroad_control.daemon.lock', begin), patch('specroad_control.daemon._locked_run') as entered:
            with self.assertRaises(ControlError) as caught:
                run(self.paths)
            self.assertEqual(caught.exception.code, 'handover_pending')
            entered.assert_not_called()
        self.assertEqual(self.paths.state_file.read_bytes(), state)

    def test_pending_different_target_is_not_a_new_handover(self):
        journal = self.pending()
        raw = journal.read_bytes()
        self.assert_rejected('invalid_handover_intent', thread_id=str(uuid4()))
        self.assertEqual(journal.read_bytes(), raw)

    def test_malformed_receipt_fields_do_not_override_pending_intent(self):
        journal = self.pending()
        original = json.loads(journal.read_text())
        for field, value in (('history_sha256', 'bad'), ('created_at', True), ('id', 'bad'),
                             ('previous_sha256', 123), ('extra', 'unexpected')):
            with self.subTest(field=field):
                doc = {**original, 'receipt': {**original['receipt'], field: value}}
                json_write(journal, doc)
                self.assert_rejected('invalid_handover_intent')

    def test_changed_config_while_pending_is_preserved_and_rejected(self):
        self.pending()
        write_private(self.paths.config, self.paths.config.read_bytes()+b'\n# changed externally\n')
        self.assert_rejected('handover_conflict')

    def test_changed_pause_while_pending_is_preserved_and_rejected(self):
        self.pending()
        json_write(self.paths.state_file, {**self.paused, 'desired': 'running'})
        self.assert_rejected('handover_conflict')

    def test_changed_old_job_cell_while_pending_is_rejected(self):
        self.pending()
        with closing(sqlite3.connect(self.paths.state/'automation.sqlite3')) as db, db:
            db.execute('UPDATE jobs SET updated=updated+1')
        self.assert_rejected('handover_conflict')

    def test_missing_source_on_explicit_completion_keeps_intent(self):
        journal = self.pending(after_scope=True)
        Path(self.seed['path']).unlink()
        self.assert_rejected('source_result_missing')
        self.assertTrue(journal.exists())

    def test_active_target_on_explicit_completion_keeps_intent(self):
        self.pending(after_scope=True)
        self.metadata(new={'thread_status': 'active'})
        self.assert_rejected('dev_thread_busy')

    def test_changed_scope_during_config_publication_keeps_journal(self):
        def interfere(path, data, **kw):
            write_private(path, data, **kw)
            if path == self.paths.config:
                with closing(sqlite3.connect(self.paths.state/'automation.sqlite3')) as db, db:
                    db.execute("UPDATE meta SET scope=?", ('0'*64,))
        with patch('specroad_control.handover.write_private', side_effect=interfere):
            with self.assertRaises(ControlError) as caught:
                self.transfer()
        self.assertEqual(caught.exception.code, 'invalid_handover_history')
        self.assertTrue((self.paths.state/'thread-handover-pending.json').exists())

    def test_changed_receipt_during_config_publication_keeps_journal(self):
        def interfere(path, data, **kw):
            write_private(path, data, **kw)
            if path == self.paths.config:
                with closing(sqlite3.connect(self.paths.state/'automation.sqlite3')) as db, db:
                    row = json.loads(db.execute('SELECT receipt FROM thread_handovers').fetchone()[0])
                    row['created_at'] += 1
                    db.execute('UPDATE thread_handovers SET receipt=?', (json.dumps(row, sort_keys=True, separators=(',', ':')),))
        with patch('specroad_control.handover.write_private', side_effect=interfere):
            with self.assertRaises(ControlError) as caught:
                self.transfer()
        self.assertEqual(caught.exception.code, 'handover_conflict')
        self.assertTrue((self.paths.state/'thread-handover-pending.json').exists())

    def test_second_precommit_metadata_read_detects_new_activity(self):
        original = Proxy.thread
        reads = 0
        def observe(proxy):
            nonlocal reads
            if proxy.config.session_id == self.target:
                reads += 1
                if reads == 2:
                    self.metadata(new={'thread_status': 'active'})
            return original(proxy)
        with patch.object(Proxy, 'thread', observe):
            self.assert_rejected('dev_thread_busy')
        self.assertEqual(reads, 2)
        self.assertTrue((self.paths.state/'thread-handover-pending.json').exists())

    def test_corrupt_completed_receipt_blocks_normal_ledger_open(self):
        self.transfer()
        config = load(self.paths)
        with closing(sqlite3.connect(self.paths.state/'automation.sqlite3')) as db, db:
            db.execute("UPDATE thread_handovers SET receipt='{}'")
        with self.assertRaises(ControlError) as caught:
            self.database(config)
        self.assertEqual(caught.exception.code, 'invalid_handover_history')

    def test_missing_completed_receipt_blocks_normal_ledger_open(self):
        self.transfer()
        config = load(self.paths)
        with closing(sqlite3.connect(self.paths.state/'automation.sqlite3')) as db, db:
            db.execute('DELETE FROM thread_handovers')
        with self.assertRaises(ControlError) as caught:
            self.database(config)
        self.assertEqual(caught.exception.code, 'invalid_handover_history')

    def test_broken_receipt_chain_blocks_another_transfer(self):
        self.transfer()
        self.thread, self.target = self.target, str(uuid4())
        self.metadata(old={'cwd': str(self.target_cwd)})
        self.transfer()
        self.thread, self.target = self.target, str(uuid4())
        self.metadata(old={'cwd': str(self.target_cwd)})
        with closing(sqlite3.connect(self.paths.state/'automation.sqlite3')) as db, db:
            record_id, raw = db.execute('SELECT id,receipt FROM thread_handovers ORDER BY rowid LIMIT 1').fetchone()
            receipt = json.loads(raw)
            receipt['created_at'] += 1
            db.execute('UPDATE thread_handovers SET receipt=? WHERE id=?',
                       (json.dumps(receipt, sort_keys=True, separators=(',', ':')), record_id))
        self.assert_rejected('invalid_handover_history')

    def test_active_persisted_worker_state_is_not_cleared(self):
        json_write(self.paths.state_file, {**self.paused, 'phase': 'working', 'active_job': True})
        self.assert_rejected('handover_worker_unproven')

    def test_missing_state_file_is_preserved(self):
        self.paths.state_file.unlink()
        self.transfer()
        self.assertFalse(self.paths.state_file.exists())

    def test_requested_parent_must_match_exact_observed_cwd_during_transfer(self):
        self.metadata(new={'cwd': str(self.dev)})
        self.assert_rejected('handover_cwd_mismatch')

    def test_runtime_can_observe_dev_after_explicit_parent_transfer(self):
        self.transfer()
        self.settings(thread=self.target, cwd=str(self.dev))
        self.assertTrue(Codex(load(self.paths)).check()['thread_resolved'])

    def test_undeclared_parent_is_not_accepted_by_legacy_config(self):
        self.metadata(old={'cwd': str(self.dev.parent)})
        self.assert_rejected('wrong_thread_repository')

    def test_symlink_requested_cwd_is_rejected_without_following_it(self):
        link = self.home/'parent-link'
        link.symlink_to(self.dev.parent, target_is_directory=True)
        self.assert_rejected('invalid_handover_target', thread_cwd=str(link))

    def test_symlink_metadata_in_configuration_is_rejected(self):
        link = self.home/'parent-link'
        link.symlink_to(self.dev.parent, target_is_directory=True)
        write_private(self.paths.config, render(replace(self.config, thread_cwd=link)).encode())
        with self.assertRaises(ControlError) as caught:
            load(self.paths)
        self.assertEqual(caught.exception.code, 'invalid_config')

    def test_target_thread_lock_is_shared_across_controllers(self):
        root = self.paths.target_locks
        private_dir(root)
        key = sha256((str(self.codex_home.resolve())+self.target).encode()).hexdigest()
        with lock(root/('thread-'+key+'.lock')):
            self.assert_rejected('already_running')

    def test_broken_pending_symlink_blocks_ordinary_load(self):
        journal = self.paths.state/'thread-handover-pending.json'
        journal.symlink_to(self.home/'absent')
        with self.assertRaises(ControlError) as caught:
            load(self.paths)
        self.assertEqual(caught.exception.code, 'handover_pending')
        self.assert_rejected('unsafe_path')

    def test_proxy_dispatch_retains_declared_workspace_and_write_roots(self):
        write_private(self.paths.config, render(replace(self.config, transport='app-server-proxy')).encode())
        self.transfer()
        self.settings(thread=self.target, cwd=str(self.target_cwd))
        config = load(self.paths)
        with Engine(config, self.paths, Gate(), core=FakeCore()) as engine:
            engine.tick()
        request = json.loads((self.codex_home/'request.json').read_text())
        self.assertEqual(request['cwd'], str(self.target_cwd))
        self.assertEqual(request['sandboxPolicy']['writableRoots'], [str(self.target_cwd), str(self.exchange)])
        self.assertFalse(request['sandboxPolicy']['networkAccess'])
        self.assertEqual(request['approvalPolicy'], 'never')
        self.assertEqual(request['threadId'], self.target)

    def test_exec_dispatch_explicitly_pins_declared_working_root(self):
        self.transfer()
        self.settings(thread=self.target, cwd=str(self.target_cwd))
        config = load(self.paths)
        with Engine(config, self.paths, Gate(), core=FakeCore()) as engine:
            engine.tick()
        calls = [json.loads(line) for line in (self.codex_home/'calls.jsonl').read_text().splitlines()]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][:4], ['exec', '--cd', str(self.target_cwd), 'resume'])
        self.assertEqual((self.codex_home/'process-cwd').read_text(), str(self.target_cwd))
        self.assertIn('sandbox_workspace_write.writable_roots='+json.dumps([str(self.target_cwd),str(self.exchange)]), calls[0])
        self.assertEqual(calls[0][-2], self.target)

    def test_cli_requires_explicit_id_and_cwd_and_rejects_seed_options(self):
        for argv in (['handover'], ['handover', '--thread-id', self.target],
                     ['handover', '--thread-id', self.target, '--thread-cwd', str(self.target_cwd), '--result', self.seed['path']],
                     ['configure', '--thread-id', self.thread, '--thread-cwd', str(self.target_cwd)]):
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                main(argv)
            self.assertEqual(caught.exception.code, 2)

    def test_cli_returns_machine_readable_completed_handover(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(['handover', '--thread-id', self.target, '--thread-cwd', str(self.target_cwd)])
        result = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertTrue(result['ok'])
        self.assertTrue(result['history_preserved'])
        self.assertFalse(result['model_called'])
