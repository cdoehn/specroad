"""Legacy setup and crash safety; never reset dispatched work."""
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
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


class BootstrapMigrationTests(AutomationCase):
    def history(self):
        return Ledger(self.paths.state / 'automation.sqlite3', scope(self.config))

    def row(self):
        ledger = self.history()
        try:
            return ledger.current()
        finally:
            ledger.close()

    def legacy(self, *, sha=None, path=None):
        text = render(self.config) + '\nseed_result = ' + json.dumps(path or self.seed['path'])
        text += '\nseed_sha256 = ' + json.dumps(sha or self.seed['sha256']) + '\n'
        write_private(self.paths.config, text.encode())

    def setup_source(self, result=None):
        return configure(self.paths, thread_id=self.thread, result=result,
                         codex=str(self.binary), core_python=str(self.python))

    def remove_pristine_history(self):
        # Only an isolated, never-dispatched test fixture is removed here.
        (self.paths.state / 'automation.sqlite3').unlink()

    def assert_clean_config(self):
        doc = tomllib.loads(self.paths.config.read_text())
        self.assertEqual(set(doc['automation']), {'enabled', 'settle_seconds', 'retry_delays_seconds', 'start_delay_seconds', 'clarification_allowed', 'correction_limit'})
        self.assertEqual(load(self.paths).start_delay_seconds, self.config.start_delay_seconds)
        self.assertEqual(load(self.paths).clarification_allowed, self.config.clarification_allowed)
        self.assertEqual(load(self.paths).correction_limit, self.config.correction_limit)
        self.assertTrue(doc['automation']['enabled'])
        self.assertFalse((self.codex_home / 'calls.jsonl').exists())

    def test_explicit_migration_preserves_ready_job(self):
        self.config = replace(self.config, start_delay_seconds=12.5,
                              clarification_allowed=False, correction_limit=2)
        self.legacy()
        before = self.row()
        reply = self.setup_source()
        self.assertTrue(reply['legacy_seed_migrated'])
        self.assertFalse(reply['bootstrap_created'])
        self.assertEqual(self.row(), before)
        self.assert_clean_config()

    def test_explicit_migration_preserves_running_job(self):
        ledger = self.history()
        ledger.change('running')
        ledger.close()
        self.legacy()
        before = self.row()
        self.setup_source()
        self.assertEqual(self.row(), before)
        with Engine(self.config, self.paths, Gate(), core=FakeCore(), codex=FakeCodex(self)) as engine:
            self.assertTrue(engine.tick()['halted'])
            self.assertEqual(engine.codex.calls, 0)
        self.assert_clean_config()

    def test_explicit_migration_preserves_uncertain_job(self):
        ledger = self.history()
        ledger.change('running')
        ledger.change('uncertain', error='connection_lost')
        ledger.close()
        self.legacy()
        before = self.row()
        self.setup_source(self.seed['path'])
        self.assertEqual(self.row(), before)
        self.assert_clean_config()

    def test_explicit_migration_preserves_waiting_result(self):
        with Engine(self.config, self.paths, Gate(), core=FakeCore(), codex=FakeCodex(self)) as engine:
            engine.tick()
        self.legacy()
        before = self.row()
        self.setup_source()
        self.assertEqual(self.row(), before)
        self.assertEqual(before['stage'], 'waiting_result')
        self.assert_clean_config()

    def test_explicit_migration_preserves_finished_work(self):
        with Engine(self.config, self.paths, Gate(), core=FakeCore(), codex=FakeCodex(self, 'no_work')) as engine:
            engine.tick()
        self.legacy()
        before = self.row()
        self.setup_source()
        self.assertEqual(self.row(), before)
        self.assertEqual(before['stage'], 'no_work')

    def test_migration_with_history_needs_no_original_result(self):
        self.legacy()
        Path(self.seed['path']).unlink()
        before = self.row()
        self.setup_source()
        self.assertEqual(self.row(), before)
        self.assert_clean_config()

    def test_migration_preserves_followup_even_when_original_removed(self):
        with Engine(self.config, self.paths, Gate(), core=FakeCore(), codex=FakeCodex(self)) as engine:
            engine.tick()
            output = engine.exchange.patches(self.seed)[0]
            following = self.result('following.zip', previous=self.seed, patch_sha=output['sha256'])
            engine.tick()
        self.legacy()
        Path(self.seed['path']).unlink()
        self.setup_source()
        self.assertEqual(self.row()['sha'], following['sha256'])
        self.assertTrue(check(self.paths)['core_validated'])

    def test_migration_without_history_uses_only_approved_seed(self):
        self.remove_pristine_history()
        self.legacy()
        reply = self.setup_source()
        self.assertTrue(reply['bootstrap_created'])
        self.assertEqual(self.row()['sha'], self.seed['sha256'])
        self.assert_clean_config()

    def test_migration_locates_exact_archived_seed_without_history(self):
        self.remove_pristine_history()
        self.legacy()
        archive = self.exchange / 'PatchHarbor-Archive'
        archive.mkdir()
        Path(self.seed['path']).rename(archive / 'renamed.zip')
        self.setup_source()
        self.assertEqual(self.row()['sha'], self.seed['sha256'])
        self.assert_clean_config()

    def test_migration_missing_approved_seed_does_not_choose_another(self):
        self.remove_pristine_history()
        self.legacy()
        Path(self.seed['path']).unlink()
        self.result('newer.zip')
        before = self.paths.config.read_bytes()
        with self.assertRaises(ControlError) as caught:
            self.setup_source()
        self.assertEqual(caught.exception.code, 'source_result_missing')
        self.assertEqual(self.paths.config.read_bytes(), before)
        self.assertFalse((self.paths.state / 'automation.sqlite3').exists())

    def test_legacy_hash_disagreement_preserves_config_and_history(self):
        self.legacy(sha='0' * 64)
        before, doc = self.row(), self.paths.config.read_bytes()
        with self.assertRaises(ControlError) as caught:
            self.setup_source()
        self.assertEqual(caught.exception.code, 'bootstrap_conflict')
        self.assertEqual(self.row(), before)
        self.assertEqual(self.paths.config.read_bytes(), doc)

    def test_explicit_replacement_cannot_override_legacy_approval(self):
        self.remove_pristine_history()
        self.legacy()
        replacement = self.result('replacement.zip')
        before = self.paths.config.read_bytes()
        with self.assertRaises(ControlError) as caught:
            self.setup_source(replacement['path'])
        self.assertEqual(caught.exception.code, 'bootstrap_conflict')
        self.assertEqual(self.paths.config.read_bytes(), before)
        self.assertFalse((self.paths.state / 'automation.sqlite3').exists())

    def test_partially_configured_legacy_seed_is_not_dropped(self):
        data = render(self.config) + '\nseed_result = ' + json.dumps(self.seed['path']) + '\n'
        write_private(self.paths.config, data.encode())
        with self.assertRaises(ControlError) as caught:
            self.setup_source()
        self.assertEqual(caught.exception.code, 'invalid_config')
        self.assertEqual(self.paths.config.read_text(), data)

    def test_migration_refuses_changed_thread(self):
        self.legacy()
        before = self.row()
        with self.assertRaises(ControlError) as caught:
            configure(self.paths, thread_id=str(uuid4()))
        self.assertEqual(caught.exception.code, 'ledger_scope_mismatch')
        self.assertEqual(self.row(), before)

    def empty_legacy_history(self):
        # Simulate old code's pre-enqueue schema (no job was ever dispatched).
        ledger = self.history()
        ledger.db.execute('DELETE FROM jobs')
        ledger.db.execute('UPDATE meta SET current=NULL')
        ledger.close()
        self.legacy()

    def test_old_empty_history_initializes_only_matching_source(self):
        self.empty_legacy_history()
        reply = self.setup_source()
        self.assertTrue(reply['bootstrap_created'])
        self.assertEqual(self.row()['stage'], 'ready')
        self.assertEqual(self.row()['sha'], self.seed['sha256'])
        self.assert_clean_config()

    def test_busy_thread_prevents_empty_history_initialization(self):
        self.empty_legacy_history()
        self.settings(thread_status='active')
        before = (self.paths.state / 'automation.sqlite3').read_bytes()
        doc = self.paths.config.read_bytes()
        with self.assertRaises(ControlError) as caught:
            self.setup_source()
        self.assertEqual(caught.exception.code, 'dev_thread_busy')
        self.assertEqual((self.paths.state / 'automation.sqlite3').read_bytes(), before)
        self.assertEqual(self.paths.config.read_bytes(), doc)

    def test_history_with_broken_current_pointer_cannot_be_reseeded(self):
        ledger = self.history()
        ledger.db.execute('UPDATE meta SET current=NULL')
        ledger.close()
        self.legacy()
        with self.assertRaises(ControlError) as caught:
            self.setup_source(self.seed['path'])
        self.assertEqual(caught.exception.code, 'invalid_ledger')

    def test_state_publish_failure_leaves_no_partial_database(self):
        self.remove_pristine_history()
        old = render(replace(self.config, enabled=False))
        write_private(self.paths.config, old.encode())
        with patch('specroad_control.ledger.write_private', side_effect=OSError('injected publish failure')):
            with self.assertRaises(OSError):
                self.setup_source(self.seed['path'])
        self.assertFalse((self.paths.state / 'automation.sqlite3').exists())
        self.assertEqual(self.paths.config.read_text(), old)
        self.assertFalse((self.codex_home / 'calls.jsonl').exists())

    def test_competing_state_publication_is_never_overwritten(self):
        other = self.result('other.zip')
        temporary = self.paths.state / 'competitor.sqlite3'
        ledger = Ledger(temporary, scope(self.config), initial=other)
        ledger.close()
        competing = temporary.read_bytes()
        self.remove_pristine_history()
        old = self.paths.config.read_bytes()
        def publish_competitor(path, _data, *, exclusive=False):
            self.assertTrue(exclusive)
            write_private(path, competing, exclusive=True)
            raise FileExistsError(path)
        with patch('specroad_control.ledger.write_private', side_effect=publish_competitor):
            with self.assertRaises(ControlError) as caught:
                self.setup_source(self.seed['path'])
        self.assertEqual(caught.exception.code, 'bootstrap_conflict')
        self.assertEqual(self.row()['sha'], other['sha256'])
        self.assertEqual(self.paths.config.read_bytes(), old)

    def test_same_state_publication_race_is_idempotent(self):
        self.remove_pristine_history()
        def publish_same(path, data, *, exclusive=False):
            write_private(path, data, exclusive=exclusive)
            raise FileExistsError(path)
        with patch('specroad_control.ledger.write_private', side_effect=publish_same):
            self.setup_source(self.seed['path'])
        ledger = self.history()
        try:
            self.assertEqual(ledger.db.execute('SELECT count(*) FROM jobs').fetchone()[0], 1)
        finally:
            ledger.close()

    def test_migration_retry_after_config_failure_does_not_replay(self):
        self.legacy()
        doc = self.paths.config.read_bytes()
        with patch('specroad_control.commands.write_private', side_effect=OSError('config publication failed')):
            with self.assertRaises(OSError):
                self.setup_source()
        self.assertEqual(self.paths.config.read_bytes(), doc)
        ledger = self.history()
        ledger.change('running')
        ledger.change('uncertain', error='interrupted')
        ledger.close()
        before = self.row()
        self.setup_source()
        self.assertEqual(self.row(), before)
        self.assert_clean_config()

    def test_check_does_not_implicitly_migrate_configuration(self):
        self.legacy()
        doc = self.paths.config.read_bytes()
        before = self.row()
        with self.assertRaises(ControlError) as caught:
            check(self.paths)
        self.assertEqual(caught.exception.code, 'seed_migration_required')
        self.assertEqual(self.paths.config.read_bytes(), doc)
        self.assertEqual(self.row(), before)

    def test_invalid_stored_result_contract_blocks_reinitialization(self):
        ledger = self.history()
        bad = dict(self.seed, dry_run='false')
        ledger.db.execute('UPDATE jobs SET source=?', (json.dumps(bad),))
        ledger.close()
        with self.assertRaises(ControlError) as caught:
            self.setup_source(self.seed['path'])
        self.assertEqual(caught.exception.code, 'invalid_ledger')

    def test_legacy_unknown_config_field_is_preserved_not_discarded(self):
        self.legacy()
        before = self.paths.config.read_text() + 'unexpected_field = true\n'
        write_private(self.paths.config, before.encode())
        with self.assertRaises(ControlError) as caught:
            self.setup_source()
        self.assertEqual(caught.exception.code, 'invalid_config')
        self.assertEqual(self.paths.config.read_text(), before)

    def test_corrupt_seed_metadata_never_creates_a_new_job(self):
        ledger = self.history()
        ledger.db.execute("UPDATE meta SET seed='not-a-sha'")
        ledger.close()
        with self.assertRaises(ControlError) as caught:
            self.setup_source(self.seed['path'])
        self.assertEqual(caught.exception.code, 'invalid_ledger')
