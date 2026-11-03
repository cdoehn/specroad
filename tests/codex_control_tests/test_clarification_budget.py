"""Bounded multi-result clarification with isolated Core and model doubles."""
from unittest.mock import patch
from specroad_control.automation import Engine, Gate
from specroad_control.errors import ControlError
from specroad_control.job_contract import contract, new_contract, schema_for
from specroad_control.local import json_read
from codex_control_tests.automation_support import FakeCore, FakeCodex, package
from codex_control_tests.decision_support import DecisionCase


class ClarificationBudgetTests(DecisionCase):
    legacy_contract = False

    def advance(self, number, **changes):
        changes.setdefault('binding', {**self.binding, 'base_commit': format(number + 100, '040x')})
        self.follow(f'follow-{number}.zip', **changes)
        self.engine.gate.set(False)
        outcome = self.engine.tick()
        self.assertFalse(outcome['halted'])
        return self.ledger().request_contract()

    def dispatch(self, kind='spec_clarification'):
        self.codex.kind = kind
        self.engine.gate.set(True)
        return self.engine.tick()

    def test_new_source_has_three_durable_slots(self):
        self.dispatch()
        selected = self.ledger().request_contract()
        self.assertEqual(selected, new_contract())
        receipt = json_read(self.paths.state/'jobs'/self.seed['sha256']/'attempt.json')
        self.assertEqual(receipt['request_contract'], selected)

    def test_three_clarifications_then_fourth_rejected(self):
        for number, remaining in enumerate((2, 1, 0), 1):
            self.assertFalse(self.dispatch()['halted'])
            selected = self.advance(number)
            self.assertEqual(selected['clarifications_remaining'], remaining)
            self.assertEqual(selected['clarification_allowed'], remaining > 0)
        self.assertTrue(self.dispatch()['halted'])
        self.assertEqual(self.ledger().current()['error'], 'clarification_limit')
        self.assertNotIn('spec_clarification', self.codex.schemas[-1]['properties']['status']['enum'])

    def test_normal_work_is_allowed_after_third_and_success_reopens_three(self):
        for number in range(1, 4):
            self.dispatch(); self.advance(number)
        self.assertFalse(self.dispatch('patch_ready')['halted'])
        self.assertEqual(self.advance(4), new_contract())
        self.assertFalse(self.dispatch()['halted'])

    def test_failed_clarification_consumes_slot_and_allows_only_repair(self):
        self.dispatch()
        selected = self.advance(1, success=False, dirty=True, primary_kind='entrypoint_failed', completed_commit=None)
        self.assertEqual(selected, new_contract(2, allowed=False))
        self.assertFalse(self.dispatch('patch_ready')['halted'])
        self.assertEqual(self.advance(2), new_contract())

    def test_failed_normal_work_does_not_replenish(self):
        self.dispatch(); self.advance(1); self.dispatch('patch_ready')
        selected = self.advance(2, success=False, primary_kind='entrypoint_failed')
        self.assertEqual(selected, new_contract(2, allowed=False))

    def test_missing_completion_does_not_authorize_another_clarification(self):
        self.dispatch()
        selected = self.advance(1, completed_commit=None)
        self.assertEqual(selected, new_contract(2, allowed=False))

    def test_restart_and_pause_preserve_remaining_budget(self):
        self.dispatch(); self.advance(1); self.dispatch(); selected = self.advance(2)
        self.engine.close()
        gate = Gate(); gate.set(False)
        with Engine(self.config, self.paths, gate, core=FakeCore(), codex=self.codex) as engine:
            self.assertFalse(engine.tick()['halted'])
            self.assertEqual(self.ledger().request_contract(), selected)
            self.assertEqual(self.codex.calls, 2)
            gate.set(True); engine.tick()
            self.assertEqual(self.codex.calls, 3)

    def test_waiting_for_apply_does_not_consume_additional_slots(self):
        self.dispatch(); original = self.ledger().request_contract()
        for _ in range(3):
            self.assertFalse(self.engine.tick()['again'])
        self.assertEqual(self.ledger().request_contract(), original)
        self.assertEqual(self.codex.calls, 1)
        self.assertEqual(self.advance(1)['clarifications_remaining'], 2)

    def test_old_v2_clarification_stays_v2_and_exhausted(self):
        self.ledger().bind_contract({'version': 2, 'clarification_allowed': True})
        self.dispatch()
        self.assertEqual(self.advance(1), {'version': 2, 'clarification_allowed': False})

    def test_old_v2_only_upgrades_after_proven_normal_completion(self):
        self.ledger().bind_contract({'version': 2, 'clarification_allowed': False})
        self.dispatch('patch_ready')
        self.assertEqual(self.advance(1), new_contract())

    def test_existing_blocked_job_is_not_reissued_or_upgraded(self):
        self.ledger().bind_contract({'version': 2, 'clarification_allowed': False})
        self.engine.codex = FakeCodex(self, 'blocked')
        self.assertTrue(self.engine.tick()['halted'])
        self.engine.close()
        with Engine(self.config, self.paths, Gate(), core=FakeCore(), codex=self.codex) as engine:
            self.assertTrue(engine.tick()['halted'])
        self.assertEqual(self.codex.calls, 0)
        self.assertEqual(self.ledger().current()['error'], 'dev_blocked')
        self.assertEqual(self.ledger().request_contract()['version'], 2)

    def test_unclassified_package_adoption_cannot_restore_permission(self):
        self.dispatch(); self.advance(1)
        row = self.ledger().current()
        package(self.exchange/'manual.zip', {'kind':'patch', 'binding':row['source']['binding']})
        self.engine.tick()
        selected = self.advance(2)
        self.assertEqual(selected, new_contract(2, allowed=False))
        self.assertEqual(self.codex.calls, 1)

    def test_invalid_budget_contracts_fail_closed(self):
        examples = [new_contract() | {'clarifications_remaining': value}
                    for value in (-1, 4, True, 1.5, '2', None)]
        examples += [new_contract() | {'clarification_limit': value} for value in (True, 2, 4, '3')]
        examples += [new_contract() | {'clarifications_remaining': 0},
                     new_contract() | {'version': 4},
                     new_contract() | {'extra': 1}]
        for value in examples:
            with self.subTest(value=value), self.assertRaises(ControlError):
                schema_for(value)

    def test_no_new_authority_can_be_attached_to_an_existing_source(self):
        ledger = self.ledger(); ledger.bind_contract(new_contract(1))
        with self.assertRaises(ControlError):
            ledger.bind_contract(new_contract(3))
        self.assertEqual(ledger.request_contract(), new_contract(1))
