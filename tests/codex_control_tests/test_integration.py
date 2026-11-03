import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
from unittest.mock import patch
import zipfile
from hashlib import sha256
from specroad_control import migration, releases, service
from specroad_control.config import initialize, load
from specroad_control.errors import ControlError
from specroad_control.local import Paths, json_read, json_write, private_dir, read_private, write_private
from codex_control_tests.support import LocalCase


class LayoutTests(LocalCase):
    def test_one_root_owns_all_runtime_locations(self):
        self.assertEqual(self.paths.config, self.paths.home/'config/config.toml')
        self.assertEqual(self.paths.state, self.paths.home/'state')
        self.assertEqual(self.paths.runtime, self.paths.home/'run')
        self.assertEqual(self.paths.logs, self.paths.home/'logs')
        self.assertEqual(self.paths.target_locks, self.paths.state/'target-locks')

    def test_config_cannot_escape_data_home(self):
        with self.assertRaises(ControlError):
            Paths.discover(str(self.home/'foreign/config.toml'))

    def test_default_root_is_independent_of_legacy_state_and_runtime_xdg(self):
        with patch.dict(os.environ, {'SPECROAD_CONTROL_HOME': '', 'XDG_STATE_HOME': '/obsolete', 'XDG_RUNTIME_DIR': '/obsolete'}):
            paths = Paths.discover()
        self.assertEqual(paths.home, self.home/'.local/share/specroad/dev/codex/control')

    def test_installed_service_uses_versioned_code_and_central_logs(self):
        rendered = service.unit_text(self.paths)
        self.assertIn(str(self.paths.home/'releases'/('a'*40)/'control'), rendered)
        self.assertIn('StandardError=append:', rendered)
        self.assertIn(str(self.paths.logs/'control.log'), rendered)

    def test_modified_release_prevents_start(self):
        path = releases.active_entrypoint(self.paths)
        write_private(path, b'changed')
        with patch.object(service, 'checked') as calls, self.assertRaises(ControlError):
            releases.active_entrypoint(self.paths)
        calls.assert_not_called()

    def test_unfinished_migration_blocks_config_load(self):
        initialize(self.paths)
        json_write(self.paths.home/'migration.json', {'phase':'copying'})
        with self.assertRaises(ControlError):
            load(self.paths)

    def test_unfinished_deployment_blocks_service_entrypoint(self):
        json_write(self.paths.home/'deployment.json', {'phase':'switching'})
        with self.assertRaises(ControlError):
            releases.active_entrypoint(self.paths)


