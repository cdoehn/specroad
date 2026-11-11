"""Reset is an explicit bounded exception; it cannot waive ordinary proof gates."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from unittest.mock import patch

import pytest

from specroad_control.apply_reconcile_proof import canonical, hashed
from specroad_control.current_acceptance_history import validate_history
from specroad_control.current_acceptance_proof import RESET_CAPABILITY
from specroad_control.errors import ControlError
from specroad_control.job_contract import new_contract
from specroad_control.local import read_private
from codex_control_tests.apply_reconcile_support import patch_package
from codex_control_tests.current_acceptance_support import AcceptanceCase


class CurrentAcceptanceResetRightTests(AcceptanceCase):
    def test_cli_forwards_explicit_reset_into_the_actual_pending_receipt(self):
        from specroad_control.cli import main
        self.manual(reset_capability=RESET_CAPABILITY)
        output = io.StringIO()
        with patch('specroad_control.cli.Paths.discover', return_value=self.paths), redirect_stdout(output):
            code = main(['accept-current', '--result', self.following['path'],
                         '--reason', 'Explicit operator reset', '--clarification', '--reset-budget'])
        self.assertEqual(code, 0)
        reply = json.loads(output.getvalue())
        self.assertTrue(reply['queued'])
        self.assertEqual(reply['request_contract'], new_contract(3, version=4))
        self.assertIs(validate_history(self.ledger())['reset_budget'], True)
        self.assertEqual(self.codex.calls, 0)

    def test_missing_reset_capability_refuses_without_persisting_intent(self):
        self.manual()
        before = self.ledger().current()
        with self.assertRaises(ControlError): self.accept_current(reset_budget=True)
        self.assertEqual(before, self.ledger().current())
        self.assertIsNone(validate_history(self.ledger()))
        self.assertEqual(self.codex.calls, 0)

    def reject_marker(self, **extra):
        self.manual(reset_capability={**RESET_CAPABILITY, **extra})
        with self.assertRaises(ControlError): self.accept_current(reset_budget=True)
        self.assertIsNone(validate_history(self.ledger()))

    def test_boolean_limit_is_not_an_integer_capability(self):
        self.reject_marker(clarification_limit=True)

    def test_unknown_marker_fields_cannot_introduce_force(self):
        self.reject_marker(force=True)

    def test_marker_cannot_discard_history(self):
        self.reject_marker(history_policy='discard')

    def test_reset_needs_the_new_receipt_version(self):
        self.reject_marker(receipt_version=1)

    def test_reset_limit_cannot_be_extended(self):
        self.reject_marker(clarification_limit=4)

    def test_explicit_reset_is_idempotent_and_cannot_be_removed_on_retry(self):
        self.manual(reset_capability=RESET_CAPABILITY)
        first = self.accept_current(reset_budget=True)
        self.assertEqual(first, self.accept_current(reset_budget=True))
        with self.assertRaises(ControlError): self.accept_current(reset_budget=False)
        self.adopt(reset_budget=True)
        self.assertTrue(self.accept_current(reset_budget=True)['completed'])
        self.assertEqual(self.ledger().db.execute('SELECT COUNT(*) FROM current_acceptances').fetchone()[0], 1)

    def test_preserving_receipt_cannot_be_replaced_by_reset(self):
        self.manual(reset_capability=RESET_CAPABILITY)
        self.accept_current()
        doc = validate_history(self.ledger())
        with self.assertRaises(ControlError): self.accept_current(reset_budget=True)
        self.assertEqual(validate_history(self.ledger()), doc)

    def test_reset_without_clarification_or_with_nontyped_flag_has_no_effect(self):
        self.manual(reset_capability=RESET_CAPABILITY)
        for changes in ({'reset_budget': True, 'clarification': False},
                        {'reset_budget': 1}, {'reset_budget': 'true'}, {'reset_budget': None}):
            with self.subTest(changes=changes), self.assertRaises(ControlError):
                self.accept_current(**changes)
        self.assertIsNone(validate_history(self.ledger()))

    def test_empty_reason_and_open_continuation_cannot_reset(self):
        self.manual(reset_capability=RESET_CAPABILITY)
        with self.assertRaises(ControlError): self.accept_current(reset_budget=True, reason=' ')
        # Isolated ledger fixture: a pending prefix remains a distinct authority.
        self.ledger().db.execute('UPDATE clarification_continuations SET pending=1 WHERE sha=?',
                                 (self.seed['sha256'],))
        self.assertTrue(self.ledger().request_contract()['clarification_continuation'])
        with self.assertRaises(ControlError): self.accept_current(reset_budget=True)
        self.assertIsNone(validate_history(self.ledger()))

    def test_full_apply_evidence_is_still_required(self):
        self.manual(completed=1, reset_capability=RESET_CAPABILITY)
        with self.assertRaises(ControlError): self.accept_current(reset_budget=True)
        self.assertIsNone(validate_history(self.ledger()))

    def test_native_lock_or_followup_blocks_explicit_reset(self):
        self.manual(reset_capability=RESET_CAPABILITY)
        self.engine.core.current.side_effect = ControlError('core_rejected', 'repository busy')
        with self.assertRaises(ControlError): self.accept_current(reset_budget=True)
        self.engine.core.current.side_effect = None
        patch_package(self.exchange / 'followup.zip', self.data(self.following))
        with self.assertRaises(ControlError): self.accept_current(reset_budget=True)
        self.assertIsNone(validate_history(self.ledger()))

    def test_active_thread_holds_reset_pending_and_rechecks_before_dispatch(self):
        self.manual(reset_capability=RESET_CAPABILITY)
        self.accept_current(reset_budget=True)
        self.engine.gate.set(True)
        self.codex.activity.return_value = 'active'
        self.assertFalse(self.engine.tick()['again'])
        self.assertEqual(self.ledger().current()['sha'], self.seed['sha256'])
        self.assertEqual(self.codex.calls, 0)
        self.codex.activity.return_value = 'idle'
        self.assertTrue(self.engine.tick()['again'])
        self.engine.core.current.side_effect = ControlError('core_rejected', 'changed before dispatch')
        self.assertTrue(self.dispatch()['halted'])
        self.assertEqual(self.codex.calls, 0)

    def test_same_source_patchless_blocker_preserves_original_attempt_bytes(self):
        self.manual(0, reset_capability=RESET_CAPABILITY)
        self.engine.tick()
        self.block_current()
        source = self.following['sha256']
        directory = self.paths.state / 'jobs' / source
        before = {p.name: read_private(p) for p in directory.iterdir() if p.is_file()}
        self.adopt(reset_budget=True)
        self.assertEqual(before, {name: read_private(directory / name) for name in before})
        self.assertEqual(self.ledger().recorded_contract(source), new_contract(0, allowed=False, version=4))
        self.assertEqual(self.ledger().request_contract(), new_contract(3, version=4))

    def test_version_two_receipt_cannot_omit_or_coerce_its_reset_intent(self):
        self.manual(reset_capability=RESET_CAPABILITY)
        self.accept_current(reset_budget=True)
        ledger = self.ledger()
        original = validate_history(ledger)
        for value in (False, 1, 'true', None):
            changed = deepcopy(original)
            if value is None: changed.pop('reset_budget')
            else: changed['reset_budget'] = value
            ledger.db.execute('UPDATE current_acceptances SET proof=?,proof_sha=?',
                              (canonical(changed).decode(), hashed(changed)))
            with self.subTest(value=value), self.assertRaises(ControlError): validate_history(ledger)
        ledger.db.execute('UPDATE current_acceptances SET proof=?,proof_sha=?',
                          (canonical(original).decode(), hashed(original)))
        self.assertEqual(validate_history(ledger), original)

    def test_completed_reset_does_not_make_base_budget_mutable(self):
        self.manual(reset_capability=RESET_CAPABILITY)
        self.adopt(reset_budget=True)
        ledger = self.ledger()
        ledger.db.execute('UPDATE clarification_budgets SET remaining=1 WHERE sha=?', (self.following['sha256'],))
        with self.assertRaises(ControlError): validate_history(ledger)


@pytest.mark.parametrize('args', [
    ['status', '--reset-budget'], ['resume', '--reset-budget'],
    ['accept-current', '--result', '/x.zip', '--reason', 'reset', '--no-clarification', '--reset-budget'],
    ['accept-current', '--clarification', '--reset-budget'],
])
def test_bad_reset_cli_options_stop_before_local_state_or_services(args):
    from specroad_control.cli import main
    with patch('specroad_control.cli.Paths.discover') as discover, redirect_stderr(io.StringIO()):
        with pytest.raises(SystemExit) as error: main(args)
        assert error.value.code == 2
        discover.assert_not_called()
