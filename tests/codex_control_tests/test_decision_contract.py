"""Versioned handoffs and durable budgets, using isolated protocol doubles."""
from specroad_control.automation import Engine, Gate
from specroad_control.continuation_evidence import request_prompt
from specroad_control.errors import ControlError
from specroad_control.job_contract import contract, schema_for
from specroad_control.local import json_read, json_write, private_dir
from codex_control_tests.automation_support import FakeCore, FakeCodex
from codex_control_tests.decision_support import DecisionCase


class DecisionContractTests(DecisionCase):
    def test_new_job_pins_version_and_accepts_exact_clarification_bundle(self):
        self.assertTrue(self.engine.tick()['again'])
        self.assertEqual(self.ledger().current()['stage'], 'waiting_result')
        self.assertEqual(self.ledger().request_contract(), {'version': 2, 'clarification_allowed': True})
        receipt = json_read(self.paths.state/'jobs'/self.seed['sha256']/'attempt.json')
        self.assertEqual(receipt['request_contract'], self.ledger().request_contract())
        self.assertIn('spec_clarification', self.codex.schemas[0]['properties']['status']['enum'])

    def test_no_model_is_called_while_waiting_for_clarification_apply(self):
        self.engine.tick()
        for _ in range(3):
            self.assertFalse(self.engine.tick()['again'])
        self.assertEqual(self.codex.calls, 1)

    def test_successful_clarification_resumes_normal_work_without_new_clarification(self):
        self.engine.tick(); self.follow()
        self.codex.kind = 'patch_ready'
        self.assertTrue(self.engine.tick()['again'])
        self.assertEqual(self.codex.calls, 2)
        self.assertNotIn('spec_clarification', self.codex.schemas[-1]['properties']['status']['enum'])
        self.assertFalse(self.ledger().request_contract()['clarification_allowed'])

    def test_second_consecutive_clarification_is_blocked_despite_valid_package(self):
        self.engine.tick(); self.follow()
        self.assertTrue(self.engine.tick()['halted'])
        self.assertEqual(self.ledger().current()['error'], 'clarification_limit')
        self.assertTrue(self.engine.tick()['halted'])
        self.assertEqual(self.codex.calls, 2)

    def test_failed_clarification_does_not_reset_budget(self):
        self.engine.tick(); self.follow(success=False, dirty=True, primary_kind='entrypoint_failed')
        self.codex.kind = 'patch_ready'
        self.engine.tick()
        self.assertFalse(self.ledger().request_contract()['clarification_allowed'])

    def test_normal_successful_committed_apply_reopens_clarification_budget(self):
        self.engine.tick(); self.follow()
        self.codex.kind = 'patch_ready'; self.engine.tick()
        self.follow('third.zip', binding={**self.binding, 'base_commit': 'd'*40})
        self.codex.kind = 'spec_clarification'; self.engine.tick()
        self.assertTrue(self.ledger().request_contract()['clarification_allowed'])
        self.assertEqual(self.ledger().current()['stage'], 'waiting_result')

    def test_pause_preserves_budget_and_prevents_dispatch_after_apply(self):
        self.engine.tick(); self.follow(); self.engine.gate.set(False)
        self.engine.tick()
        self.assertEqual(self.codex.calls, 1)
        self.assertFalse(self.ledger().request_contract()['clarification_allowed'])
        self.codex.kind = 'patch_ready'; self.engine.gate.set(True); self.engine.tick()
        self.assertEqual(self.codex.calls, 2)

    def test_restart_preserves_budget(self):
        self.engine.tick(); self.follow(); self.engine.gate.set(False); self.engine.tick()
        self.engine.close()
        with Engine(self.config, self.paths, Gate(), core=FakeCore(), codex=self.codex) as engine:
            self.assertTrue(engine.tick()['halted'])
            self.assertEqual(engine.summary()['error'], 'clarification_limit')

    def test_legacy_attempt_stays_legacy(self):
        directory = self.paths.state/'jobs'/self.seed['sha256']; private_dir(directory)
        original = {'source_sha256': self.seed['sha256'], 'thread_id': self.thread, 'number': 0,
                    'request_source': {k: self.seed[k] for k in ('path', 'sha256', 'binding', 'run_id')}}
        json_write(directory/'attempt.json', original)
        content = (directory/'attempt.json').read_bytes()
        self.codex.kind = 'patch_ready'; self.engine.tick()
        self.assertEqual((directory/'attempt.json').read_bytes(), content)
        self.assertEqual(self.ledger().request_contract(), contract())
        self.assertEqual(self.codex.schemas[0], schema_for())
        self.assertEqual(self.codex.prompts[0], request_prompt(original, self.seed))

    def test_contract_cannot_gain_permission_after_it_is_bound(self):
        ledger = self.ledger()
        ledger.bind_contract({'version': 2, 'clarification_allowed': False})
        with self.assertRaises(ControlError):
            ledger.bind_contract({'version': 2, 'clarification_allowed': True})
        self.assertFalse(ledger.request_contract()['clarification_allowed'])

    def test_unknown_versions_and_malformed_flags_fail_closed(self):
        for value in ({'version': 3, 'clarification_allowed': True},
                      {'version': True, 'clarification_allowed': False},
                      {'version': 2, 'clarification_allowed': 1},
                      {'version': 1, 'clarification_allowed': True}):
            with self.subTest(value=value), self.assertRaises(ControlError):
                schema_for(value)

    def test_archiving_does_not_change_request_identity_in_either_version(self):
        for selected in (contract(), {'version': 2, 'clarification_allowed': False}):
            attempt = {'request_source': {k: self.seed[k] for k in ('path', 'sha256', 'binding', 'run_id')},
                       'request_contract': selected}
            expected = request_prompt(attempt, self.seed)
            self.assertEqual(request_prompt(attempt, {**self.seed, 'path': '/archive/renamed.zip'}), expected)

    def test_blocked_still_requires_explicit_recovery(self):
        self.engine.codex = FakeCodex(self, 'blocked')
        self.assertTrue(self.engine.tick()['halted'])
        self.assertEqual(self.ledger().current()['error'], 'dev_blocked')
        self.assertTrue(self.engine.tick()['halted'])
        self.assertEqual(self.engine.codex.calls, 1)
