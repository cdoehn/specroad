"""Explicit, evidence-only recovery of old terminal overloads, never blind replay."""
from dataclasses import replace
import contextlib
import io
import json
import time
from unittest.mock import patch
from specroad_control.automation import Engine,Gate
from specroad_control.codex import Codex
from specroad_control.commands import recover
from specroad_control.config import render
from specroad_control.errors import ControlError
from specroad_control.job_contract import prompt_for,scope,SCHEMA
from specroad_control.ledger import Ledger
from specroad_control.local import private_dir,json_read,json_write,write_private
from codex_control_tests.automation_support import AutomationCase,FakeCore,package
from codex_control_tests.retry_support import initialize_git


class LegacyRetryTests(AutomationCase):
    def setUp(self):
        super().setUp()
        initialize_git(self.dev)
        self.config=replace(self.config,transport='app-server-proxy')
        write_private(self.paths.config,render(self.config).encode())
        self.directory=self.paths.state/'jobs'/self.seed['sha256'];private_dir(self.directory)
        self.settings(overload=True)
        with self.assertRaises(ControlError):
            Codex(self.config).run(prompt_for(self.seed),SCHEMA,self.directory)
        # Only the independent fixture simulates the old receipt layout.
        (self.directory/'failure.json').unlink()
        with self.ledger() as ledger:
            ledger.change('running');ledger.change('uncertain',error='codex_turn_failed')
        self.config_bytes=self.paths.config.read_bytes()

    @contextlib.contextmanager
    def ledger(self):
        ledger=Ledger(self.paths.state/'automation.sqlite3',scope(self.config))
        try:yield ledger
        finally:ledger.close()

    def assert_blocked(self):
        with self.assertRaises(ControlError):recover(self.paths)
        with self.ledger() as ledger:self.assertEqual(ledger.current()['stage'],'uncertain')
        self.assertEqual(len((self.codex_home/'calls.jsonl').read_text().splitlines()),1)

    def test_valid_legacy_proof_schedules_but_never_dispatches_or_changes_config(self):
        before=time.time();result=recover(self.paths)
        self.assertTrue(result['recovered']);self.assertEqual(result['stage'],'retry_wait')
        self.assertGreaterEqual(result['retry_at'],before+60)
        self.assertFalse(result['model_called']);self.assertFalse(result['service_started'])
        self.assertEqual(self.paths.config.read_bytes(),self.config_bytes)
        self.assertFalse((self.directory/'failure.json').exists())
        with self.ledger() as ledger:
            self.assertTrue(ledger.retry_info(self.seed['sha256'])['evidence']['legacy'])
        self.assertEqual(len((self.codex_home/'calls.jsonl').read_text().splitlines()),1)

    def test_repeated_recover_preserves_deadline_budget_and_original_evidence(self):
        raw=(self.directory/'events.jsonl').read_bytes()
        first=recover(self.paths);second=recover(self.paths)
        self.assertFalse(second['recovered'])
        with self.ledger() as ledger:
            retry=ledger.retry_info(self.seed['sha256']);self.assertEqual(retry['number'],1)
            self.assertEqual(retry['due'],first['retry_at'])
        self.assertEqual((self.directory/'events.jsonl').read_bytes(),raw)

    def test_recovery_proof_allows_exactly_one_later_normal_attempt(self):
        result=recover(self.paths);self.settings(mode='no_work')
        with Engine(self.config,self.paths,Gate(),core=FakeCore(),clock=lambda:result['retry_at']) as engine:
            self.assertTrue(engine.tick()['halted'])
        with self.ledger() as ledger:self.assertEqual(ledger.current()['stage'],'no_work')
        self.assertEqual(len((self.codex_home/'calls.jsonl').read_text().splitlines()),2)
        self.assertTrue((self.directory/'attempts/0001/protocol-completion.json').exists())

    def test_new_user_change_after_legacy_recovery_blocks_dispatch(self):
        result=recover(self.paths);(self.dev/'fixture.txt').write_text('new user work')
        with Engine(self.config,self.paths,Gate(),core=FakeCore(),clock=lambda:result['retry_at']) as engine:
            self.assertTrue(engine.tick()['halted'])
        self.assertEqual(len((self.codex_home/'calls.jsonl').read_text().splitlines()),1)

    def test_live_active_thread_is_not_stopped_by_recover(self):
        self.settings(thread_status='active');self.assert_blocked()

    def test_unknown_tools_in_live_full_history_veto_legacy_replay(self):
        self.codex_daemon.server.history['test-turn']['items'].append({'id':'mcp','type':'mcpToolCall'})
        self.assert_blocked()

    def test_truncated_legacy_log_is_not_a_terminal_proof(self):
        p=self.directory/'events.jsonl';p.write_bytes(p.read_bytes()[:-4]);self.assert_blocked()

    def test_foreign_turn_id_in_receipt_cannot_borrow_failure(self):
        json_write(self.directory/'turn.json',{'thread_id':self.thread,'turn_id':'foreign'})
        self.assert_blocked()

    def test_duplicate_terminal_in_legacy_log_is_ambiguous(self):
        p=self.directory/'events.jsonl';lines=p.read_bytes().splitlines(keepends=True)
        terminal=next(l for l in lines if b'turn/completed' in l)
        p.write_bytes(p.read_bytes()+terminal);self.assert_blocked()

    def test_missing_started_record_is_not_guessed(self):
        p=self.directory/'events.jsonl';p.write_bytes(b''.join(l for l in p.read_bytes().splitlines(keepends=True) if b'turn/started' not in l))
        self.assert_blocked()

    def test_legacy_internal_retry_true_is_not_replaced(self):
        p=self.directory/'events.jsonl';p.write_bytes(p.read_bytes().replace(b'"willRetry": false',b'"willRetry": true'))
        self.assert_blocked()

    def test_changed_result_does_not_allow_recovery(self):
        p=self.exchange/'seed.zip';p.write_bytes(b'broken')
        self.assert_blocked()

    def test_successful_output_is_adopted_before_any_retry(self):
        package(self.exchange/'ready.zip',{'kind':'patch','binding':self.binding})
        result=recover(self.paths);self.assertEqual(result['stage'],'waiting_result')
        with self.ledger() as ledger:self.assertIsNone(ledger.retry_info(self.seed['sha256']))

    def test_multiple_outputs_remain_ambiguous(self):
        package(self.exchange/'one.zip',{'kind':'patch','binding':self.binding,'different':1})
        package(self.exchange/'two.zip',{'kind':'patch','binding':self.binding,'different':2})
        self.assert_blocked()

    def test_logs_separate_structured_error_decision_from_return_value(self):
        out,err=io.StringIO(),io.StringIO()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            result=recover(self.paths)
        self.assertEqual(out.getvalue(),'')
        logged=[json.loads(l) for l in err.getvalue().splitlines()]
        decision=next(e for e in logged if e.get('decision')=='scheduled')
        self.assertEqual(decision['codex_error'],'serverOverloaded')
        self.assertEqual(decision['retry_at'],result['retry_at'])
