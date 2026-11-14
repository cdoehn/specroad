"""Operator restarts use actual checkpoints, never prior runtime provenance."""
from contextlib import closing
from dataclasses import dataclass, replace
import json
from pathlib import Path
from types import SimpleNamespace, ModuleType
from unittest.mock import Mock, patch

import pytest

from codex_control_tests.automation_support import AutomationCase, FakeCore, FakeCodex
from specroad_control.automation import Engine, Gate
from specroad_control import cli, service, ph_checkpoint
from specroad_control.config import render
from specroad_control.correction_budget import bind, read
from specroad_control.errors import ControlError
from specroad_control.job_contract import new_contract, scope
from specroad_control.ledger import Ledger
from specroad_control.local import json_read, json_write, write_private
from specroad_control.mixed_contract import CAPABILITY
from specroad_control.start_current import ACTIVE, REQUEST, active_cycle, enqueue, pending


def configure_start_case(self):
    AutomationCase.setUp(self)
    self.config = replace(self.config, clarification_allowed=True, correction_limit=20)
    write_private(self.paths.config, render(self.config).encode())
    self.fresh = self.result('current.zip', dirty=True,
        binding={**self.binding, 'state_fingerprint': 'c' * 16},
        development_contract={**CAPABILITY, 'clarification_limit': 20})
    self.core = FakeCore()
    self.core.checkpoint = Mock(return_value=self.fresh)
    self.core.call = Mock(side_effect=lambda _operation, _path: {
        'sha256': self.fresh['sha256'], 'binding': self.fresh['binding'],
        'repository_path': self.fresh['repository_path'], 'dirty': self.fresh['dirty']})
    self.codex = FakeCodex(self, 'no_work')
    self.codex.activity = Mock(return_value='idle')
    self.engine = Engine(self.config, self.paths, Gate(), core=self.core, codex=self.codex)
    self.addCleanup(self.engine.close)


