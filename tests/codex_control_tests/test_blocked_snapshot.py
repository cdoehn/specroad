"""Independent byte-level oracles for passive Apply snapshot evidence."""
from hashlib import sha256
from pathlib import Path
import tempfile
from unittest import TestCase
import zipfile

from specroad_control.apply_reconcile_proof import canonical
from specroad_control.blocked_chain_proof import modified_files, snapshot
from specroad_control.errors import ControlError
from codex_control_tests.blocked_chain_support import git_blob, snapshot_members


def diff(before, after, hunks):
    return (b'diff --git a/source.txt b/source.txt\nindex ' + git_blob(before).encode() + b'..'
            + git_blob(after).encode() + b' 100644\n--- a/source.txt\n+++ b/source.txt\n' + hunks)


class PassiveSnapshotTests(TestCase):
    def test_exact_multiple_hunks_preserve_unmentioned_lines(self):
        before = b'a\nb\nc\nd\ne\nf\n'; after = b'a\nB\nc\nd\nE\nf\n'
        patch = diff(before, after, b'@@ -2 +2 @@\n-b\n+B\n@@ -5 +5 @@\n-e\n+E\n')
        result = modified_files({'source.txt': ('100644', before), 'kept': ('100755', b'kept\n')}, patch)
        self.assertEqual(result, {'source.txt': ('100644', after), 'kept': ('100755', b'kept\n')})

    def test_no_final_newline_is_preserved(self):
        patch = diff(b'old', b'new', b'@@ -1 +1 @@\n-old\n\\ No newline at end of file\n+new\n\\ No newline at end of file\n')
        self.assertEqual(modified_files({'source.txt': ('100644', b'old')}, patch)['source.txt'][1], b'new')

    def test_crlf_is_preserved_byte_for_byte(self):
        before, after = b'a\r\nold\r\n', b'a\r\nnew\r\n'
        patch = diff(before, after, b'@@ -1,2 +1,2 @@\n a\r\n-old\r\n+new\r\n')
        self.assertEqual(modified_files({'source.txt': ('100644', before)}, patch)['source.txt'][1], after)

    def test_insertion_into_empty_file(self):
        patch = diff(b'', b'new\n', b'@@ -0,0 +1 @@\n+new\n')
        self.assertEqual(modified_files({'source.txt': ('100644', b'')}, patch)['source.txt'][1], b'new\n')

    def test_removing_contents_keeps_the_empty_file(self):
        patch = diff(b'old\n', b'', b'@@ -1 +0,0 @@\n-old\n')
        self.assertEqual(modified_files({'source.txt': ('100644', b'old\n')}, patch), {'source.txt': ('100644', b'')})

    def test_wrong_context_is_rejected_without_fuzz(self):
        patch = diff(b'old\n', b'new\n', b'@@ -1 +1 @@\n-wrong\n+new\n')
        with self.assertRaises(ControlError): modified_files({'source.txt': ('100644', b'old\n')}, patch)

    def test_wrong_output_position_is_rejected(self):
        patch = diff(b'old\n', b'new\n', b'@@ -1 +2 @@\n-old\n+new\n')
        with self.assertRaises(ControlError): modified_files({'source.txt': ('100644', b'old\n')}, patch)

    def test_postimage_hash_cannot_be_forged_by_a_valid_hunk(self):
        patch = diff(b'old\n', b'different\n', b'@@ -1 +1 @@\n-old\n+new\n')
        with self.assertRaises(ControlError): modified_files({'source.txt': ('100644', b'old\n')}, patch)

    def test_duplicate_diff_for_the_same_path_is_rejected(self):
        patch = diff(b'old\n', b'new\n', b'@@ -1 +1 @@\n-old\n+new\n')
        with self.assertRaises(ControlError): modified_files({'source.txt': ('100644', b'old\n')}, patch + patch)

    def fixture(self, base, work, **replace):
        temporary = tempfile.TemporaryDirectory(prefix='snapshot-proof-'); self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / 'result.zip'
        entries, untracked, members = snapshot_members(base, work)
        members['manifest.json'] = canonical({'base_entries': entries, 'untracked_entries': untracked})
        members.update(replace)
        with zipfile.ZipFile(path, 'w') as archive:
            for name, content in members.items(): archive.writestr(name, content)
        return {'path': str(path), 'sha256': sha256(path.read_bytes()).hexdigest(), 'dirty': base != work}

    def test_complete_native_inventory_reconstructs_tracked_and_untracked_bytes(self):
        fact = self.fixture({'source.txt': b'old\n'}, {'source.txt': b'new\n', 'new.txt': b'added\n'})
        self.assertEqual(snapshot(fact), ({'source.txt': ('100644', b'old\n')},
                                         {'source.txt': ('100644', b'new\n'), 'new.txt': ('100644', b'added\n')}))

    def test_uninventoried_snapshot_entry_blocks(self):
        fact = self.fixture({'source.txt': b'old\n'}, {'source.txt': b'old\n'}, **{'base/extra.txt': b'extra'})
        with self.assertRaises(ControlError): snapshot(fact)

    def test_staged_changes_are_not_silently_ignored(self):
        fact = self.fixture({'source.txt': b'old\n'}, {'source.txt': b'old\n'}, **{'changes/staged.patch': b'changes'})
        with self.assertRaises(ControlError): snapshot(fact)

    def test_dirty_flag_must_match_the_byte_maps(self):
        fact = self.fixture({'source.txt': b'old\n'}, {'source.txt': b'old\n'}); fact['dirty'] = True
        with self.assertRaises(ControlError): snapshot(fact)

    def test_changed_native_archive_bytes_are_rejected(self):
        fact = self.fixture({'source.txt': b'old\n'}, {'source.txt': b'old\n'})
        with Path(fact['path']).open('ab') as stream: stream.write(b'changed')
        with self.assertRaises(ControlError): snapshot(fact)
