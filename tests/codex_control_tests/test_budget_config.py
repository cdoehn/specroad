"""Operator policy changes are local and never rewrite issued contracts."""
from contextlib import closing
from dataclasses import replace
from unittest.mock import patch

import pytest

from codex_control_tests.automation_support import AutomationCase
from codex_control_tests.test_start_current import configure_start_case
from specroad_control import budget_config, cli
from specroad_control.config import load, render
from specroad_control.correction_budget import read
from specroad_control.decision_policy import successor_contract
from specroad_control.job_contract import fresh_contract, new_contract, scope
from specroad_control.ledger import Ledger
from specroad_control.local import read_private, write_private
from specroad_control.start_current import enqueue, active_cycle


class BudgetConfigTests(AutomationCase):
    setUp = configure_start_case

    def change(self, **values):
        with patch('specroad_control.ipc.request', return_value={'ok': True}) as ipc:
            result = budget_config.configure(self.paths, **values)
        ipc.assert_called_once_with(self.paths, 'policy-changed')
        return result

    def test_local_read_is_readonly_and_defaults_are_twenty(self):
        before = read_private(self.paths.config)
        with patch('specroad_control.ipc.request', side_effect=AssertionError('read must not wake')):
            value = budget_config.configure(self.paths)
        self.assertEqual(value['effective'], {'clarification_allowed': True, 'clarification_limit': 20, 'correction_limit': 20})
        self.assertEqual(read_private(self.paths.config), before)
        self.assertEqual(self.codex.calls, 0)

    def test_saved_policy_above_twenty_applies_to_a_new_explicit_cycle(self):
        original = self.paths.ledger.read_bytes()
        result = self.change(clarification_allowed=False, clarification_limit=37, correction_limit=41)
        self.assertFalse(result['service_started'])
        self.assertEqual(self.paths.ledger.read_bytes(), original)
        enqueue(self.paths, load(self.paths))
        self.engine.tick()
        with closing(Ledger(self.paths.ledger, scope(self.config))) as ledger:
            self.assertEqual(ledger.request_contract(), new_contract(37, allowed=False, version=4, limit=37))
            self.assertEqual(read(ledger, self.fresh['sha256'])['maximum'], 41)
        self.assertEqual(self.codex.calls, 0)

    def test_invocation_overrides_win_over_file_and_survive_worker_restart(self):
        self.change(clarification_limit=29, correction_limit=31)
        enqueue(self.paths, load(self.paths), overrides={'clarification_limit': 47, 'clarification_allowed': False})
        self.engine.tick()
        value = budget_config.status(self.paths)
        self.assertEqual(value['configured']['clarification_limit'], 29)
        self.assertEqual(value['effective'], {'clarification_allowed': False, 'clarification_limit': 47, 'correction_limit': 31})
        self.assertEqual(active_cycle(self.paths)['overrides'], {'clarification_limit': 47, 'clarification_allowed': False})
        self.engine.close()
        from specroad_control.automation import Engine, Gate
        with Engine(load(self.paths), self.paths, Gate(), core=self.core, codex=self.codex) as restarted:
            restarted.tick()
            self.assertEqual(restarted.config.clarification_limit, 47)
        self.assertEqual(load(self.paths).clarification_limit, 29)

    def test_bound_request_is_not_reinterpreted_by_changed_policy(self):
        enqueue(self.paths, self.config)
        self.engine.tick()
        with closing(Ledger(self.paths.ledger, scope(self.config))) as ledger:
            selected = ledger.request_contract()
        self.change(clarification_allowed=False, clarification_limit=43, correction_limit=53)
        self.engine.tick()
        with closing(Ledger(self.paths.ledger, scope(self.config))) as ledger:
            self.assertEqual(ledger.request_contract(), selected)
            self.assertEqual(read(ledger, self.fresh['sha256'])['maximum'], 20)
        self.assertFalse(self.engine.config.clarification_allowed)
        self.assertEqual(self.codex.calls, 1)

    def test_successful_followup_uses_new_full_limits_but_failure_keeps_old_remainder(self):
        selected = new_contract(6, version=4, limit=20)
        failed = {**self.fresh, 'success': False, 'dirty': True}
        next_request = successor_contract(selected, 'patch_ready', failed, verified=True,
                                          clarification_allowed=False, clarification_limit=44)
        self.assertEqual((next_request['clarification_limit'], next_request['clarifications_remaining']), (20, 6))
        self.assertFalse(next_request['clarification_allowed'])
        success = {**self.fresh, 'success': True, 'dirty': False, 'completed_commit': self.fresh['binding']['base_commit']}
        renewed = successor_contract(selected, 'patch_ready', success, verified=True, clarification_limit=44)
        self.assertEqual(renewed, new_contract(44, version=4, limit=44))

    def test_legacy_project_marker_does_not_gain_configurable_authority(self):
        source = {**self.fresh, 'development_contract': {**self.fresh['development_contract'], 'clarification_limit': 5}}
        self.assertEqual(fresh_contract(source, limit=100), new_contract(5, version=4, limit=5))

    def test_cli_sets_policy_without_deploy_or_start(self):
        with patch('specroad_control.cli.Paths.discover', return_value=self.paths), \
                patch('specroad_control.ipc.request', return_value={'ok': True}), \
                patch('specroad_control.service.start', side_effect=AssertionError('no start')):
            self.assertEqual(cli.main(['config', '--no-clarification', '--clarification-limit', '28', '--correction-limit', '39']), 0)
        self.assertEqual(load(self.paths).correction_limit, 39)
        self.assertFalse(load(self.paths).clarification_allowed)

    def test_start_cli_passes_only_explicit_overrides(self):
        with patch('specroad_control.cli.Paths.discover', return_value=self.paths), \
                patch('specroad_control.service.start', return_value={'queued': True}) as start:
            self.assertEqual(cli.main(['start', '--from-current', '--clarification-limit', '52']), 0)
        start.assert_called_once_with(self.paths, from_current=True, overrides={'clarification_limit': 52})


@pytest.mark.parametrize('args', [
    ['start', '--correction-limit', '30'], ['resume', '--clarification-limit', '30'],
    ['config', '--thread-id', 'forbidden'], ['status', '--no-clarification'],
])
def test_policy_options_cannot_silently_change_unrelated_commands(args):
    with pytest.raises(SystemExit):
        cli.main(args)
