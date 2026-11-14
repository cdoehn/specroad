"""New budget policy through isolated native-container and ledger boundaries."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

from specroad_control.config import parse, render
from specroad_control.correction_budget import bind, read
from specroad_control.current_acceptance_history import active, validate_history
from specroad_control.current_acceptance_policy import RESET_CAPABILITY
from specroad_control.decision_policy import successor_contract
from specroad_control.errors import ControlError
from specroad_control.job_contract import contract, fresh_contract, new_contract, schema_for
from specroad_control.mixed_contract import CAPABILITY, MIXED, capability
from specroad_control.toml_compat import tomllib
from codex_control_tests.current_acceptance_support import AcceptanceCase
from codex_control_tests.mixed_support import MixedCase

TWENTY = {**CAPABILITY, 'clarification_limit': 20}


def failed_source(limit=20):
    return {'success': False, 'dirty': True, 'completed_commit': None,
            'binding': {'base_commit': 'a' * 40},
            'development_contract': {**CAPABILITY, 'clarification_limit': limit}}


class TwentyBudgetTests(MixedCase):
    def setUp(self):
        marker = patch('codex_control_tests.mixed_support.CAPABILITY', TWENTY)
        marker.start(); self.addCleanup(marker.stop)
        super().setUp()

    def test_new_request_and_both_default_budgets_have_twenty_places(self):
        self.assertFalse(self.dispatch()['halted'])
        self.assertEqual(self.ledger().request_contract(), new_contract(20, version=4, limit=20))
        budget = read(self.ledger(), self.seed['sha256'])
        self.assertEqual((budget['maximum'], budget['remaining'], budget['active']), (20, 20, False))

    def test_failed_normal_apply_preserves_permission_without_replenishment(self):
        self.dispatch(); original = self.ledger().request_contract()
        self.outcome(completed=0); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(), original)
        self.assertFalse(self.dispatch(data=self.correction())['halted'])
        self.outcome(completed=0); self.engine.tick()
        self.assertTrue(self.ledger().request_contract()['clarification_allowed'])
        self.assertEqual(self.ledger().request_contract(self.seed['sha256']), original)
        self.assertEqual(read(self.ledger(), self.following['sha256'])['remaining'], 19)

    def test_pending_prefix_continues_once_then_normal_rest_keeps_permission(self):
        self.dispatch(mixed=True); original = self.ledger().request_contract()
        self.outcome(completed=0); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(),
                         new_contract(19, allowed=False, version=4, continuation=True, limit=20))
        pending = self.correction()
        self.assertEqual(pending['stages'][0]['after'], self.latest_data['stages'][0]['after'])
        self.assertFalse(self.dispatch(mixed=True, data=pending)['halted'])
        self.outcome(completed=1); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(), new_contract(19, version=4, limit=20))
        rest = self.correction()
        self.assertEqual(rest['handoff_kind'], 'patch_ready')
        self.assertEqual([s['commit_id'] for s in rest['stages']], ['feature.W', 'feature.R', 'feature.C'])
        self.assertFalse(self.dispatch(data=rest)['halted'])
        self.outcome(); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(), new_contract(20, version=4, limit=20))
        self.assertEqual(self.ledger().request_contract(self.seed['sha256']), original)

    def test_twenty_failed_repairs_exhaust_before_twenty_first_dispatch(self):
        self.dispatch(); self.outcome(completed=0); self.engine.tick()
        self.assertEqual(read(self.ledger(), self.following['sha256'])['remaining'], 20)
        for remaining in range(19, -1, -1):
            self.assertFalse(self.dispatch(data=self.correction())['halted'])
            self.outcome(completed=0); self.engine.tick()
            self.assertEqual(read(self.ledger(), self.following['sha256'])['remaining'], remaining)
        calls = self.codex.calls
        self.assertTrue(self.dispatch(data=self.correction())['halted'])
        self.assertEqual(self.codex.calls, calls)
        self.assertEqual(self.ledger().current()['error'], 'correction_budget_exhausted')
        self.assertTrue(self.ledger().request_contract()['clarification_allowed'])
        self.assertEqual(self.ledger().request_contract()['clarifications_remaining'], 20)

    def test_positive_permission_cannot_replace_the_open_implementation_rest(self):
        self.dispatch(mixed=True)
        prefix = deepcopy(self.latest_data['stages'][0])
        self.outcome(completed=1); self.engine.tick()
        self.assertTrue(self.ledger().request_contract()['clarification_allowed'])
        rest = self.correction()
        rest['stages'].insert(0, prefix)
        rest['handoff_kind'] = MIXED
        self.assertTrue(self.dispatch(mixed=True, data=rest)['halted'])
        self.assertIsNone(self.ledger().current()['patch_sha'])

    def test_new_default_does_not_refill_old_repair_budget_until_clean_success(self):
        self.engine.config = replace(self.config, correction_limit=5)
        self.dispatch(); self.outcome(completed=0); self.engine.tick()
        self.dispatch(data=self.correction()); self.outcome(completed=1); self.engine.tick()
        source = self.ledger().current()['source']
        before = read(self.ledger(), source['sha256'])
        self.assertEqual((before['maximum'], before['remaining']), (5, 4))
        self.engine.config = self.config
        self.assertEqual(bind(self.ledger(), source, 20), before)
        self.assertFalse(self.dispatch(data=self.correction())['halted'])
        self.outcome(); self.engine.tick()
        after = read(self.ledger(), self.following['sha256'])
        self.assertEqual((after['maximum'], after['remaining'], after['active']), (20, 20, False))
        self.assertEqual(read(self.ledger(), source['sha256']), before)

    def test_explicit_opt_out_remains_disabled_after_failure_and_success(self):
        self.engine.config = replace(self.config, clarification_allowed=False)
        self.dispatch(); self.outcome(completed=0); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(),
                         new_contract(20, allowed=False, version=4, limit=20))
        self.dispatch(data=self.correction()); self.outcome(); self.engine.tick()
        self.assertFalse(self.ledger().request_contract()['clarification_allowed'])

    def test_config_accepts_the_full_range_and_preserves_an_explicit_old_limit(self):
        config = replace(self.config, core_python=Path(sys.executable), codex_executable=Path(sys.executable))
        for limit in (1, 3, 5, 6, 19, 20):
            with self.subTest(limit=limit):
                selected = parse(tomllib.loads(render(replace(config, correction_limit=limit))), self.paths)
                self.assertEqual(selected.correction_limit, limit)
        document = tomllib.loads(render(config))
        document['automation'].pop('correction_limit')
        self.assertEqual(parse(document, self.paths).correction_limit, 20)


@pytest.mark.parametrize('limit', [3, 5, 20])
def test_fresh_contract_uses_only_the_declared_project_maximum(limit):
    assert fresh_contract(failed_source(limit)) == new_contract(limit, version=4, limit=limit)


@pytest.mark.parametrize('limit', [3, 5, 20])
def test_positive_legacy_balance_is_preserved_under_new_source_policy(limit):
    previous = new_contract(2, allowed=False, version=4, limit=limit)
    original = deepcopy(previous)
    selected = successor_contract(previous, 'patch_ready', failed_source(), verified=True)
    assert selected == new_contract(2, version=4, limit=limit)
    assert previous == original


@pytest.mark.parametrize('limit', [3, 5])
def test_old_project_markers_keep_failed_successor_policy(limit):
    previous = new_contract(limit, version=4, limit=limit)
    selected = successor_contract(previous, MIXED, failed_source(limit), verified=True)
    assert selected == new_contract(limit - 1, allowed=False, version=4, limit=limit)


@pytest.mark.parametrize('handoff', ['patch_ready', MIXED, None])
def test_unverified_successor_never_grants_clarification(handoff):
    previous = new_contract(4, version=4, limit=20)
    selected = successor_contract(previous, handoff, failed_source(), verified=False)
    assert selected['clarification_allowed'] is False
    assert selected['clarifications_remaining'] == (3 if handoff == MIXED else 4)


def test_unknown_handoff_with_verified_source_does_not_grant_or_refill():
    previous = new_contract(4, version=4, limit=20)
    selected = successor_contract(previous, None, failed_source(), verified=True)
    assert selected == new_contract(4, allowed=False, version=4, limit=20)


def test_last_clarification_place_allows_only_unchanged_pending_prefix():
    previous = new_contract(1, version=4, limit=20)
    pending = successor_contract(previous, MIXED, failed_source(), verified=True, pending_clarification=True)
    assert pending == new_contract(0, allowed=False, version=4, continuation=True, limit=20)
    assert MIXED in schema_for(pending)['properties']['status']['enum']
    again = successor_contract(pending, MIXED, failed_source(), verified=True, pending_clarification=True)
    assert again == pending
    rest = successor_contract(again, MIXED, failed_source(), verified=True, pending_clarification=False)
    assert rest == new_contract(0, allowed=False, version=4, limit=20)
    assert MIXED not in schema_for(rest)['properties']['status']['enum']


def test_twentieth_new_clarification_exhausts_the_unchanged_counter():
    previous = new_contract(20, version=4, limit=20)
    for remaining in range(19, -1, -1):
        previous = successor_contract(previous, MIXED, failed_source(), verified=True)
        assert previous == new_contract(remaining, allowed=remaining > 0, version=4, limit=20)
    assert MIXED not in schema_for(previous)['properties']['status']['enum']


@pytest.mark.parametrize('limit', [True, False, 0, 4, 19, 21, 20.0, '20'])
def test_unsupported_clarification_contracts_and_markers_are_rejected(limit):
    with pytest.raises(ValueError):
        capability({**TWENTY, 'clarification_limit': limit})
    value = {**new_contract(0, allowed=False, version=4, limit=20), 'clarification_limit': limit}
    if type(limit) is int and limit > 0:
        assert contract(value) == value  # CONFIG: operator limits are independent of marker versions.
    else:
        with pytest.raises(ControlError):
            contract(value)


class TwentyResetAcceptanceTests(AcceptanceCase):
    def setUp(self):
        marker = patch('codex_control_tests.mixed_support.CAPABILITY', TWENTY)
        marker.start(); self.addCleanup(marker.stop)
        super().setUp()

    def test_explicit_reset_uses_twenty_marker_and_preserves_original_contract(self):
        self.manual(0, reset_capability={**RESET_CAPABILITY, 'clarification_limit': 20})
        self.accept_current(reset_budget=True)
        pending = validate_history(self.ledger())
        self.assertEqual(pending['version'], 2)
        self.assertIs(pending['reset_budget'], True)
        self.adopt(reset_budget=True)
        ledger = self.ledger()
        self.assertEqual(ledger.request_contract(), new_contract(20, version=4, limit=20))
        self.assertEqual(ledger.recorded_contract(self.seed['sha256']), new_contract(0, allowed=False, version=4))
        self.assertIsNone(validate_history(ledger))
        self.assertEqual(active(ledger, self.following['sha256']), pending)
        self.assertEqual(self.codex.calls, 0)

    def test_new_marker_does_not_reset_a_preserving_acceptance(self):
        self.manual(2, reset_capability={**RESET_CAPABILITY, 'clarification_limit': 20})
        self.adopt()
        self.assertEqual(self.ledger().request_contract(), new_contract(2, version=4))
