import os
from pathlib import Path
import stat
from specroad_control.config import initialize, load
from specroad_control.errors import ControlError
from specroad_control.local import Paths, REPO, json_read, json_write, lock, outside, private_dir, read_private, write_private
from codex_control_tests.support import LocalCase

class LocalTests(LocalCase):
    def test_external_config_created_once_and_preserved(self):
        config = initialize(self.paths)
        self.assertEqual(config.session_id, '')
        data = read_private(self.paths.config).replace(b'session_id = ""', b'session_id = "00000000-0000-4000-8000-000000000001"')
        write_private(self.paths.config, data)
        initialize(self.paths)
        self.assertEqual(read_private(self.paths.config), data)
        self.assertEqual(stat.S_IMODE(self.paths.config.stat().st_mode), 0o600)

    def test_status_read_does_not_create_state(self):
        self.assertIsNone(json_read(self.paths.state_file))
        self.assertFalse(self.paths.state.exists())

    def test_atomic_private_state_roundtrip(self):
        json_write(self.paths.state_file, {'schema': 1, 'value': 1})
        json_write(self.paths.state_file, {'schema': 1, 'value': 2})
        self.assertEqual(json_read(self.paths.state_file)['value'], 2)
        self.assertEqual(stat.S_IMODE(self.paths.state_file.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.paths.state.stat().st_mode), 0o700)

    def test_exclusive_creation_preserves_existing(self):
        write_private(self.paths.config, b'old', exclusive=True)
        with self.assertRaises(FileExistsError): write_private(self.paths.config, b'new', exclusive=True)
        self.assertEqual(read_private(self.paths.config), b'old')

    def test_inside_git_or_product_is_rejected(self):
        worktree = self.home/'example-repo'; worktree.mkdir(); (worktree/'.git').write_text('gitdir: ignored')
        for p in (worktree/'config.toml', REPO/'config.toml', REPO.parent/'exchange/config.toml'):
            with self.subTest(path=str(p)), self.assertRaises(ControlError): outside(p)

    def test_symlink_and_public_config_are_rejected(self):
        initialize(self.paths)
        self.paths.config.chmod(0o644)
        with self.assertRaises(ControlError): load(self.paths)
        self.paths.config.chmod(0o600)
        target = self.home/'alias'
        target.symlink_to(self.paths.config.parent, target_is_directory=True)
        with self.assertRaises(ControlError): outside(target/'config.toml')

    def test_lock_is_exclusive_and_reusable(self):
        p = self.paths.state/'worker.lock'
        with lock(p):
            with self.assertRaises(ControlError):
                with lock(p): pass
        with lock(p): pass
        self.assertTrue(p.exists())

    def test_invalid_config_preserved(self):
        write_private(self.paths.config, b'format_version = [broken')
        with self.assertRaises(ControlError): load(self.paths)
        self.assertEqual(read_private(self.paths.config), b'format_version = [broken')
