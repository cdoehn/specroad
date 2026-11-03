"""Pure workspace path and permission contracts, with no private runtime state."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from specroad_control.config import Config, execution_directory, writable_roots
from specroad_control.continuation_evidence import policy
from specroad_control.errors import ControlError


class ExecutionDirectoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='control-path-contract-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / 'Workspace Ä with spaces'
        self.dev = self.workspace / 'dev'
        self.dev.mkdir(parents=True)
        self.exchange = self.workspace / 'exchange'
        self.exchange.mkdir()
        self.config = Config(self.dev, self.exchange, str(uuid4()), thread_cwd=self.workspace)

    def reject(self, target):
        with self.assertRaises(ControlError) as caught:
            execution_directory(replace(self.config, thread_cwd=target))
        self.assertEqual(caught.exception.code, 'invalid_thread_workspace')

    def test_parent_is_preserved_without_string_normalization(self):
        self.assertEqual(execution_directory(self.config), self.workspace)

    def test_explicit_dev_is_supported(self):
        self.assertEqual(execution_directory(replace(self.config, thread_cwd=self.dev)), self.dev)

    def test_legacy_dev_is_supported(self):
        self.assertEqual(execution_directory(replace(self.config, thread_cwd=None)), self.dev)

    def test_policy_grants_workspace_and_exchange_without_network(self):
        self.assertEqual(policy(self.config), {
            'approvalPolicy': 'never', 'sandboxPolicy': {'type': 'workspaceWrite',
                'writableRoots': [str(self.workspace), str(self.exchange)], 'networkAccess': False}})

    def test_parent_policy_includes_every_child_but_not_parent_above_it(self):
        roots = list(map(Path, writable_roots(self.config)))
        for name in ('dev', 'apply', 'control', 'patchharbor', 'workspace-script'):
            self.assertTrue(any((self.workspace / name).is_relative_to(root) for root in roots))
        self.assertFalse(any(self.root.is_relative_to(root) for root in roots))

    def test_relative_workspace_is_rejected(self):
        self.reject(Path('relative'))

    def test_foreign_existing_directory_is_rejected(self):
        foreign = self.root / 'foreign'
        foreign.mkdir()
        self.reject(foreign)

    def test_noncanonical_parent_segments_are_rejected(self):
        self.reject(self.workspace / 'dev' / '..')

    def test_removed_workspace_is_rejected(self):
        self.dev.rmdir()
        self.exchange.rmdir()
        self.workspace.rmdir()
        self.reject(self.workspace)

    def test_workspace_replaced_by_file_is_rejected(self):
        self.dev.rmdir()
        self.exchange.rmdir()
        self.workspace.rmdir()
        self.workspace.write_text('not a directory')
        self.reject(self.workspace)

    def test_workspace_symlink_is_rejected(self):
        link = self.root / 'linked'
        link.symlink_to(self.workspace, target_is_directory=True)
        self.reject(link)

    def test_late_parent_symlink_is_rejected(self):
        saved = self.root / 'saved'
        self.workspace.rename(saved)
        self.workspace.symlink_to(saved, target_is_directory=True)
        self.reject(self.workspace)

    def test_symlink_in_ancestor_is_rejected(self):
        link = self.root / 'linked'
        link.symlink_to(self.workspace, target_is_directory=True)
        self.reject(link / 'dev')

    def test_changed_dev_symlink_does_not_authorize_an_unrelated_parent(self):
        foreign = self.root / 'foreign'
        foreign.mkdir()
        self.dev.rmdir()
        self.dev.symlink_to(foreign, target_is_directory=True)
        self.reject(self.workspace)
