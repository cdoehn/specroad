"""Failure boundaries preserve immutable authority and atomic source claims."""
import hashlib
import json
import sqlite3
from unittest.mock import patch
from specroad_control import commands
from specroad_control.errors import ControlError
from specroad_control.job_contract import new_contract, prompt_for, continuation_prompt
from specroad_control.local import json_read, json_write
from specroad_control.retry_ledger import attempt_directory
from codex_control_tests.automation_support import FakeCore
from codex_control_tests.decision_support import DecisionCase
from codex_control_tests.test_overload_retry import RetryCase
from codex_control_tests.test_continuation import PartialCodex


class BudgetGuards(DecisionCase):
    legacy_contract = False

    def test_coherent_changed_counter_does_not_claim_followup(self):
        self.ledger().bind_contract(new_contract(1))
        self.engine.tick(); source = self.follow(); ledger = self.ledger(); before = ledger.current()
        ledger.db.execute('UPDATE clarification_budgets SET remaining=3')
        with self.assertRaises(ControlError) as caught:
            self.engine.tick()
        self.assertEqual(caught.exception.code, 'request_contract_changed')
        self.assertEqual(ledger.current(), before)
        self.assertNotIn(source['run_id'], ledger.known_runs())
        self.assertEqual(self.codex.calls, 1)

    def test_missing_attempt_does_not_claim_classified_followup(self):
        self.engine.tick(); source = self.follow(); before = self.ledger().current()
        (attempt_directory(self.paths, self.seed['sha256'], 0)/'attempt.json').unlink()
        with self.assertRaises(ControlError):
            self.engine.tick()
        self.assertEqual(self.ledger().current(), before)
        self.assertNotIn(source['run_id'], self.ledger().known_runs())

    def test_missing_budget_is_an_error_not_a_fresh_allowance(self):
        ledger = self.ledger(); ledger.bind_contract(new_contract())
        ledger.db.execute('DELETE FROM clarification_budgets')
        with self.assertRaises(ControlError) as caught:
            self.engine.tick()
        self.assertEqual(caught.exception.code, 'request_contract_invalid')
        self.assertEqual(self.codex.calls, 0)

    def test_orphan_budget_cannot_create_a_new_contract(self):
        ledger = self.ledger(); ledger.bind_contract(new_contract(1))
        ledger.db.execute('DELETE FROM request_contracts')
        with self.assertRaises(ControlError) as caught:
            self.engine.tick()
        self.assertEqual(caught.exception.code, 'request_contract_invalid')
        self.assertEqual(self.codex.calls, 0)

    def test_invalid_persisted_budget_is_never_permission(self):
        ledger = self.ledger(); ledger.bind_contract(new_contract(1))
        for value in (-1, 4, 'unknown', 1.5):
            with self.subTest(value=value):
                ledger.db.execute('UPDATE clarification_budgets SET remaining=?', (value,))
                with self.assertRaises(ControlError) as caught:
                    ledger.request_contract()
                self.assertEqual(caught.exception.code, 'request_contract_invalid')
        ledger.db.execute('UPDATE clarification_budgets SET remaining=1, maximum=4')
        with self.assertRaises(ControlError):
            ledger.request_contract()

    def test_budget_insertion_failure_rolls_back_new_job_and_both_tables(self):
        self.engine.tick(); source = self.follow(); ledger = self.ledger(); before = ledger.current()
        insert = ledger._insert_contract
        def fail(*args):
            insert(*args)
            raise sqlite3.OperationalError('simulated disk failure after budget insert')
        with patch.object(ledger, '_insert_contract', side_effect=fail), self.assertRaises(sqlite3.Error):
            ledger.enqueue(source)
        self.assertEqual(ledger.current(), before)
        self.assertEqual(ledger.request_contract(), new_contract())
        for table in ('jobs', 'request_contracts', 'clarification_budgets'):
            self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0], 1)

    def test_reobserving_same_handoff_is_idempotent(self):
        self.engine.tick(); ledger = self.ledger(); before = ledger.current()
        for _ in range(3):
            ledger.change('waiting_result', patch_sha=before['patch_sha'], output_kind='spec_clarification')
        self.follow(); self.engine.gate.set(False); self.engine.tick()
        self.assertEqual(ledger.request_contract(), new_contract(2))

    def test_changed_attempt_at_dispatch_cannot_gain_slots(self):
        self.ledger().bind_contract(new_contract(1)); original = self.engine.exchange.assert_current
        count = 0
        def inspect(*args):
            nonlocal count
            original(*args); count += 1
            if count == 2:
                directory = attempt_directory(self.paths, self.seed['sha256'], 0)
                doc = json_read(directory/'attempt.json')
                doc['request_contract'] = new_contract()
                json_write(directory/'attempt.json', doc)
        self.engine.exchange.assert_current = inspect
        self.assertTrue(self.engine.tick()['halted'])
        self.assertEqual(self.codex.calls, 0)
        self.assertEqual(self.ledger().current()['error'], 'request_contract_changed')

    def test_clean_flag_is_required_for_replenishment(self):
        self.ledger().bind_contract(new_contract(0)); self.codex.kind = 'patch_ready'
        self.engine.tick(); self.follow(dirty=True)
        self.engine.gate.set(False); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(), new_contract(0))

    def test_completion_must_match_original_v3_attempt(self):
        self.engine.tick(); ledger = self.ledger()
        directory = attempt_directory(self.paths, self.seed['sha256'], 0)
        answer = json_read(directory/'completion.json')
        doc = json_read(directory/'attempt.json'); doc['request_contract'] = new_contract(1)
        json_write(directory/'attempt.json', doc)
        with self.assertRaises(ControlError) as caught:
            self.engine.accept(ledger, ledger.current()['source'], answer)
        self.assertEqual(caught.exception.code, 'request_contract_changed')

    def test_v3_crash_recovery_preserves_budget_without_model_or_service(self):
        self.ledger().bind_contract(new_contract(1)); self.engine.tick()
        ledger = self.ledger(); row = ledger.current()
        directory = attempt_directory(self.paths, self.seed['sha256'], 0)
        answer = json_read(directory/'completion.json')
        ledger.db.execute("UPDATE jobs SET stage='uncertain',patch_sha=NULL,error='unresolved_job'")
        ledger.db.execute('UPDATE request_contracts SET output_kind=NULL')
        json_write(directory/'protocol-completion.json', {'completed':True, 'thread_id':self.thread,
                   'transport':'exec', 'answer':answer})
        self.engine.close(); original = commands.Engine
        def factory(config, paths, gate):
            return original(config, paths, gate, core=FakeCore(), codex=self.codex)
        with patch.object(commands, 'Engine', side_effect=factory):
            result = commands.recover(self.paths)
        self.assertTrue(result['recovered']); self.assertFalse(result['model_called'])
        self.assertFalse(result['service_started'])
        self.assertEqual(ledger.request_contract(), new_contract(1))
        self.assertEqual(ledger.current()['patch_sha'], row['patch_sha'])
        self.assertEqual(self.codex.calls, 1)

    def test_v2_prompt_and_continuation_identities_remain_exact(self):
        source = {'path':'/reference/result.zip','sha256':'1'*64,
                  'binding':{'repo_id':'00000000-0000-4000-8000-000000000001',
                             'base_commit':'2'*40,'state_fingerprint':'3'*16,
                             'fingerprint_algorithm':'patchharbor-state-v1'},
                  'run_id':'00000000-0000-4000-8000-000000000002'}
        source = json.loads(json.dumps(source, sort_keys=True))
        evidence = {'turn_id':'original-turn','workspace_sha256':'4'*64,'history_sha256':'5'*64}
        # Protocol identities captured from shipped FIX10, not editorial assertions.
        hashes = {
            False: ('045bf52c672205c8d5a6cc48d6ac8f01eed77e0eef2821297ff175ed9c4e9ac2',
                    '55aeb896880aa5b42b34ee000611ba409c55b52c81581562c5acfa9d5a783a9d'),
            True: ('988193abcf6c7a1e8113579a39cd60042ea0f734ea287aabc1b20273839ba669',
                   'e1c8afefc4c3eadb68bf6685fd8eb53ec8bd81f2b65132af24e4b2eb74dec234')}
        for allowed, expected in hashes.items():
            selected = {'version':2, 'clarification_allowed':allowed}
            observed = (prompt_for(source, selected), continuation_prompt(source, evidence, selected))
            self.assertEqual(tuple(hashlib.sha256(s.encode()).hexdigest() for s in observed), expected)


