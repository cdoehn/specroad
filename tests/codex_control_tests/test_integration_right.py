from hashlib import sha256
import io
import json
import os
from pathlib import Path
from unittest.mock import patch
import zipfile
from specroad_control import migration, releases, service
from specroad_control.config import initialize, load
from specroad_control.errors import ControlError
from specroad_control.local import json_read, json_write, read_private, write_private
from codex_control_tests import test_integration as integration
from codex_control_tests.support import LocalCase


class ReleaseRecoveryTests(LocalCase):
    candidate = integration.ReleaseTests.candidate
    def prepare(self):
        raw, facts = self.candidate()
        initialize(self.paths)
        facts['binding']['repo_id'] = load(self.paths).repo_id
        candidate = self.home/'result.zip'; candidate.write_bytes(raw)
        facts['path'] = str(candidate)
        write_private(self.paths.unit, service.OWNER.encode()+b'old unit')
        self.enterContext(patch('specroad_control.core.Core.result', return_value=facts))
        self.enterContext(patch.object(migration,'stopped'))
        return candidate

    def test_reload_failure_restores_active_version_and_unit(self):
        candidate = self.prepare()
        before = read_private(self.paths.unit)
        active = json_read(self.paths.home/'active-release.json')
        with patch.object(service,'checked', side_effect=[ControlError('systemd_failed','failure'), None]):
            with self.assertRaises(ControlError): releases.deploy(self.paths, str(candidate))
        self.assertEqual(read_private(self.paths.unit), before)
        self.assertEqual(json_read(self.paths.home/'active-release.json'), active)
        self.assertEqual(json_read(self.paths.home/'deployment.json')['phase'], 'rolled_back')

    def test_interrupted_same_release_can_finish_without_reseeding(self):
        candidate = self.prepare()
        original = releases.json_write
        def die(path, data):
            if path.name == 'deployment.json' and data.get('phase') == 'completed':
                raise OSError('lost connection after reload')
            original(path, data)
        with patch.object(service,'checked'), patch.object(releases,'json_write', side_effect=die):
            with self.assertRaises(OSError): releases.deploy(self.paths, str(candidate))
        with self.assertRaises(ControlError): releases.active_entrypoint(self.paths)
        with patch.object(service,'checked') as calls:
            self.assertTrue(releases.deploy(self.paths, str(candidate))['deployed'])
        self.assertEqual([c.args[0] for c in calls.call_args_list], [['daemon-reload']])
        self.assertEqual(releases.active_entrypoint(self.paths).parent.name, 'c'*40)

    def test_foreign_unit_after_interruption_is_preserved(self):
        candidate = self.prepare()
        active = json_read(self.paths.home/'active-release.json')
        journal = {'format_version':1,'phase':'switching','previous':active,'next':active,'previous_unit':'old'}
        json_write(self.paths.home/'deployment.json',journal)
        with patch.object(service,'checked') as calls, self.assertRaises(ControlError):
            releases.deploy(self.paths,str(candidate))
        calls.assert_not_called()
        self.assertEqual(read_private(self.paths.unit),service.OWNER.encode()+b'old unit')

    def test_first_deployment_can_create_missing_unit(self):
        candidate = self.prepare()
        self.paths.unit.unlink()
        with patch.object(service,'checked') as calls:
            self.assertTrue(releases.deploy(self.paths,str(candidate))['deployed'])
        self.assertTrue(self.paths.unit.exists())
        self.assertEqual([c.args[0] for c in calls.call_args_list],[['daemon-reload']])

    def test_new_service_must_be_absent_from_manager(self):
        with patch.object(service,'inspect',return_value={'LoadState':'loaded','ActiveState':'inactive'}):
            with self.assertRaises(ControlError): migration.stopped(self.paths,allow_uninstalled=True)

    def test_facts_use_strict_booleans(self):
        raw,facts=self.candidate()
        for key in ('dirty','dry_run','success','entrypoint_started'):
            with self.subTest(key=key),self.assertRaises(ControlError):
                releases.release_files(raw,dict(facts,**{key:int(facts[key])}),'test-repo')

    def test_archive_traversal_is_rejected(self):
        raw,facts=self.candidate()
        buffer=io.BytesIO(raw)
        with zipfile.ZipFile(buffer,'a') as archive:
            archive.writestr(releases.PREFIX+'specroad_control/../escape.py',b'bad')
        changed=buffer.getvalue();facts['sha256']=sha256(changed).hexdigest()
        with self.assertRaises(ControlError): releases.release_files(changed,facts,'test-repo')

    def test_added_untracked_runtime_code_is_rejected(self):
        root=releases.active_entrypoint(self.paths).parent
        write_private(root/'specroad_control/extra.py',b'pass')
        with self.assertRaises(ControlError): releases.active_entrypoint(self.paths)


class MigrationRecoveryTests(LocalCase):
    legacy = integration.MigrationTests.legacy
    run_migration = integration.MigrationTests.run_migration
    def test_changed_backup_after_interruption_stops_retry(self):
        self.legacy()
        with patch.object(migration,'copy_record',side_effect=OSError('no space')):
            with self.assertRaises(OSError): self.run_migration()
        target=self.paths.home/'backups/migration-source.zip'
        with zipfile.ZipFile(target,'a') as archive: archive.writestr('unexpected',b'changed')
        with self.assertRaises(ControlError): self.run_migration()

    def test_incomplete_migration_cannot_be_treated_as_new(self):
        self.legacy()
        json_write(self.paths.home/'migration.json', {'format_version':1,'phase':'unknown'})
        with self.assertRaises(ControlError): self.run_migration()

    def test_incomplete_apply_log_rejects_release(self):
        case = integration.ReleaseTests.candidate
        raw, facts = case(self)
        buffer = io.BytesIO(raw)
        # Build a new archive with only the native-looking source files, no gate proof.
        target = self.home/'without-proof.zip'
        with zipfile.ZipFile(io.BytesIO(raw)) as source, zipfile.ZipFile(target,'w') as dest:
            for entry in source.infolist():
                if entry.filename != 'logs/execution.log':
                    dest.writestr(entry.filename,source.read(entry.filename))
        facts.update(path=str(target),sha256=sha256(target.read_bytes()).hexdigest())
        with self.assertRaises(ControlError): releases.tested_apply(facts)
