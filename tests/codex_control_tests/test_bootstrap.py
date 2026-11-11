"""Bootstrap state contracts; all paths, identities and processes are isolated."""
from dataclasses import replace
import json
from pathlib import Path
from specroad_control.toml_compat import tomllib
from unittest.mock import patch
from uuid import uuid4
from specroad_control.automation import Engine, Gate, scope
from specroad_control.commands import configure, check
from specroad_control.config import load, render
from specroad_control.errors import ControlError
from specroad_control.ledger import Ledger
from specroad_control.local import write_private
from codex_control_tests.automation_support import AutomationCase, FakeCore, FakeCodex, package


class BootstrapTests(AutomationCase):
    def history(self):
        return Ledger(self.paths.state / 'automation.sqlite3', scope(self.config))

    def fresh(self):
        # This removes only the pristine, never-dispatched test fixture.
        (self.paths.state / 'automation.sqlite3').unlink()
        write_private(self.paths.config, render(replace(self.config, enabled=False, repo_id='', session_id='')).encode())

    def setup_source(self, result=None):
        return configure(self.paths, thread_id=self.thread, result=result,
                         codex=str(self.binary), core_python=str(self.python))

    def engine(self, mode='patch'):
        codex = FakeCodex(self, mode)
        engine = Engine(self.config, self.paths, Gate(), core=FakeCore(), codex=codex)
        self.addCleanup(engine.close)
        return engine, codex

    def row(self):
        ledger = self.history()
        try:
            return ledger.current()
        finally:
            ledger.close()

    def test_first_setup_places_result_only_in_runtime_state(self):
        self.fresh()
        reply = self.setup_source(self.seed['path'])
        doc = tomllib.loads(self.paths.config.read_text())
        self.assertEqual(set(doc['automation']), {'enabled', 'settle_seconds', 'retry_delays_seconds', 'start_delay_seconds', 'clarification_allowed', 'correction_limit'})
        self.assertEqual(load(self.paths).start_delay_seconds, self.config.start_delay_seconds)
        self.assertEqual(load(self.paths).clarification_allowed, self.config.clarification_allowed)
        self.assertEqual(load(self.paths).correction_limit, self.config.correction_limit)
        self.assertNotIn(self.seed['path'], self.paths.config.read_text())
        self.assertNotIn(self.seed['sha256'], self.paths.config.read_text())
        self.assertEqual(self.row()['source']['sha256'], self.seed['sha256'])
        self.assertEqual(self.row()['stage'], 'ready')
        self.assertTrue(reply['bootstrap_created'])
        self.assertFalse(reply['service_started'])
        self.assertFalse(reply['model_called'])
        self.assertFalse((self.codex_home / 'calls.jsonl').exists())

    def test_configure_without_result_reuses_current_state(self):
        before = self.row()
        reply = self.setup_source()
        self.assertFalse(reply['bootstrap_created'])
        self.assertEqual(self.row(), before)

    def test_missing_state_requires_explicit_initial_result(self):
        self.fresh()
        before = self.paths.config.read_bytes()
        with self.assertRaises(ControlError) as caught:
            self.setup_source()
        self.assertEqual(caught.exception.code, 'state_not_initialized')
        self.assertEqual(self.paths.config.read_bytes(), before)
        self.assertFalse((self.paths.state / 'automation.sqlite3').exists())

    def test_worker_never_guesses_seed_when_state_is_missing(self):
        (self.paths.state / 'automation.sqlite3').unlink()
        engine, codex = self.engine()
        with self.assertRaises(ControlError) as caught:
            engine.tick()
        self.assertEqual(caught.exception.code, 'state_not_initialized')
        self.assertEqual(codex.calls, 0)
        self.assertFalse((self.paths.state / 'automation.sqlite3').exists())

    def test_check_does_not_initialize_runtime_state(self):
        (self.paths.state / 'automation.sqlite3').unlink()
        with self.assertRaises(ControlError):
            check(self.paths)
        self.assertFalse((self.paths.state / 'automation.sqlite3').exists())
        self.assertFalse((self.codex_home / 'calls.jsonl').exists())

    def test_followup_changes_state_without_rewriting_configuration(self):
        before = self.paths.config.read_bytes()
        engine, codex = self.engine()
        engine.tick()
        output = engine.exchange.patches(self.seed)[0]
        following = self.result('following.zip', previous=self.seed, patch_sha=output['sha256'])
        engine.tick()
        self.assertEqual(self.row()['sha'], following['sha256'])
        self.assertEqual(self.paths.config.read_bytes(), before)
        self.assertEqual(codex.calls, 2)

    def test_restart_after_followup_does_not_need_original_seed_file(self):
        engine, codex = self.engine()
        engine.tick()
        output = engine.exchange.patches(self.seed)[0]
        self.result('following.zip', previous=self.seed, patch_sha=output['sha256'])
        engine.tick()
        engine.close()
        Path(self.seed['path']).unlink()
        with Engine(self.config, self.paths, Gate(), core=FakeCore(), codex=codex) as restarted:
            self.assertFalse(restarted.tick()['again'])
        self.assertTrue(check(self.paths)['core_validated'])
        self.assertEqual(codex.calls, 2)

    def test_repeated_initial_result_does_not_rewind_advanced_state(self):
        engine, _codex = self.engine()
        engine.tick()
        output = engine.exchange.patches(self.seed)[0]
        self.result('following.zip', previous=self.seed, patch_sha=output['sha256'])
        engine.tick()
        engine.close()
        before = self.row()
        self.setup_source(self.seed['path'])
        self.assertEqual(self.row(), before)

    def test_different_initial_result_cannot_replace_existing_state(self):
        other = self.result('another.zip')
        before, config = self.row(), self.paths.config.read_bytes()
        with self.assertRaises(ControlError) as caught:
            self.setup_source(other['path'])
        self.assertEqual(caught.exception.code, 'bootstrap_conflict')
        self.assertEqual(self.row(), before)
        self.assertEqual(self.paths.config.read_bytes(), config)

    def test_retargeting_thread_does_not_reuse_history(self):
        before = self.row()
        with self.assertRaises(ControlError) as caught:
            configure(self.paths, thread_id=str(uuid4()), result=self.seed['path'])
        self.assertEqual(caught.exception.code, 'ledger_scope_mismatch')
        self.assertEqual(self.row(), before)

    def test_changed_approved_result_is_not_reapproved_silently(self):
        package(Path(self.seed['path']), {**self.seed, 'different': True})
        with self.assertRaises(ControlError) as caught:
            self.setup_source(self.seed['path'])
        self.assertEqual(caught.exception.code, 'bootstrap_conflict')

    def test_corrupt_history_is_preserved_during_configure(self):
        path = self.paths.state / 'automation.sqlite3'
        path.write_bytes(b'not a database')
        with self.assertRaises(ControlError) as caught:
            self.setup_source(self.seed['path'])
        self.assertEqual(caught.exception.code, 'invalid_ledger')
        self.assertEqual(path.read_bytes(), b'not a database')

    def test_no_work_remains_terminal_after_reconfiguration(self):
        engine, codex = self.engine('no_work')
        engine.tick()
        engine.close()
        self.setup_source(self.seed['path'])
        with Engine(self.config, self.paths, Gate(), core=FakeCore(), codex=codex) as restarted:
            self.assertTrue(restarted.tick()['halted'])
        self.assertEqual(codex.calls, 1)

    def test_runtime_state_is_private_and_outside_repository(self):
        path = self.paths.state / 'automation.sqlite3'
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
        self.assertNotIn(self.dev, path.parents)
        self.assertNotIn(self.exchange, path.parents)

    def test_blank_legacy_install_config_is_still_readable(self):
        data = self.paths.config.read_text() + 'seed_result = ""\nseed_sha256 = ""\n'
        write_private(self.paths.config, data.encode())
        self.assertTrue(load(self.paths).enabled)
        self.setup_source()
        self.assertEqual(set(tomllib.loads(self.paths.config.read_text())['automation']), {'enabled', 'settle_seconds', 'retry_delays_seconds', 'start_delay_seconds', 'clarification_allowed', 'correction_limit'})
        self.assertEqual(load(self.paths).start_delay_seconds, self.config.start_delay_seconds)
        self.assertEqual(load(self.paths).clarification_allowed, self.config.clarification_allowed)
        self.assertEqual(load(self.paths).correction_limit, self.config.correction_limit)

    def test_nonempty_legacy_seed_requires_explicit_migration(self):
        data = self.paths.config.read_text() + '\nseed_result = ' + json.dumps(self.seed['path']) + '\nseed_sha256 = ' + json.dumps(self.seed['sha256']) + '\n'
        write_private(self.paths.config, data.encode())
        before = self.paths.config.read_bytes()
        with self.assertRaises(ControlError) as caught:
            load(self.paths)
        self.assertEqual(caught.exception.code, 'seed_migration_required')
        self.assertEqual(self.paths.config.read_bytes(), before)

    def test_interrupted_config_publication_keeps_initialized_state(self):
        self.fresh()
        with patch('specroad_control.commands.write_private', side_effect=OSError('injected config write failure')):
            with self.assertRaises(OSError):
                self.setup_source(self.seed['path'])
        self.assertFalse(load(self.paths).enabled)
        before = self.row()
        self.setup_source(self.seed['path'])
        self.assertEqual(self.row(), before)
        self.assertTrue(load(self.paths).enabled)
        self.assertFalse((self.codex_home / 'calls.jsonl').exists())

    def test_busy_thread_cannot_publish_bootstrap_or_config(self):
        self.fresh()
        self.settings(thread_status='active')
        before = self.paths.config.read_bytes()
        with self.assertRaises(ControlError):
            self.setup_source(self.seed['path'])
        self.assertEqual(self.paths.config.read_bytes(), before)
        self.assertFalse((self.paths.state / 'automation.sqlite3').exists())

    def test_archive_before_first_turn_is_resolved_from_state(self):
        directory = self.exchange / 'PatchHarbor-Archive'
        directory.mkdir()
        Path(self.seed['path']).rename(directory / 'renamed.zip')
        self.setup_source()
        self.assertTrue(check(self.paths)['core_validated'])

    def test_unscanned_nested_result_cannot_seed_worker(self):
        directory = self.exchange / 'unscanned'
        directory.mkdir()
        nested = Path(self.seed['path']).rename(directory / 'nested.zip')
        with self.assertRaises(ControlError) as caught:
            self.setup_source(str(nested))
        self.assertEqual(caught.exception.code, 'invalid_seed')
