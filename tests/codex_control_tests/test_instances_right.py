"""Conflict, recovery and routing boundaries for parallel controllers."""
from dataclasses import replace
from hashlib import sha256
import os
from unittest.mock import patch
from specroad_control import bootstrap, migration, service
from specroad_control.config import parse, render
from specroad_control.errors import ControlError
from specroad_control.local import Paths, lock, write_private
from specroad_control.toml_compat import tomllib
from codex_control_tests.automation_support import AutomationCase
from codex_control_tests import test_instances as helpers


class InstanceGuards(AutomationCase):
    engine = helpers.InstanceTests.engine
    other = helpers.InstanceTests.other

    def test_invalid_names_and_config_crossing_fail_before_creation(self):
        for name in ('', '../dev2', '/tmp/dev2', 'a/b', 'Upper', 'a' * 33, 'a;start', 'a\n'):
            with self.subTest(name=name), self.assertRaises(ControlError):
                Paths.discover(instance=name)
        with self.assertRaises(ControlError):
            Paths.discover(str(self.paths.config), instance='dev2')
        self.assertFalse((self.paths.home/'instances').exists())

    def test_environment_selection_is_persisted_and_cli_can_override_it(self):
        with patch.dict(os.environ, {'SPECROAD_CONTROL_INSTANCE': 'dev2'}):
            selected = Paths.discover()
            self.assertEqual(selected.instance, 'dev2')
            self.assertEqual(Paths.discover(instance='default'), self.paths)
        text = service.unit_text(selected, entrypoint=self.home/'installed/control')
        self.assertIn('SPECROAD_CONTROL_INSTANCE=dev2', text)
        self.assertIn('SPECROAD_CONTROL_HOME=' + str(self.paths.home), text)

    def test_linked_instance_directory_is_rejected(self):
        container = self.paths.home/'instances'
        container.mkdir(mode=0o700)
        (container/'dev2').symlink_to(self.home)
        with self.assertRaises(ControlError):
            Paths.discover(instance='dev2')

    def test_different_data_homes_still_conflict_on_native_apply_identity(self):
        candidate = replace(self.other(), repo_id=self.config.repo_id)
        with self.engine(self.config, self.paths):
            with patch.dict(os.environ, {'SPECROAD_CONTROL_HOME': str(self.home/'other')}):
                other_paths = Paths.discover(instance='second')
            with self.assertRaises(ControlError):
                with self.engine(candidate, other_paths):
                    self.fail('Shared Apply identity was not protected')

    def test_legacy_repository_lock_blocks_new_instance(self):
        key = sha256(str(self.config.repository.resolve()).encode()).hexdigest()
        with lock(self.paths.target_locks/('repo-' + key + '.lock')):
            with self.assertRaises(ControlError):
                with self.engine(self.config, Paths.discover(instance='dev2')):
                    self.fail('Legacy owner was bypassed')
        with self.engine(self.config, self.paths):
            pass  # Failed partial acquisition must have released every other lock.

    def test_resolved_apply_alias_and_thread_id_across_codex_homes_conflict(self):
        second = Paths.discover(instance='dev2')
        alias = self.home/'apply-alias'
        alias.symlink_to(self.config.apply_directory)
        cases = (replace(self.other(), apply_repository=alias),
                 replace(self.other(), session_id=self.config.session_id, codex_home=self.home/'other-codex'))
        with self.engine(self.config, self.paths):
            for case, candidate in enumerate(cases):
                with self.subTest(case=case), self.assertRaises(ControlError):
                    with self.engine(candidate, second):
                        self.fail('Target alias bypassed ownership')

    def test_stop_and_offline_verification_route_to_named_unit(self):
        second = Paths.discover(instance='dev2')
        inactive = {'LoadState': 'loaded', 'ActiveState': 'inactive'}
        reply = type('Reply', (), {'stdout': '0'})()
        with patch.object(service, 'verify_owned', return_value=inactive), patch.object(service, 'checked', return_value=reply) as call:
            service.stop(second)
            migration.stopped(second)
        self.assertEqual(call.call_args_list[0].args[0], ['--no-block', 'stop', second.unit.name])
        self.assertEqual(call.call_args_list[1].args[0][1], second.unit.name)

    def test_named_legacy_migration_never_copies_default_history(self):
        second = Paths.discover(instance='dev2')
        with self.assertRaises(ControlError):
            migration.migrate(second)
        self.assertFalse(second.home.exists())

    def test_second_lane_seed_requires_exact_apply_path(self):
        candidate = replace(self.other(), apply_repository=self.home/'specroad-apply2')
        with patch('specroad_control.bootstrap.Core.result', return_value=self.seed):
            with self.assertRaises(ControlError):
                bootstrap.select_source(candidate, self.seed['path'], None, needs_initial=True)
        correct = dict(self.seed, repository_path=str(candidate.apply_directory))
        with patch('specroad_control.bootstrap.Core.result', return_value=correct):
            self.assertEqual(bootstrap.select_source(candidate, correct['path'], None, needs_initial=True), correct)

    def test_apply_binding_cannot_overlap_dev_exchange_or_local_state(self):
        second = Paths.discover(instance='dev2')
        for path in (self.config.repository, self.config.exchange, second.home):
            candidate = replace(self.config, apply_repository=path)
            with self.subTest(path=str(path)), self.assertRaises((ValueError, ControlError)):
                parse(tomllib.loads(render(candidate)), second)
