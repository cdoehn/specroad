"""Passive reads reject special files, resource overflow and ambiguous inventories."""
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch
import zipfile

from specroad_control.apply_reconcile_proof import archive_bytes, canonical
from specroad_control.blocked_chain_proof import snapshot, no_collisions
from specroad_control.errors import ControlError
import codex_control_tests.test_blocked_snapshot as support


class PassiveSnapshotGuardTests(TestCase):
    fixture = support.PassiveSnapshotTests.fixture

    def rewrite(self, fact, change):
        path = Path(fact['path'])
        with zipfile.ZipFile(path) as archive: members = {n: archive.read(n) for n in archive.namelist()}
        change(members)
        with zipfile.ZipFile(path, 'w') as archive:
            for name, content in members.items(): archive.writestr(name, content)
        fact['sha256'] = sha256(path.read_bytes()).hexdigest()

    def test_symlink_is_not_followed_even_to_identical_bytes(self):
        fact = self.fixture({'file.txt': b'body\n'}, {'file.txt': b'body\n'})
        path = Path(fact['path']); real = path.with_suffix('.original'); path.rename(real); path.symlink_to(real)
        with self.assertRaises(OSError): archive_bytes(fact)

    def test_fifo_is_rejected_without_waiting_for_a_writer(self):
        temporary = tempfile.TemporaryDirectory(prefix='fifo-proof-'); self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / 'archive'; os.mkfifo(path)
        with self.assertRaises(ControlError): archive_bytes({'path': str(path), 'sha256': 'a' * 64})

    def test_directory_cannot_be_read_as_a_result_archive(self):
        temporary = tempfile.TemporaryDirectory(prefix='dir-proof-'); self.addCleanup(temporary.cleanup)
        with self.assertRaises(ControlError): archive_bytes({'path': temporary.name, 'sha256': 'a' * 64})

    def test_root_path_cannot_appear_in_a_snapshot(self):
        with self.assertRaises(ControlError): no_collisions({'.': ('100644', b'value')})

    def test_file_directory_collision_is_rejected(self):
        with self.assertRaises(ControlError): no_collisions({'a': ('100644', b'value'), 'a/b': ('100644', b'other')})

    def test_native_inventory_blob_hash_must_match_real_bytes(self):
        fact = self.fixture({'file.txt': b'body\n'}, {'file.txt': b'body\n'})
        self.rewrite(fact, lambda m: m.update({'base/file.txt': b'fake\n'}))
        with self.assertRaises(ControlError): snapshot(fact)

    def test_duplicate_inventory_paths_are_rejected(self):
        fact = self.fixture({'file.txt': b'body\n'}, {'file.txt': b'body\n'})
        def mutate(members):
            manifest = json.loads(members['manifest.json']); manifest['base_entries'] *= 2
            members['manifest.json'] = canonical(manifest)
        self.rewrite(fact, mutate)
        with self.assertRaises(ControlError): snapshot(fact)

    def test_untracked_cannot_overwrite_a_tracked_path(self):
        fact = self.fixture({'file.txt': b'body\n'}, {'file.txt': b'body\n', 'new.txt': b'new\n'})
        def mutate(members):
            manifest = json.loads(members['manifest.json']); manifest['untracked_entries'][0]['path'] = 'file.txt'
            members['manifest.json'] = canonical(manifest); members['untracked/file.txt'] = members.pop('untracked/new.txt')
        self.rewrite(fact, mutate)
        with self.assertRaises(ControlError): snapshot(fact)

    def test_file_count_is_bounded_before_reconstruction(self):
        fact = self.fixture({'a': b'a', 'b': b'b'}, {'a': b'a', 'b': b'b'})
        with patch(snapshot.__module__ + '.FILE_LIMIT', 1):
            with self.assertRaises(ControlError): snapshot(fact)

    def test_total_snapshot_bytes_are_bounded(self):
        fact = self.fixture({'a': b'ab'}, {'a': b'ab'})
        with patch(snapshot.__module__ + '.SNAPSHOT_LIMIT', 1):
            with self.assertRaises(ControlError): snapshot(fact)
