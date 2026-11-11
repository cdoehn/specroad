"""Budget continuity and explicit opt-out; no model retries spend repair slots."""
from dataclasses import replace
import json
from hashlib import sha256
from unittest.mock import patch

from specroad_control.automation import Engine, Gate
from specroad_control.config import parse, render
from specroad_control.correction_budget import bind, read, preserve
from specroad_control.current_acceptance_policy import selection
from specroad_control.errors import ControlError
from specroad_control.job_contract import new_contract
from specroad_control.toml_compat import tomllib
from codex_control_tests.mixed_support import MixedCase
from specroad_control.mixed_contract import CAPABILITY
from codex_control_tests.current_acceptance_support import AcceptanceCase


class DevelopmentDefaultsRightTests(MixedCase):
    def setUp(self):
        marker = patch('codex_control_tests.mixed_support.CAPABILITY',
                       {**CAPABILITY, 'clarification_limit': 5})
        marker.start(); self.addCleanup(marker.stop)
        super().setUp()

    def test_restart_and_changed_default_preserve_consumed_budget(self):
        self.dispatch(); self.outcome(completed=0); self.engine.tick()
        self.dispatch(data=self.correction()); self.outcome(completed=0); self.engine.tick()
        source = self.ledger().current()['source']
        before = read(self.ledger(), source['sha256'])
        self.assertEqual(before['remaining'], 4)
        self.assertEqual(bind(self.ledger(), source, 2), before)
        self.assertEqual(read(self.ledger(), source['sha256']), before)
        for remaining in (3, 2, 1, 0):
            self.assertFalse(self.dispatch(data=self.correction())['halted'])
            self.outcome(completed=0)
            self.engine.tick()
            self.assertEqual(read(self.ledger(), self.following['sha256'])['remaining'], remaining)
        self.assertEqual(self.dispatch(), {'halted': True, 'again': False})
        stopped = self.ledger().current()
        exhausted = read(self.ledger(), stopped['sha'])
        calls = self.codex.calls
        self.engine.close()
        with Engine(replace(self.config, correction_limit=2), self.paths, Gate(),
                    core=self.engine.core, codex=self.codex) as restarted:
            self.assertEqual(restarted.tick(), {'halted': True, 'again': False})
            self.assertEqual(restarted.summary()['error'], 'correction_budget_exhausted')
            self.assertEqual(restarted.summary()['correction_budget'], exhausted)
        self.assertEqual(self.codex.calls, calls)
        self.assertEqual(self.ledger().current()['sha'], stopped['sha'])
        self.assertEqual(self.ledger().current()['error'], 'correction_budget_exhausted')
        self.assertEqual(read(self.ledger(), stopped['sha']), exhausted)
        self.assertFalse(self.ledger().attempt_directory(self.paths, stopped['sha'], 0).exists())

    def test_invalid_config_limits_fail_instead_of_becoming_truthy(self):
        for value in (True, False, 0, 6, -1, 2.5, '5'):
            document = tomllib.loads(render(self.config))
            document['automation']['correction_limit'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse(document, self.paths)
        document = tomllib.loads(render(self.config))
        document['automation']['clarification_allowed'] = 'false'
        with self.assertRaises(ValueError):
            parse(document, self.paths)

    def test_partial_success_never_renews_repairs(self):
        self.dispatch(); self.outcome(completed=0); self.engine.tick()
        self.dispatch(data=self.correction()); self.outcome(completed=1); self.engine.tick()
        current = read(self.ledger(), self.following['sha256'])
        self.assertTrue(current['active'])
        self.assertEqual(current['remaining'], 4)

    def test_forged_counter_with_recomputed_hash_is_rejected(self):
        self.dispatch(); self.outcome(completed=0); self.engine.tick()
        self.dispatch(data=self.correction()); self.outcome(completed=0); self.engine.tick()
        ledger = self.ledger(); identity = ledger.current()['sha']
        value = read(ledger, identity); value['remaining'] += 1
        raw = json.dumps(value, sort_keys=True, separators=(',', ':'))
        ledger.db.execute('UPDATE apply_correction_budgets SET proof=?,sha256=? WHERE source_sha=?',
                          (raw, sha256(raw.encode()).hexdigest(), identity))
        with self.assertRaises(ControlError):
            read(ledger, identity)

    def test_explicit_disabled_selection_has_additive_semantics(self):
        old = new_contract(4, version=4, limit=5)
        self.assertTrue(selection(old, None, False, 'same_ready')['clarification_allowed'])
        current = selection(old, None, False, 'same_ready', strict_choice=True)
        self.assertFalse(current['clarification_allowed'])
        self.assertEqual(current['clarifications_remaining'], 4)
        self.assertEqual(current['clarification_limit'], 5)


class CurrentDefaultAcceptanceTests(AcceptanceCase):
    def test_accept_current_uses_config_default_without_flag(self):
        self.manual()
        reply = self.accept_current(clarification=None)
        self.assertTrue(reply['request_contract']['clarification_allowed'])

    def test_accept_current_honours_disabled_config_without_flag(self):
        self.manual()
        self.config = replace(self.config, clarification_allowed=False)
        self.engine.config = self.config
        self.paths.config.write_text(render(self.config))
        reply = self.accept_current(clarification=None)
        self.assertFalse(reply['request_contract']['clarification_allowed'])

    def test_new_receipt_records_disabled_selection_without_rewriting_old_contract(self):
        self.manual(); self.engine.tick()
        ledger = self.ledger()
        # Synthetic unissued ready source with an existing positive grant.
        ledger.db.execute('UPDATE request_contracts SET allowed=1 WHERE sha=?', (ledger.current()['sha'],))
        original = ledger.recorded_contract()
        self.adopt(clarification=False)
        self.assertEqual(self.ledger().recorded_contract(), original)
        self.assertFalse(self.ledger().request_contract()['clarification_allowed'])
        from specroad_control.current_acceptance_history import active
        self.assertEqual(active(self.ledger(), self.ledger().current()['sha'])['version'], 3)
