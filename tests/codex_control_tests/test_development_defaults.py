"""Operator defaults and durable Apply repair limits through real ledger flow."""
from dataclasses import replace
from pathlib import Path
import sys
from unittest.mock import patch

from specroad_control.config import parse, render
from specroad_control.correction_budget import read
from specroad_control.job_contract import contract, new_contract
from specroad_control.mixed_contract import CAPABILITY
from specroad_control.toml_compat import tomllib
from codex_control_tests.mixed_support import MixedCase


class DevelopmentDefaultsTests(MixedCase):
    def setUp(self):
        marker = patch('codex_control_tests.mixed_support.CAPABILITY',
                       {**CAPABILITY, 'clarification_limit': 5})
        marker.start()
        self.addCleanup(marker.stop)
        super().setUp()

    def test_new_supported_request_has_five_slots_and_allows_clarification(self):
        self.assertFalse(self.dispatch(True)['halted'])
        self.assertEqual(self.ledger().request_contract(),
                         new_contract(5, version=4, limit=5))
        self.outcome(completed=1)
        self.engine.tick()
        selected = self.ledger().request_contract()
        self.assertEqual(selected, new_contract(4, allowed=False, version=4, limit=5))
        self.assertFalse(self.dispatch(data=self.correction())['halted'])
        self.outcome()
        self.engine.tick()
        self.assertEqual(self.ledger().request_contract(),
                         new_contract(5, version=4, limit=5))

    def test_external_config_defaults_true_and_explicit_false_round_trips(self):
        configured = replace(self.config, core_python=Path(sys.executable),
                             codex_executable=Path(sys.executable))
        document = tomllib.loads(render(configured))
        document['automation'].pop('clarification_allowed')
        document['automation'].pop('correction_limit')
        selected = parse(document, self.paths)
        self.assertTrue(selected.clarification_allowed)
        self.assertEqual(selected.correction_limit, 5)
        disabled = replace(selected, clarification_allowed=False, correction_limit=2)
        reread = parse(tomllib.loads(render(disabled)), self.paths)
        self.assertFalse(reread.clarification_allowed)
        self.assertEqual(reread.correction_limit, 2)

    def test_disabled_default_blocks_only_new_clarification(self):
        self.engine.config = replace(self.config, clarification_allowed=False)
        self.assertFalse(self.dispatch()['halted'])
        self.assertEqual(self.ledger().request_contract(),
                         new_contract(5, allowed=False, version=4, limit=5))
        self.outcome()
        self.engine.tick()
        self.assertFalse(self.ledger().request_contract()['clarification_allowed'])
        self.assertEqual(self.ledger().request_contract()['clarifications_remaining'], 5)

    def test_five_failed_apply_repairs_stop_before_a_sixth_model_call(self):
        self.dispatch()
        initial = read(self.ledger(), self.seed['sha256'])
        self.assertEqual((initial['active'], initial['remaining']), (False, 5))
        self.outcome(completed=0)
        self.engine.tick()
        budget = read(self.ledger(), self.following['sha256'])
        self.assertEqual((budget['active'], budget['remaining']), (True, 5))
        for remaining in (4, 3, 2, 1, 0):
            self.assertFalse(self.dispatch(data=self.correction())['halted'])
            self.outcome(completed=0)
            self.engine.tick()
            budget = read(self.ledger(), self.following['sha256'])
            self.assertEqual(budget['remaining'], remaining)
        calls = self.codex.calls
        self.assertTrue(self.dispatch(data=self.correction())['halted'])
        self.assertEqual(self.codex.calls, calls)
        self.assertEqual(self.ledger().current()['error'], 'correction_budget_exhausted')
        stopped = self.ledger().current()
        self.assertEqual(stopped['stage'], 'ready')
        exhausted = read(self.ledger(), stopped['sha'])
        self.assertEqual((exhausted['active'], exhausted['remaining']), (True, 0))
        self.assertEqual(self.engine.summary()['error'], 'correction_budget_exhausted')
        self.assertEqual(self.engine.summary()['correction_budget'], exhausted)
        directory = self.ledger().attempt_directory(self.paths, stopped['sha'], 0)
        self.assertFalse(directory.exists())
        self.assertEqual(self.engine.tick(), {'halted': True, 'again': False})
        self.assertEqual(self.codex.calls, calls)
        self.assertEqual(read(self.ledger(), stopped['sha']), exhausted)
        self.assertFalse(directory.exists())

    def test_complete_clean_repair_reopens_five_places(self):
        self.dispatch()
        self.outcome(completed=0)
        self.engine.tick()
        self.dispatch(data=self.correction())
        self.outcome()
        self.engine.tick()
        budget = read(self.ledger(), self.following['sha256'])
        self.assertEqual((budget['active'], budget['remaining']), (False, 5))

    def test_historical_three_slot_contract_is_still_exactly_readable(self):
        old = new_contract(2, allowed=False, version=4)
        self.assertEqual(contract(old), old)
        self.assertEqual(old['clarification_limit'], 3)
