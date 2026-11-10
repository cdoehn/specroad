"""An explicit operator reset creates new authority without rewriting the past."""
from specroad_control.current_acceptance_history import validate_history
from specroad_control.current_acceptance_proof import RESET_CAPABILITY
from specroad_control.job_contract import new_contract
from codex_control_tests.current_acceptance_support import AcceptanceCase


class CurrentAcceptanceResetTests(AcceptanceCase):
    def test_explicit_reset_is_queued_then_adopted_with_original_budget_intact(self):
        self.manual(2, reset_capability=RESET_CAPABILITY)
        before = self.ledger().current()
        reply = self.accept_current(reset_budget=True)
        self.assertTrue(reply['queued'])
        self.assertTrue(reply['budget_reset'])
        self.assertEqual(reply['request_contract'], new_contract(3, version=4))
        self.assertEqual(before, self.ledger().current())
        doc = validate_history(self.ledger())
        self.assertEqual(doc['version'], 2)
        self.assertIs(doc['reset_budget'], True)
        self.assertEqual(doc['previous_contract'], new_contract(2, allowed=False, version=4))
        self.assertFalse(self.engine.tick()['again'])  # Paused means no adoption.
        self.assertEqual(self.codex.calls, 0)
        self.adopt(reset_budget=True)
        ledger = self.ledger()
        self.assertEqual(ledger.request_contract(), new_contract(3, version=4))
        self.assertEqual(ledger.request_contract(self.seed['sha256']), doc['previous_contract'])
        self.assertEqual(self.codex.calls, 0)

    def test_zero_remaining_can_be_explicitly_renewed(self):
        self.manual(0, reset_capability=RESET_CAPABILITY)
        self.adopt(reset_budget=True)
        self.assertEqual(self.ledger().request_contract(), new_contract(3, version=4))
        self.assertEqual(self.ledger().recorded_contract(self.seed['sha256']),
                         new_contract(0, allowed=False, version=4))

    def test_operator_reset_does_not_repeat_when_the_mixed_apply_fails(self):
        self.manual(1, reset_capability=RESET_CAPABILITY)
        self.adopt(reset_budget=True)
        self.assertFalse(self.dispatch(mixed=True)['halted'])
        self.assertEqual(self.ledger().output_kind(), 'patch_ready_with_clarification')
        self.outcome(completed=1)
        self.engine.tick()
        self.assertEqual(self.ledger().request_contract(),
                         new_contract(2, allowed=False, version=4))

    def test_without_reset_the_existing_receipt_and_budget_stay_version_one(self):
        self.manual(2, reset_capability=RESET_CAPABILITY)
        self.accept_current()
        self.assertEqual(validate_history(self.ledger())['version'], 1)
        self.adopt()
        self.assertEqual(self.ledger().request_contract(), new_contract(2, version=4))
