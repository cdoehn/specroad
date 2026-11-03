"""Confirmed failure is retryable; time without a terminal event is not failure."""
from dataclasses import replace
import contextlib
import io
import json
from unittest.mock import patch
from specroad_control.automation import Engine, Gate
from specroad_control.errors import ControlError
from specroad_control.job_contract import prompt_for, scope
from specroad_control.ledger import Ledger
from specroad_control.local import json_write, json_read, private_dir
from specroad_control.retry_ledger import attempt_directory
from specroad_control.turn_failure import safe_command, proof
from specroad_control.telemetry import record
from codex_control_tests.automation_support import AutomationCase, FakeCore, package
from codex_control_tests.retry_support import initialize_git


class OverloadCodex:
    """Independent protocol facts; no Codex or model is started by these tests."""
    def __init__(self, case):
        self.case = case
        self.calls = 0
        self.failures = 1
        self.error = 'serverOverloaded'
        self.will_retry = False
        self.status = 'idle'
        self.effect = None
        self.turns = {}
        self.inspect_calls = 0

    def check(self):
        return {'model_called': False, 'thread_resolved': True}

    def inspect_turn(self, turn_id):
        self.inspect_calls += 1
        return {'thread_status': self.status, 'turn': self.turns.get(turn_id)}

    def run(self, prompt, schema, directory, *, readonly=False, authorize=lambda:True):
        if not authorize():
            raise ControlError('dispatch_paused', 'paused')
        self.calls += 1
        source = json.loads(prompt.splitlines()[1])
        turn_id = f'turn-{self.calls}'
        items = [{'id':'u', 'type':'userMessage', 'content':[{'type':'text','text':prompt}]},
                 {'id':'r', 'type':'reasoning'},
                 {'id':'p', 'type':'commandExecution','command':'/bin/bash -lc \'pwd && git rev-parse --show-toplevel\'',
                  'status':'completed','exitCode':0}]
        if self.effect:
            items.append(self.effect)
        turn = {'id':turn_id,'status':'failed','items':items,'error':{'codexErrorInfo': self.error}}
        self.turns[turn_id] = turn
        if self.calls <= self.failures:
            details = {'turn_status':'failed','codex_error':self.error,'codex_will_retry':self.will_retry}
            json_write(directory/'turn.json', {'thread_id':self.case.thread,'turn_id':turn_id})
            json_write(directory/'failure.json', {'thread_id':self.case.thread,'turn_id':turn_id,**details})
            raise ControlError('codex_turn_failed','failed',details=details)
        return {'source_result_sha256':source['sha256'],'status':'no_work','patch_sha256':'','message':''}


class RetryCase(AutomationCase):
    def setUp(self):
        super().setUp()
        initialize_git(self.dev)
        self.config = replace(self.config, transport='app-server-proxy')
        self.now = 1000.0
        self.codex = OverloadCodex(self)
        self.engine = Engine(self.config,self.paths,Gate(),core=FakeCore(),codex=self.codex,clock=lambda:self.now)
        self.addCleanup(self.engine.close)

    def ledger(self):
        ledger = Ledger(self.paths.state/'automation.sqlite3',scope(self.config))
        self.addCleanup(ledger.close)
        return ledger

