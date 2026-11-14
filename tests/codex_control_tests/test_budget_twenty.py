"""New budget policy through isolated native-container and ledger boundaries."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

from specroad_control.config import parse, render
from specroad_control.correction_budget import bind, read
from specroad_control.current_acceptance_history import validate_history
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
