"""Behavioral regression coverage for installation under inherited umasks."""
from contextlib import contextmanager
import os
import stat
from unittest.mock import patch

from specroad_control import service
from specroad_control.errors import ControlError
from specroad_control.local import private_dir, read_private, user_dir, write_private
from codex_control_tests.support import LocalCase


@contextmanager
def file_creation_mask(value):
    previous = os.umask(value)
    try:
        yield
    finally:
        os.umask(previous)


class PermissionTests(LocalCase):
    def manager(self):
        props = {'LoadState': 'loaded', 'ActiveState': 'inactive', 'UnitFileState': 'static'}
        inspector = patch.object(service, 'inspect', return_value=props)
        inspector.start()
        self.addCleanup(inspector.stop)
        actions = patch.object(service, 'checked')
        mock = actions.start()
        self.addCleanup(actions.stop)
        return mock

    def assert_mode(self, path, mode):
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), mode)

    def check_install(self, mask):
        actions = self.manager()
        with file_creation_mask(mask):
            result = service.install(self.paths)
            current = os.umask(mask)
            self.assertEqual(current, mask)
            self.assertTrue(result['installed'])
            self.assertFalse(result['started'])
            self.assertFalse(result['autostart'])
            actions.assert_called_once_with(['daemon-reload'])
            for directory in (self.home/'cfg', self.home/'cfg/systemd', self.paths.unit.parent,
                              self.paths.config.parent, self.paths.home, self.paths.state):
                self.assert_mode(directory, 0o700)
            self.assert_mode(self.paths.unit, 0o600)
            self.assert_mode(self.paths.config, 0o600)
            self.assertFalse(self.paths.socket.exists())

    def test_install_under_umask_0000(self):
        self.check_install(0o000)

    def test_install_under_umask_0002(self):
        self.check_install(0o002)

    def test_install_under_umask_0022(self):
        self.check_install(0o022)

    def test_install_under_umask_0077(self):
        self.check_install(0o077)

    def test_existing_safe_systemd_directories_keep_modes_and_other_units(self):
        self.manager()
        self.paths.unit.parent.mkdir(parents=True)
        directories = (self.home/'cfg', self.home/'cfg/systemd', self.paths.unit.parent)
        for directory in directories:
            directory.chmod(0o755)
        other_unit = self.paths.unit.parent/'unrelated.service'
        other_unit.write_bytes(b'unrelated service - preserve')
        other_unit.chmod(0o644)
        with file_creation_mask(0o002):
            service.install(self.paths)
        for directory in directories:
            self.assert_mode(directory, 0o755)
        self.assertEqual(other_unit.read_bytes(), b'unrelated service - preserve')
        self.assert_mode(other_unit, 0o644)

    def test_reinstall_under_umask_0002_preserves_real_config_bytes(self):
        self.manager()
        service.install(self.paths)
        config = read_private(self.paths.config) + b'\n# local setting retained\n'
        write_private(self.paths.config, config)
        with file_creation_mask(0o002):
            service.install(self.paths)
        self.assertEqual(read_private(self.paths.config), config)
        self.assert_mode(self.paths.config, 0o600)

    def test_existing_group_writable_unit_parent_rejected_without_chmod(self):
        self.check_unsafe_unit_parent(0o775)

    def test_existing_world_writable_unit_parent_rejected_without_chmod(self):
        self.check_unsafe_unit_parent(0o777)

    def check_unsafe_unit_parent(self, mode):
        actions = self.manager()
        self.paths.unit.parent.mkdir(parents=True)
        self.paths.unit.parent.chmod(mode)
        with self.assertRaises(ControlError) as caught:
            service.install(self.paths)
        self.assertEqual(caught.exception.code, 'unsafe_permissions')
        self.assert_mode(self.paths.unit.parent, mode)
        self.assertFalse(self.paths.unit.exists())
        self.assertFalse(self.paths.config.exists())
        actions.assert_not_called()

    def test_unsafe_existing_intermediate_directory_is_not_repaired(self):
        actions = self.manager()
        parent = self.paths.unit.parent.parent
        parent.mkdir(parents=True)
        parent.chmod(0o775)
        with self.assertRaises(ControlError) as caught:
            service.install(self.paths)
        self.assertEqual(caught.exception.code, 'unsafe_permissions')
        self.assert_mode(parent, 0o775)
        self.assertFalse(self.paths.unit.parent.exists())
        self.assertFalse(self.paths.config.exists())
        actions.assert_not_called()

    def test_safe_existing_intermediate_kept_when_user_child_is_created(self):
        self.manager()
        parent = self.paths.unit.parent.parent
        parent.mkdir(parents=True)
        parent.chmod(0o755)
        (self.home/'cfg').chmod(0o755)
        with file_creation_mask(0o002):
            service.install(self.paths)
        self.assert_mode(parent, 0o755)
        self.assert_mode(self.paths.unit.parent, 0o700)

    def test_private_directory_creates_all_missing_levels_privately(self):
        with file_creation_mask(0o000):
            private_dir(self.home/'a/b/c')
        for name in ('a', 'a/b', 'a/b/c'):
            self.assert_mode(self.home/name, 0o700)

    def test_private_directory_does_not_chmod_existing_readable_directory(self):
        target = self.home/'existing'
        target.mkdir()
        target.chmod(0o755)
        with self.assertRaises(ControlError) as caught:
            private_dir(target)
        self.assertEqual(caught.exception.code, 'unsafe_permissions')
        self.assert_mode(target, 0o755)

    def test_symlink_parent_is_not_followed(self):
        real = self.home/'real'
        real.mkdir(mode=0o700)
        alias = self.home/'alias'
        alias.symlink_to(real, target_is_directory=True)
        with self.assertRaises(ControlError) as caught:
            user_dir(alias/'child')
        self.assertEqual(caught.exception.code, 'unsafe_path')
        self.assertFalse((real/'child').exists())
        self.assertTrue(alias.is_symlink())

    def test_regular_file_cannot_become_directory(self):
        target = self.home/'existing'
        target.write_bytes(b'preserve')
        target.chmod(0o600)
        with self.assertRaises(ControlError) as caught:
            user_dir(target)
        self.assertEqual(caught.exception.code, 'unsafe_permissions')
        self.assertEqual(target.read_bytes(), b'preserve')

    def test_concurrently_created_writable_directory_is_rejected(self):
        target = self.home/'concurrent'
        def concurrent_mkdir(*args, **kwargs):
            os.mkdir(target, 0o700)
            target.chmod(0o775)
            raise FileExistsError(target)
        with patch.object(type(target), 'mkdir', side_effect=concurrent_mkdir):
            with self.assertRaises(ControlError) as caught:
                user_dir(target)
        self.assertEqual(caught.exception.code, 'unsafe_permissions')
        self.assert_mode(target, 0o775)

    def test_install_failure_does_not_leave_changed_umask(self):
        self.manager()
        self.paths.unit.parent.mkdir(parents=True)
        self.paths.unit.parent.chmod(0o775)
        with file_creation_mask(0o002):
            with self.assertRaises(ControlError):
                service.install(self.paths)
            self.assertEqual(os.umask(0o002), 0o002)
