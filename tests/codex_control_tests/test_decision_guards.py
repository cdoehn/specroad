"""Evidence compatibility, interrupted publication and dispatch boundary tests."""
import hashlib
import json
import sqlite3
from unittest.mock import patch
from specroad_control import commands
from specroad_control.errors import ControlError
from specroad_control.job_contract import contract, continuation_prompt, prompt_for
from specroad_control.local import json_read, json_write, private_dir
from specroad_control.retry_ledger import attempt_directory
from specroad_control.workspace import fingerprint
from codex_control_tests.automation_support import FakeCore, package
from codex_control_tests.decision_support import DecisionCase
from codex_control_tests.test_overload_retry import RetryCase
from codex_control_tests.test_continuation import PartialCodex


class DecisionGuards(DecisionCase):
    def test_legacy_prompt_bytes_match_pre_upgrade_dispatches(self):
        source = {'path':'/reference/result.zip','sha256':'1'*64,
                  'binding':{'repo_id':'00000000-0000-4000-8000-000000000001',
                             'base_commit':'2'*40,'state_fingerprint':'3'*16,
                             'fingerprint_algorithm':'patchharbor-state-v1'},
                  'run_id':'00000000-0000-4000-8000-000000000002'}
        source = json.loads(json.dumps(source, sort_keys=True))
        evidence = {'turn_id':'original-turn','workspace_sha256':'4'*64,'history_sha256':'5'*64}
        # Hashes are protocol identities captured from the previous delivered code,
        # not expectations about editorial wording or presentation.
        self.assertEqual(hashlib.sha256(prompt_for(source).encode()).hexdigest(),
                         '554b2015388ce0921593856977a3101bbebed06f0c98971061aa8049946526a2')
        self.assertEqual(hashlib.sha256(continuation_prompt(source, evidence).encode()).hexdigest(),
                         'b2f7b83670d620c16af723b92ff34ba4aa734139c8c7525301d94510021e1b41')

    def test_attempt_change_at_final_dispatch_prevents_model(self):
        original = self.engine.exchange.assert_current
        count = 0
        def inspect(*args):
            nonlocal count
            original(*args); count += 1
            if count == 2:
                directory = attempt_directory(self.paths, self.seed['sha256'], 0)
                document = json_read(directory/'attempt.json')
                document['request_contract']['clarification_allowed'] = False
                json_write(directory/'attempt.json', document)
        self.engine.exchange.assert_current = inspect
        self.assertTrue(self.engine.tick()['halted'])
        self.assertEqual(self.codex.calls, 0)
        self.assertEqual(self.ledger().current()['stage'], 'ready')
        self.assertEqual(self.ledger().current()['error'], 'request_contract_changed')

    def test_clarification_output_cannot_be_reclassified_to_reopen_budget(self):
        self.engine.tick(); ledger = self.ledger(); before = ledger.current()
        with self.assertRaises(ControlError):
            ledger.change('waiting_result', patch_sha=before['patch_sha'], output_kind='patch_ready')
        self.assertEqual(ledger.current(), before)
        self.follow(); self.engine.gate.set(False); self.engine.tick()
        self.assertFalse(self.ledger().request_contract()['clarification_allowed'])

    def test_package_cannot_change_after_classification(self):
        self.engine.tick(); ledger = self.ledger(); before = ledger.current()
        with self.assertRaises(ControlError):
            ledger.change('waiting_result', patch_sha='f'*64)
        self.assertEqual(ledger.current(), before)

    def test_handoff_rollback_keeps_both_budget_and_job(self):
        ledger = self.ledger()
        ledger.bind_contract({'version':2,'clarification_allowed':False})
        ledger.change('running'); before = ledger.current()
        with self.assertRaises(ControlError):
            ledger.change('waiting_result', patch_sha='f'*64, output_kind='spec_clarification')
        self.assertEqual(ledger.current(), before)
        self.assertIsNone(ledger.db.execute('SELECT output_kind FROM request_contracts').fetchone()[0])

    def test_followup_budget_and_claim_roll_back_together(self):
        self.engine.tick(); source = self.follow(); ledger = self.ledger(); before = ledger.current()
        with patch.object(ledger, '_insert_contract', side_effect=sqlite3.OperationalError('disk fixture')):
            with self.assertRaises(sqlite3.Error):
                ledger.enqueue(source)
        self.assertEqual(ledger.current(), before)
        self.assertNotIn(source['run_id'], ledger.known_runs())

    def test_unknown_adopted_output_does_not_reopen_budget(self):
        self.engine.tick(); self.follow(); self.engine.gate.set(False); self.engine.tick()
        row = self.ledger().current()
        package(self.exchange/'manual.zip', {'kind':'patch','binding':row['source']['binding']})
        self.engine.tick()
        self.follow('third.zip', binding={**self.binding,'base_commit':'d'*40})
        self.engine.tick()
        self.assertFalse(self.ledger().request_contract()['clarification_allowed'])
        self.assertEqual(self.codex.calls, 1)

    def test_failed_normal_apply_does_not_reopen_budget(self):
        self.engine.tick(); self.follow(); self.codex.kind='patch_ready'; self.engine.tick()
        self.follow('third.zip', binding={**self.binding,'base_commit':'d'*40}, success=False, primary_kind='entrypoint_failed')
        self.engine.gate.set(False); self.engine.tick()
        self.assertFalse(self.ledger().request_contract()['clarification_allowed'])

    def test_missing_completion_commit_does_not_reopen_budget(self):
        self.engine.tick(); self.follow(); self.codex.kind='patch_ready'; self.engine.tick()
        self.follow('third.zip', binding={**self.binding,'base_commit':'d'*40}, completed_commit=None)
        self.engine.gate.set(False); self.engine.tick()
        self.assertFalse(self.ledger().request_contract()['clarification_allowed'])

    def test_damaged_history_is_not_interpreted_as_permission(self):
        ledger=self.ledger(); ledger.bind_contract({'version':2,'clarification_allowed':False})
        for allowed in (2, -1, 'yes'):
            ledger.db.execute('UPDATE request_contracts SET allowed=?', (allowed,))
            with self.assertRaises(ControlError) as caught:
                ledger.request_contract()
            self.assertEqual(caught.exception.code, 'request_contract_invalid')

    def test_offline_recovery_accepts_clarification_without_model_or_service(self):
        self.engine.tick(); ledger = self.ledger(); row = ledger.current()
        directory=attempt_directory(self.paths, self.seed['sha256'], 0)
        answer=json_read(directory/'completion.json')
        # A crash after protocol completion, before accepting the handoff.
        ledger.db.execute("UPDATE jobs SET stage='uncertain',patch_sha=NULL,error='unresolved_job'")
        ledger.db.execute('UPDATE request_contracts SET output_kind=NULL')
        json_write(directory/'protocol-completion.json', {'completed':True,'thread_id':self.thread,
                    'transport':'exec','answer':answer})
        self.engine.close()
        original=commands.Engine
        def factory(config,paths,gate):
            return original(config,paths,gate,core=FakeCore(),codex=self.codex)
        with patch.object(commands,'Engine',side_effect=factory):
            result=commands.recover(self.paths)
        self.assertTrue(result['recovered']); self.assertFalse(result['model_called'])
        self.assertFalse(result['service_started']); self.assertEqual(self.codex.calls,1)
        self.assertEqual(self.ledger().current()['patch_sha'],row['patch_sha'])