class StartCurrentTests(AutomationCase):
    setUp = configure_start_case

    def request(self):
        return enqueue(self.paths, self.config)

    def test_exhausted_old_budget_does_not_block_a_fresh_dirty_checkpoint(self):
        old_path = self.paths.ledger
        old_path.unlink()  # Isolated fixture: construct an actually exhausted repair cycle.
        previous = self.result('old-failure.zip', operation='apply', success=False, dirty=True,
                               primary_kind='entrypoint_exit', entrypoint_started=True)
        with closing(Ledger(old_path, scope(self.config), initial=previous)) as ledger:
            ledger.bind_contract(new_contract(0, allowed=False, version=4))
            bind(ledger, previous, 5)
            for number in range(5):
                patch_sha = format(number + 1, '064x')
                ledger.change('waiting_result', patch_sha=patch_sha, output_kind='patch_ready')
                following = self.result(f'old-repair-{number}.zip', previous=previous, patch_sha=patch_sha,
                    success=False, dirty=True, primary_kind='entrypoint_exit')
                ledger.enqueue(following, decision_evidence={'verified': True}, correction_limit=5)
                previous = following
            self.assertEqual(read(ledger, previous['sha256'])['remaining'], 0)
        old_bytes = old_path.read_bytes()
        marker = self.dev / 'unfinished.txt'
        marker.write_bytes(b'uncommitted work\x00')
        self.request()
        self.assertTrue(self.engine.tick()['again'])
        self.assertNotEqual(self.paths.ledger, old_path)
        with closing(Ledger(self.paths.ledger, scope(self.config))) as ledger:
            self.assertEqual(ledger.current()['source'], self.fresh)
            self.assertEqual(ledger.request_contract(), new_contract(20, version=4, limit=20))
            budget = read(ledger, self.fresh['sha256'])
            self.assertEqual((budget['maximum'], budget['remaining'], budget['active']), (20, 20, False))
        self.assertEqual(old_path.read_bytes(), old_bytes)
        self.assertEqual(marker.read_bytes(), b'uncommitted work\x00')
        self.assertIsNone(pending(self.paths))
        self.assertEqual(self.codex.calls, 0)  # Activation itself is not a Dev dispatch.

    def test_corrupt_old_ledger_is_not_needed_for_explicit_start(self):
        old = self.paths.ledger
        write_private(old, b'not a database')
        self.request()
        self.engine.tick()
        self.assertEqual(old.read_bytes(), b'not a database')
        with closing(Ledger(self.paths.ledger, scope(self.config))) as ledger:
            self.assertEqual(ledger.current()['sha'], self.fresh['sha256'])

    def test_without_explicit_request_invalid_history_is_not_silently_reset(self):
        write_private(self.paths.ledger, b'broken')
        with self.assertRaises(ControlError):
            self.engine.tick()
        self.core.checkpoint.assert_not_called()
        self.assertIsNone(active_cycle(self.paths))

    def test_active_dev_and_busy_apply_wait_without_opening_or_replacing_old_state(self):
        old = self.paths.ledger.read_bytes()
        request = self.request()
        self.codex.activity.return_value = 'active'
        self.assertIn('retry_after', self.engine.tick())
        self.core.checkpoint.assert_not_called()
        self.codex.activity.return_value = 'idle'
        self.core.checkpoint.side_effect = ControlError('repository_busy', 'test lock held')
        self.assertIn('retry_after', self.engine.tick())
        self.assertEqual(pending(self.paths), request)
        self.assertEqual(self.paths.ledger.read_bytes(), old)
        self.core.checkpoint.side_effect = None
        self.engine.tick()
        self.assertIsNotNone(active_cycle(self.paths))

    def test_duplicate_pending_request_and_interruption_after_publication_do_not_refill(self):
        request = self.request()
        self.assertEqual(self.request(), request)
        self.engine.tick()
        target = self.paths.ledger
        with closing(Ledger(target, scope(self.config))) as ledger:
            ledger.db.execute('UPDATE clarification_budgets SET remaining=19')
        json_write(self.paths.state / REQUEST, request)
        self.engine.tick()
        self.assertEqual(self.paths.ledger, target)
        self.assertEqual(self.core.checkpoint.call_count, 1)
        with closing(Ledger(target, scope(self.config))) as ledger:
            self.assertEqual(ledger.request_contract()['clarifications_remaining'], 19)

    def test_pause_during_capture_preserves_pending_request_for_later_resume(self):
        def capture():
            self.engine.gate.set(False)
            return self.fresh
        self.core.checkpoint.side_effect = capture
        self.request()
        self.engine.tick()
        self.assertIsNone(active_cycle(self.paths))
        self.assertIsNotNone(pending(self.paths))
        self.core.checkpoint.side_effect = None
        self.engine.gate.set(True)
        self.engine.tick()
        self.assertIsNotNone(active_cycle(self.paths))

    def test_configured_opt_out_and_correction_limit_are_used_for_new_cycle(self):
        self.engine.config = replace(self.config, clarification_allowed=False, correction_limit=7)
        write_private(self.paths.config, render(self.engine.config).encode())
        enqueue(self.paths, self.engine.config)
        self.engine.tick()
        with closing(Ledger(self.paths.ledger, scope(self.engine.config))) as ledger:
            self.assertFalse(ledger.request_contract()['clarification_allowed'])
            self.assertEqual(read(ledger, self.fresh['sha256'])['remaining'], 7)

    def test_wrong_apply_identity_never_activates_checkpoint(self):
        self.core.checkpoint.return_value = {**self.fresh, 'repository_path': str(self.dev)}
        self.request()
        with self.assertRaises(ControlError):
            self.engine.tick()
        self.assertIsNone(active_cycle(self.paths))

    def test_current_tree_changed_after_capture_never_activates_checkpoint(self):
        self.core.call.return_value = None
        self.core.call.side_effect = lambda *_args: {**self.fresh, 'dirty': False}
        self.request()
        with self.assertRaises(ControlError):
            self.engine.tick()
        self.assertIsNone(active_cycle(self.paths))

    def test_invalid_old_runtime_pointer_can_be_replaced_by_explicit_start(self):
        json_write(self.paths.state / ACTIVE, {'obsolete': True})
        self.request()
        self.engine.tick()
        self.assertEqual(active_cycle(self.paths)['source_sha256'], self.fresh['sha256'])

    def test_existing_readers_keep_the_old_database_while_current_reader_changes(self):
        with closing(Ledger(self.paths.ledger, scope(self.config))) as previous:
            self.request()
            self.engine.tick()
            self.assertEqual(previous.current()['sha'], self.seed['sha256'])
            with closing(Ledger(self.paths.ledger, scope(self.config))) as current:
                self.assertEqual(current.current()['sha'], self.fresh['sha256'])

    def test_start_service_queues_without_reading_history_or_capturing_in_cli(self):
        write_private(self.paths.ledger, b'old invalid database')
        with patch.object(service, 'verify_owned', return_value={'ActiveState': 'active'}), \
                patch.object(service, 'unit_text', return_value='owned unit'), \
                patch.object(service, 'read_private', return_value=b'owned unit'), \
                patch.object(service, 'checked') as manager, \
                patch('specroad_control.ipc.request') as ipc, \
                patch('specroad_control.handover_queue.startup', side_effect=AssertionError('old history')):
            result = service.start(self.paths, from_current=True)
        self.assertTrue(result['queued'])
        self.assertIsNotNone(pending(self.paths))
        self.core.checkpoint.assert_not_called()
        manager.assert_called_once_with(['start', self.paths.unit.name])
        ipc.assert_called_once_with(self.paths, 'resume')

    def test_native_capture_is_rechecked_when_dev_becomes_active_before_activation(self):
        self.codex.activity.side_effect = ['idle', 'active']
        self.request()
        self.assertIn('retry_after', self.engine.tick())
        self.assertIsNone(active_cycle(self.paths))
        self.assertIsNotNone(pending(self.paths))

    def test_next_tick_dispatches_once_from_the_new_checkpoint(self):
        self.request()
        self.engine.tick()
        self.assertTrue(self.engine.tick()['halted'])
        self.assertEqual(self.codex.calls, 1)
        with closing(Ledger(self.paths.ledger, scope(self.config))) as ledger:
            self.assertEqual(ledger.current()['stage'], 'no_work')
            self.assertEqual(ledger.current()['sha'], self.fresh['sha256'])


