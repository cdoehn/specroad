"""User activity during slow evidence checks must not become a claimed turn."""
from dataclasses import replace
import json
from unittest.mock import patch

import pytest

from specroad_control.automation import Engine, Gate, scope
from specroad_control.codex import Codex
from specroad_control.codex_proxy import Proxy
from specroad_control.errors import ControlError
from specroad_control.ledger import Ledger
from specroad_control.telemetry import record
from codex_control_tests.automation_support import AutomationCase, FakeCore, FakeCodex


class DispatchBoundaryTests(AutomationCase):
    def engine(self, transport='app-server-proxy', codex=None):
        config = replace(self.config, transport=transport)
        engine = Engine(config, self.paths, Gate(), core=FakeCore(), codex=codex or Codex(config))
        self.addCleanup(engine.close)
        return engine

    def current(self):
        ledger = Ledger(self.paths.state / 'automation.sqlite3', scope(self.config))
        try:
            return ledger.current()
        finally:
            ledger.close()

    def busy_during_proof(self, transport):
        engine = self.engine(transport)
        from specroad_control.current_acceptance import guard_dispatch

        def proof(*args):
            guard_dispatch(*args)
            self.settings(thread_status='active')

        with patch('specroad_control.current_acceptance.guard_dispatch', side_effect=proof) as checked:
            result = engine.tick()
        self.assertEqual(checked.call_count, 1)
        self.assertEqual(result, {'halted': False, 'again': False, 'retry_after': 30})
        self.assertEqual(self.current()['stage'], 'ready')
        self.assertIsNone(self.current()['error'])
        self.assertEqual(engine.summary()['thread_status'], 'active')
        self.assertFalse((self.codex_home / 'calls.jsonl').exists())
        directory = self.paths.state / 'jobs' / self.seed['sha256']
        original = (directory / 'attempt.json').read_bytes()
        self.assertEqual({p.name for p in directory.iterdir()}, {'attempt.json'})
        self.settings(mode='no_work')
        self.assertTrue(engine.tick()['halted'])
        self.assertEqual(self.current()['stage'], 'no_work')
        self.assertEqual((directory / 'attempt.json').read_bytes(), original)
        self.assertEqual(len((self.codex_home / 'calls.jsonl').read_text().splitlines()), 1)
        engine.tick()
        self.assertEqual(len((self.codex_home / 'calls.jsonl').read_text().splitlines()), 1)

    def test_proxy_waits_for_late_user_turn_and_dispatches_once_after_idle(self):
        self.busy_during_proof('app-server-proxy')

    def test_exec_waits_for_late_user_turn_and_dispatches_once_after_idle(self):
        self.busy_during_proof('exec')

    def test_unknown_late_activity_still_halts_without_dispatch(self):
        engine = self.engine()
        with patch('specroad_control.current_acceptance.guard_dispatch',
                   side_effect=lambda *args: self.settings(thread_status='unknown')):
            self.assertTrue(engine.tick()['halted'])
        self.assertEqual(self.current()['stage'], 'ready')
        self.assertEqual(self.current()['error'], 'dev_thread_busy')
        self.assertFalse((self.codex_home / 'calls.jsonl').exists())

    def test_late_wrong_thread_directory_still_halts(self):
        engine = self.engine()
        with patch('specroad_control.current_acceptance.guard_dispatch',
                   side_effect=lambda *args: self.settings(cwd=str(self.home))):
            self.assertTrue(engine.tick()['halted'])
        self.assertEqual(self.current()['error'], 'wrong_thread_repository')
        self.assertFalse((self.codex_home / 'calls.jsonl').exists())

    def test_invalid_apply_evidence_still_prevents_dispatch(self):
        engine = self.engine()
        with patch('specroad_control.current_acceptance.guard_dispatch',
                   side_effect=ControlError('current_acceptance_rejected', 'changed proof')):
            self.assertTrue(engine.tick()['halted'])
        self.assertEqual(self.current()['error'], 'current_acceptance_rejected')
        self.assertFalse((self.codex_home / 'calls.jsonl').exists())

    def test_busy_error_after_durable_claim_is_never_replayed(self):
        codex = FakeCodex(self)

        def run(prompt, schema, directory, *, authorize):
            assert authorize()
            codex.calls += 1
            raise ControlError('dev_thread_busy', 'unknown outcome', details={'thread_status': 'active'})

        codex.run = run
        engine = self.engine(codex=codex)
        self.assertTrue(engine.tick()['halted'])
        self.assertEqual(self.current()['stage'], 'uncertain')
        self.assertTrue(engine.tick()['halted'])
        self.assertEqual(codex.calls, 1)

    def test_pause_during_final_metadata_check_prevents_claim(self):
        engine = self.engine()
        check = engine.codex.check

        def pause():
            # This must remain outside Gate's mutex so pause is responsive.
            engine.gate.set(False)
            return check()

        with patch.object(engine.codex, 'check', side_effect=pause):
            self.assertFalse(engine.tick()['halted'])
        self.assertEqual(self.current()['stage'], 'ready')
        self.assertFalse((self.codex_home / 'calls.jsonl').exists())


@pytest.mark.parametrize('rpc_code,expected', [(-32600, -32600), (True, None), ('private text', None)])
def test_rpc_rejection_logs_only_method_and_numeric_code(rpc_code, expected, capsys):
    proxy = Proxy.__new__(Proxy)
    proxy.sequence = 0
    proxy.send = lambda document: None
    proxy.read = lambda timeout: {'id': 1, 'error': {'code': rpc_code, 'message': 'private server prose'}}
    with pytest.raises(ControlError) as caught:
        proxy.call('turn/start', {})
    assert caught.value.code == 'codex_request_rejected'
    assert caught.value.details == {'rpc_method': 'turn/start', 'rpc_code': expected}
    record('automation_error', error=caught.value.code, **caught.value.details)
    raw = capsys.readouterr().err
    entry = json.loads(raw)
    assert entry['rpc_method'] == 'turn/start'
    assert entry['rpc_code'] == expected
    assert 'private' not in raw