class MigrationTests(LocalCase):
    def legacy(self):
        old = Paths.legacy()
        initialize(old)
        private_dir(old.state)
        db = sqlite3.connect(old.state/'automation.sqlite3')
        db.execute('CREATE TABLE preserved (budget INTEGER, pause TEXT, payload BLOB)')
        db.execute('INSERT INTO preserved VALUES (2, ?, ?)', ('paused', b'original'))
        db.commit(); db.close()
        (old.state/'automation.sqlite3').chmod(0o600)
        write_private(old.state/'jobs/history.json', b'{"keep":"bytes"}\n')
        write_private(old.config.with_name('config.limits.toml'), b'min_free_bytes = 10000000000\n')
        write_private(old.unit, service.OWNER.encode()+b'legacy unit\n')
        return old

    def run_migration(self):
        with patch.object(migration, 'stopped'), patch.object(migration.shutil, 'disk_usage', return_value=type('Disk', (), {'free':10**12})()):
            return migration.migrate(self.paths)

    def test_bytes_history_pause_budget_and_originals_preserved(self):
        old = self.legacy()
        before = migration.inventory(old)
        result = self.run_migration()
        self.assertTrue(result['migrated']); self.assertFalse(result['started'])
        for name, row in before.items():
            self.assertEqual(migration.digest(self.paths.home/name), row['sha256'])
            self.assertEqual(migration.digest(Path(row['source'])), row['sha256'])
        db = sqlite3.connect(self.paths.state/'automation.sqlite3')
        try: self.assertEqual(db.execute('SELECT * FROM preserved').fetchone(), (2, 'paused', b'original'))
        finally: db.close()
        with zipfile.ZipFile(self.paths.home/'backups/migration-source.zip') as archive:
            self.assertIsNone(archive.testzip())
        self.assertTrue(self.run_migration()['already_migrated'])

    def test_copy_failure_is_resumable_and_never_starts_service(self):
        self.legacy()
        with patch.object(migration, 'copy_record', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.run_migration()
        self.assertEqual(json_read(self.paths.home/'migration.json')['phase'], 'copying')
        self.assertTrue(self.run_migration()['migrated'])

    def test_changed_source_after_interruption_is_blocked(self):
        old = self.legacy()
        with patch.object(migration, 'copy_record', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.run_migration()
        write_private(old.state/'jobs/history.json', b'changed')
        with self.assertRaises(ControlError): self.run_migration()

    def test_foreign_target_is_not_overwritten(self):
        self.legacy()
        write_private(self.paths.state/'foreign', b'existing')
        with self.assertRaises(ControlError): self.run_migration()
        self.assertEqual(read_private(self.paths.state/'foreign'), b'existing')

    def test_running_worker_blocks_copy(self):
        self.legacy()
        with patch.object(service, 'verify_owned', return_value={'ActiveState':'active'}):
            with self.assertRaises(ControlError): migration.migrate(self.paths)
        self.assertFalse((self.paths.home/'migration.json').exists())

    def test_linked_source_is_rejected(self):
        old = self.legacy()
        (old.state/'alias').symlink_to(old.state/'jobs/history.json')
        with self.assertRaises(ControlError): self.run_migration()

    def test_history_inventory_larger_than_small_json_limit(self):
        old = self.legacy()
        for number in range(300):
            write_private(old.state/('jobs/'+str(number)+'.json'), b'{}')
        self.assertTrue(self.run_migration()['migrated'])
        self.assertLess((self.paths.home/'migration.json').stat().st_size, 65536)


class ReleaseTests(LocalCase):
    def candidate(self):
        root = releases.active_entrypoint(self.paths).parent
        from specroad_control.apply_reconcile_proof import hashed
        binding = {'repo_id':'test-repo', 'base_commit':'a'*40}
        public = {'binding':binding, 'source_result_sha256':'d'*64,
                  'stages':[{'commit_id':'fixture.W'}]}
        progress = {'format_version':1,'kind':'specroad-apply-progress-v1','phase':'completed',
                    'error':None,'active_commit_id':None,'remaining_commit_ids':[],
                    'plan_sha256':hashed(public),'source_result_sha256':'d'*64,'actual_head':'c'*40,
                    'committed':[{'commit_id':'fixture.W','commit':'c'*40,'parent':'a'*40,
                                  'gate':{'selection_sha256':'e'*64,'observations_sha256':'f'*64,
                                          'tests':2,'required_tests':1,'partition_index':0}}]}
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('logs/execution.log', 'SPECROAD_APPLY_PLAN '+json.dumps(public)+'\n'+
                             'SPECROAD_APPLY_PROGRESS '+json.dumps(progress)+'\n')
            for p in root.rglob('*'):
                if p.is_file() and p.name != 'release.json':
                    archive.writestr(releases.PREFIX+p.relative_to(root).as_posix(), p.read_bytes())
        raw = buffer.getvalue()
        facts = {'kind':'result','operation':'apply','dry_run':False,'success':True,
                 'dirty':False,'entrypoint_started':True,'completed_commit':'c'*40,'expected':binding,
                 'binding':{'repo_id':'test-repo','base_commit':'c'*40},'sha256':sha256(raw).hexdigest()}
        return raw, facts

    def test_release_rejects_failure_dirty_wrong_repo_or_changed_bytes(self):
        raw, facts = self.candidate()
        self.assertIn('control', releases.release_files(raw, facts, 'test-repo'))
        for changes in ({'success':False},{'dirty':True},{'completed_commit':'d'*40},{'sha256':'0'*64}):
            with self.subTest(changes=changes), self.assertRaises(ControlError):
                releases.release_files(raw, dict(facts, **changes), 'test-repo')
        with self.assertRaises(ControlError): releases.release_files(raw, facts, 'foreign')

    def test_deploy_keeps_history_and_does_not_start(self):
        raw, facts = self.candidate()
        initialize(self.paths)
        cfg = load(self.paths)
        facts['binding']['repo_id'] = cfg.repo_id
        candidate = self.home/'result.zip'; candidate.write_bytes(raw)
        facts['path'] = str(candidate)
        write_private(self.paths.unit, service.OWNER.encode()+b'old')
        write_private(self.paths.state/'preserved', b'pause-and-history')
        with patch('specroad_control.core.Core.result', return_value=facts), patch.object(migration,'stopped'), patch.object(service,'checked') as call:
            result = releases.deploy(self.paths, str(candidate))
        self.assertFalse(result['started'])
        self.assertEqual(read_private(self.paths.state/'preserved'), b'pause-and-history')
        self.assertEqual([c.args[0] for c in call.call_args_list], [['daemon-reload']])
        self.assertEqual(releases.active_entrypoint(self.paths).parent.name, 'c'*40)