class OverloadRetryTests(RetryCase):
    def test_terminal_overload_schedules_wait_without_immediate_model_replay(self):
        result = self.engine.tick()
        self.assertEqual(result['retry_after'],60)
        self.assertFalse(result['halted'])
        self.assertEqual(self.codex.calls,1)
        self.assertEqual(self.ledger().current()['stage'],'retry_wait')
        self.assertEqual(self.engine.summary()['codex_error'],'serverOverloaded')

    def test_retry_due_time_not_outputs_controls_replacement(self):
        self.engine.tick()
        self.now += 59
        self.assertEqual(self.engine.tick()['retry_after'],1)
        self.assertEqual(self.codex.calls,1)
        self.now += 1
        self.assertTrue(self.engine.tick()['halted'])
        self.assertEqual(self.codex.calls,2)
        self.assertEqual(self.ledger().current()['stage'],'no_work')

    def test_attempt_evidence_is_not_overwritten(self):
        self.engine.tick()
        first = self.paths.state/'jobs'/self.seed['sha256']/'failure.json'
        before = first.read_bytes()
        self.now += 60; self.engine.tick()
        self.assertEqual(first.read_bytes(),before)
        self.assertTrue((first.parent/'attempts/0001/completion.json').is_file())

    def test_active_thread_after_hours_prevents_a_new_call(self):
        self.engine.tick(); self.now += 7200; self.codex.status='active'
        for _ in range(3):
            self.assertEqual(self.engine.tick()['retry_after'],30)
            self.now += 3600
        self.assertEqual(self.codex.calls,1)
        self.assertEqual(self.ledger().current()['stage'],'retry_wait')

    def test_unknown_live_status_is_blocked_not_retried(self):
        self.engine.tick(); self.now += 60; self.codex.status='systemError'
        self.assertTrue(self.engine.tick()['halted']); self.assertEqual(self.codex.calls,1)

    def test_budget_remains_bounded_per_source(self):
        self.codex.failures=20
        for delay in (60,180,600,1800):
            self.assertEqual(self.engine.tick()['retry_after'],delay)
            self.now += delay
        self.assertTrue(self.engine.tick()['halted'])
        self.assertEqual(self.codex.calls,5)
        self.assertEqual(self.ledger().current()['stage'],'uncertain')

    def test_restart_preserves_due_and_attempt_number(self):
        self.engine.tick(); self.engine.close()
        with Engine(self.config,self.paths,Gate(),core=FakeCore(),codex=self.codex,clock=lambda:self.now) as engine:
            self.assertEqual(engine.tick()['retry_after'],60)
            self.assertEqual(self.codex.calls,1)
            self.now+=60; engine.tick()
        self.assertEqual(self.codex.calls,2)

    def test_internal_codex_retry_is_not_overlapped(self):
        self.codex.will_retry=True
        self.assertTrue(self.engine.tick()['halted'])
        self.assertEqual(self.codex.calls,1)

    def test_other_error_is_not_treated_as_capacity(self):
        self.codex.error='usageLimitExceeded'
        self.assertTrue(self.engine.tick()['halted'])
        self.assertEqual(self.codex.calls,1)

    def test_mutating_or_unknown_tool_prevents_retry(self):
        self.codex.effect={'id':'write','type':'fileChange','status':'completed'}
        self.assertTrue(self.engine.tick()['halted']); self.assertEqual(self.codex.calls,1)

    def test_bound_patch_appearing_during_backoff_is_adopted(self):
        self.engine.tick()
        package(self.exchange/'output.zip',{'kind':'patch','binding':self.binding})
        self.engine.tick()
        self.assertEqual(self.codex.calls,1)
        self.assertEqual(self.ledger().current()['stage'],'waiting_result')

    def test_pause_at_due_time_preserves_scheduled_job(self):
        self.engine.tick(); self.now+=60; self.engine.gate.set(False)
        self.engine.tick(); self.assertEqual(self.codex.calls,1)
        self.assertEqual(self.ledger().current()['stage'],'retry_wait')
        self.engine.gate.set(True);self.engine.tick();self.assertEqual(self.codex.calls,2)

    def test_original_failure_without_new_receipt_remains_uncertain(self):
        ledger=self.ledger();ledger.change('running');ledger.change('uncertain',error='codex_turn_failed')
        self.assertTrue(self.engine.tick()['halted']);self.assertEqual(self.codex.calls,0)

    def test_foreign_turn_does_not_prove_failure(self):
        self.engine.tick();self.now+=60
        self.codex.turns['turn-1']['id']='wrong'
        self.assertTrue(self.engine.tick()['halted']);self.assertEqual(self.codex.calls,1)

    def test_wrong_source_in_turn_cannot_be_replayed(self):
        self.engine.tick();self.now+=60
        self.codex.turns['turn-1']['items'][0]['content'][0]['text']='unrelated request'
        self.assertTrue(self.engine.tick()['halted']);self.assertEqual(self.codex.calls,1)

    def test_no_missing_durable_claim_is_reconstructed_from_time(self):
        ledger=self.ledger();ledger.change('running')
        self.now+=86400
        self.assertTrue(self.engine.tick()['halted']);self.assertEqual(self.codex.calls,0)

    def test_journal_records_cause_and_retry_decision_but_not_server_secrets(self):
        output=io.StringIO()
        with contextlib.redirect_stderr(output): self.engine.tick()
        entries=[json.loads(line) for line in output.getvalue().splitlines()]
        errors=[e for e in entries if e['event']=='automation_error']
        decisions=[e for e in entries if e.get('decision')=='scheduled']
        self.assertEqual(errors[0]['codex_error'],'serverOverloaded')
        self.assertFalse(errors[0]['codex_will_retry'])
        self.assertEqual(decisions[0]['retry_at'],1060)
        self.assertEqual(decisions[0]['source_sha256'],self.seed['sha256'])
        with contextlib.redirect_stderr(output):
            doc=record('automation_error',codex_error='other',prompt='SECRET',message='SECRET',error='bad\nline')
        self.assertNotIn('SECRET',json.dumps(doc));self.assertEqual(doc['error'],'bad_line')

    def test_allowlist_does_not_confuse_shell_substrings_with_readonly_work(self):
        for command in ['pwd; touch x','echo pwd','$(pwd)','pwd > x','pwd &','git status','bash -lc "pwd; true"']:
            self.assertFalse(safe_command(command),command)
        self.assertTrue(safe_command('/bin/bash -lc "pwd && git rev-parse --show-toplevel"'))