def test_cli_start_current_is_explicit_and_only_available_on_start():
    with patch('specroad_control.cli.Paths.discover') as discover, patch.object(service, 'start') as start:
        discover.return_value.instance = 'fixture'
        start.return_value = {'start_requested': True, 'queued': True}
        assert cli.main(['start', '--from-current']) == 0
        start.assert_called_once_with(discover.return_value, from_current=True)
    with pytest.raises(SystemExit):
        cli.main(['status', '--from-current'])


@dataclass(frozen=True)
class RepositoryPathValue:
    """API contract double: a value object, not an os.PathLike or a string."""
    value: Path

    def __str__(self):
        return str(self.value)


@pytest.fixture
def checkpoint_api(monkeypatch):
    # The adapter uses API contract doubles; installed-service integration is
    # a separate acceptance. RepositoryPath intentionally has no __fspath__.
    modules = {name: ModuleType(name) for name in ('patchharbor', 'patchharbor.api', 'patchharbor.errors')}
    modules['patchharbor'].api = api = modules['patchharbor.api']
    class NativeError(Exception):
        pass
    modules['patchharbor.errors'].PatchHarborError = NativeError
    modules['patchharbor.errors'].FailureReason = SimpleNamespace(REPOSITORY_BUSY='busy')
    for name, module in modules.items():
        monkeypatch.setitem(__import__('sys').modules, name, module)
    api.context = Mock()
    api.bundle = Mock()
    return api


@pytest.mark.parametrize('foreign', [False, True])
def test_native_checkpoint_checks_identity_and_uses_native_snapshot(checkpoint_api, capsys, tmp_path, foreign):
    api = checkpoint_api
    repository, exchange = tmp_path / 'apply', tmp_path / 'exchange'
    repository.mkdir(); exchange.mkdir()
    work = repository / 'uncommitted.py'; work.write_bytes(b'original bytes\n')
    context = SimpleNamespace(repo_id='foreign' if foreign else 'expected',
                              repository_path=RepositoryPathValue(repository))
    api.context.return_value = context
    api.bundle.return_value = SimpleNamespace(context=context, path=exchange / 'checkpoint.zip',
        report=SimpleNamespace(primary_result=SimpleNamespace(success=True)))
    assert ph_checkpoint.main([str(repository), 'expected', str(exchange)]) == int(foreign)
    reply = json.loads(capsys.readouterr().out)
    assert reply['ok'] is not foreign
    assert work.read_bytes() == b'original bytes\n'
    if foreign:
        api.bundle.assert_not_called()
    else:
        api.bundle.assert_called_once_with(repository, output_directory=exchange)
        assert reply['path'] == str(exchange / 'checkpoint.zip')


def test_native_checkpoint_rejects_foreign_path_value_before_capture(checkpoint_api, capsys, tmp_path):
    repository, other = tmp_path / 'apply', tmp_path / 'other'
    repository.mkdir(); other.mkdir()
    marker = other / 'untouched.txt'; marker.write_bytes(b'foreign work\n')
    checkpoint_api.context.return_value = SimpleNamespace(
        repo_id='expected', repository_path=RepositoryPathValue(other))
    assert ph_checkpoint.main([str(repository), 'expected', str(tmp_path / 'exchange')]) == 1
    assert json.loads(capsys.readouterr().out) == {'ok': False, 'error': 'checkpoint_failed'}
    checkpoint_api.bundle.assert_not_called()
    assert marker.read_bytes() == b'foreign work\n'
