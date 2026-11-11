from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from specroad_control.config import Config
from specroad_control.exchange import Exchange
from specroad_control.current_acceptance_proof import checked
from codex_control_tests.automation_support import FakeCore, package
from codex_control_tests.current_acceptance_support import AcceptanceCase


class ExactAcceptanceTests(AcceptanceCase):
    def test_unrelated_history_is_not_natively_validated_before_acceptance(self):
        self.manual()
        active_commits = {self.binding['base_commit'], self.following['binding']['base_commit']}
        for number in range(300):
            historical_commit = 'f' + format(number, '039x')
            self.assertNotIn(historical_commit, active_commits)
            package(self.exchange / ('old-%04d.zip' % number),
                    {'kind': 'patch', 'binding': dict(self.binding, base_commit=historical_commit)})
        with patch.object(self.engine.core, 'patch', wraps=self.engine.core.patch) as calls:
            proof = checked(self.engine, self.following)
        self.assertEqual(proof['result']['sha256'], self.following['sha256'])
        self.assertGreater(calls.call_count, 0)
        assert all(not Path(call.args[0]).name.startswith('old-') for call in calls.call_args_list)


def test_repeated_relevant_discovery_reuses_validation_and_reports_progress(tmp_path):
    binding = dict(repo_id=str(uuid4()), base_commit='a'*40, state_fingerprint='b'*16,
                   fingerprint_algorithm='patchharbor-state-v1')
    config = Config(tmp_path/'dev', tmp_path, str(uuid4()), repo_id=binding['repo_id'])
    package(tmp_path/'selected.zip', dict(kind='patch', binding=binding))
    core = FakeCore(); events = []; exchange = Exchange(config, core, observe=lambda **v: events.append(v))
    with patch.object(core, 'patch', wraps=core.patch) as calls:
        first = list(exchange.candidates('patch', lambda m: m['base_commit']=='a'*40))
        second = list(exchange.candidates('patch', lambda m: m['base_commit']=='a'*40))
    assert first == second and calls.call_count == 1
    assert events[-1]['validation']['phase'] == 'complete'
    assert events[-1]['validation']['cache_hits'] == 1