class DecisionRetryGuards(RetryCase):
    def test_new_readonly_retry_preserves_decision_contract(self):
        self.engine.tick()
        original=json_read(attempt_directory(self.paths,self.seed['sha256'],0)/'attempt.json')
        self.now+=60; self.engine.tick()
        retry=json_read(attempt_directory(self.paths,self.seed['sha256'],1)/'attempt.json')
        self.assertEqual(retry['request_contract'],original['request_contract'])
        self.assertEqual(self.codex.calls,2)

    def test_changed_decision_prompt_is_not_a_readonly_retry_permission(self):
        self.engine.tick()
        self.codex.turns['turn-1']['items'][0]['content'][0]['text'] += '\nForeign authority'
        self.now+=60
        self.assertTrue(self.engine.tick()['halted']); self.assertEqual(self.codex.calls,1)

    def test_legacy_partial_overload_can_continue_without_new_authority(self):
        directory=attempt_directory(self.paths,self.seed['sha256'],0); private_dir(directory)
        json_write(directory/'attempt.json',{'source_sha256':self.seed['sha256'], 'thread_id':self.thread,
            'number':0, 'workspace_sha256':fingerprint(self.dev),
            'request_source':{k:self.seed[k] for k in ('path','sha256','binding','run_id')}})
        codex=PartialCodex(self); self.engine.codex=codex; codex.observe=self.engine.observe
        self.assertEqual(self.engine.tick()['retry_after'],60)
        self.now+=60; self.engine.tick()
        self.assertEqual(codex.calls,2)
        retry=json_read(attempt_directory(self.paths,self.seed['sha256'],1)/'attempt.json')
        self.assertEqual(retry['request_contract'],contract())

    def test_versioned_partial_overload_preserves_authority(self):
        codex=PartialCodex(self); self.engine.codex=codex; codex.observe=self.engine.observe
        self.assertEqual(self.engine.tick()['retry_after'],60)
        self.now+=60; self.engine.tick()
        self.assertEqual(codex.calls,2)
        first=json_read(attempt_directory(self.paths,self.seed['sha256'],0)/'attempt.json')
        second=json_read(attempt_directory(self.paths,self.seed['sha256'],1)/'attempt.json')
        self.assertEqual(first['request_contract'],second['request_contract'])