class BudgetRetryGuards(RetryCase):
    def test_readonly_retry_keeps_one_remaining_slot(self):
        self.ledger().bind_contract(new_contract(1)); self.engine.tick()
        original = json_read(attempt_directory(self.paths, self.seed['sha256'], 0)/'attempt.json')
        self.now += 60; self.engine.tick()
        retry = json_read(attempt_directory(self.paths, self.seed['sha256'], 1)/'attempt.json')
        self.assertEqual(original['request_contract'], new_contract(1))
        self.assertEqual(retry['request_contract'], original['request_contract'])

    def test_partial_overload_keeps_one_remaining_slot(self):
        self.ledger().bind_contract(new_contract(1))
        codex = PartialCodex(self); self.engine.codex = codex; codex.observe = self.engine.observe
        self.engine.tick(); self.now += 60; self.engine.tick()
        first = json_read(attempt_directory(self.paths, self.seed['sha256'], 0)/'attempt.json')
        second = json_read(attempt_directory(self.paths, self.seed['sha256'], 1)/'attempt.json')
        self.assertEqual(first['request_contract'], new_contract(1))
        self.assertEqual(second['request_contract'], first['request_contract'])
        self.assertEqual(codex.calls, 2)

    def test_changed_v3_prompt_prevents_readonly_retry(self):
        self.ledger().bind_contract(new_contract(1)); self.engine.tick()
        self.codex.turns['turn-1']['items'][0]['content'][0]['text'] += '\nChanged budget'
        self.now += 60
        self.assertTrue(self.engine.tick()['halted'])
        self.assertEqual(self.codex.calls, 1)
