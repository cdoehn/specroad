"""Actual distribution bytes and hashes, independent of the build implementation."""
import ast
import json
import os
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from support.portable import build_distribution, copy_source_fixture, files_under
from support.payload_identity import (
    LANGUAGE_RESOURCES, PROFILE_RESOURCES, SHIPPED_RESOURCES,
    reference_digest, reference_payload,
)


def recorded_metadata(raw):
    """Read a generated data literal without importing or executing its module."""
    assignments = [node for node in ast.parse(raw.decode("utf-8")).body
                   if isinstance(node, ast.Assign) and any(
                       isinstance(target, ast.Name) and target.id == "BUILD_METADATA"
                       for target in node.targets)]
    if len(assignments) != 1:
        raise AssertionError("Exactly one generated build record is required")
    return ast.literal_eval(assignments[0].value)


class PayloadIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = copy_source_fixture(self.root / "source")
        self.package = self.source / "specroad"
        self.sequence = 0

    def build_and_check(self, source=None):
        """Check both real outputs against a separately specified source inventory."""
        source = self.source if source is None else source
        self.sequence += 1
        module, archive = build_distribution(self.root / ("build-" + str(self.sequence)), source)
        expected = reference_payload(source / "specroad", (module / "__main__.py").read_bytes())
        wanted = {"format_version": 1, "hash_algorithm": "specroad-dev-payload-v1",
                  "build_sha256": reference_digest(expected)}
        module_bytes = files_under(module)
        record = module_bytes.pop("specroad/_build.py")
        self.assertEqual(module_bytes, expected)
        self.assertEqual(recorded_metadata(record), wanted)
        with ZipFile(archive) as zipped:
            files = [info for info in zipped.infolist() if not info.is_dir()]
            self.assertEqual(len(files), len({info.filename for info in files}))
            archive_bytes = {info.filename: zipped.read(info) for info in files}
        self.assertEqual(archive_bytes.pop("specroad/_build.py"), record)
        self.assertEqual(archive_bytes, expected)
        return wanted["build_sha256"]

    def test_module_and_zipapp_have_complete_reference_inventory(self):
        self.build_and_check()

    def test_each_profile_resource_binds_its_actual_bytes(self):
        baseline = self.build_and_check()
        for relative in PROFILE_RESOURCES:
            with self.subTest(resource=relative):
                path = self.package / relative
                before = path.read_bytes()
                try:
                    path.write_bytes(before + b"\n")
                    self.assertNotEqual(self.build_and_check(), baseline)
                finally:
                    path.write_bytes(before)
        self.assertEqual(self.build_and_check(), baseline)

    def test_each_language_resource_binds_its_actual_bytes(self):
        baseline = self.build_and_check()
        for relative in LANGUAGE_RESOURCES:
            with self.subTest(resource=relative):
                path = self.package / relative
                before = path.read_bytes()
                try:
                    path.write_bytes(before + b"\n")
                    self.assertNotEqual(self.build_and_check(), baseline)
                finally:
                    path.write_bytes(before)
        self.assertEqual(self.build_and_check(), baseline)

    def test_same_size_resource_edit_with_restored_mtime_changes_identity(self):
        baseline = self.build_and_check()
        path = self.package / "profile_data/core.json"
        before, metadata = path.read_bytes(), path.stat()
        after = before.replace(b'"core"', b'"cora"', 1)
        self.assertNotEqual(before, after)
        self.assertEqual(len(before), len(after))
        path.write_bytes(after)
        os.utime(path, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
        self.assertNotEqual(self.build_and_check(), baseline)

    def test_json_whitespace_is_bound_even_when_values_are_unchanged(self):
        baseline = self.build_and_check()
        path = self.package / "profile_data/software-de.json"
        before = path.read_bytes()
        path.write_bytes(before + b" \n")
        self.assertEqual(json.loads(path.read_bytes()), json.loads(before))
        self.assertNotEqual(self.build_and_check(), baseline)

    def test_relocated_retimestamped_source_preserves_identity(self):
        baseline = self.build_and_check()
        other = copy_source_fixture(self.root / "relocated", source_root=self.source)
        for path in (other / "specroad").rglob("*"):
            if path.is_file():
                os.utime(path, ns=(946684800000000000, 946684800000000000))
        self.assertEqual(self.build_and_check(other), baseline)

    def test_unregistered_files_do_not_enter_distribution_or_hash(self):
        baseline = self.build_and_check()
        sentinel = self.root / "UNEXPECTED_EXECUTION"
        poison = ("open(" + repr(str(sentinel)) + ", 'w').write('bad')").encode()
        for name in ("unregistered.json", "profile_data/unregistered.json",
                     "language_data/packages/unregistered.json", "host.tmp",
                     "__pycache__/poison.py", "__pycache__/cache.pyc"):
            path = self.package / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(poison)
        self.assertEqual(self.build_and_check(), baseline)
        self.assertFalse(sentinel.exists())

    def test_generated_build_record_is_excluded_and_source_record_is_inert(self):
        baseline = self.build_and_check()
        sentinel = self.root / "BUILD_RECORD_EXECUTED"
        (self.package / "_build.py").write_text(
            "open(" + repr(str(sentinel)) + ", 'w').write('bad')\n", encoding="utf-8")
        self.assertEqual(self.build_and_check(), baseline)
        self.assertFalse(sentinel.exists())

    def test_relative_program_path_remains_part_of_the_hash(self):
        first = self.package / "identity_probe_a.py"
        first.write_bytes(b"VALUE = 1\n")
        baseline = self.build_and_check()
        first.rename(self.package / "identity_probe_b.py")
        self.assertNotEqual(self.build_and_check(), baseline)

    def test_build_keeps_all_source_bytes_unchanged(self):
        before = files_under(self.source)
        self.build_and_check()
        self.assertEqual(files_under(self.source), before)

    def test_reference_inventory_cannot_silently_drop_required_resources(self):
        for relative in SHIPPED_RESOURCES:
            with self.subTest(resource=relative):
                path = self.package / relative
                original = path.read_bytes()
                path.unlink()
                try:
                    with self.assertRaises(FileNotFoundError):
                        reference_payload(self.package, b"launcher")
                finally:
                    path.write_bytes(original)

    def test_actual_hash_rejects_incomplete_or_wrong_byte_expectations(self):
        self.sequence += 1
        module, _ = build_distribution(self.root / ("build-" + str(self.sequence)), self.source)
        actual = recorded_metadata((module / "specroad/_build.py").read_bytes())["build_sha256"]
        complete = reference_payload(self.package, (module / "__main__.py").read_bytes())
        self.assertEqual(reference_digest(complete), actual)
        for relative in SHIPPED_RESOURCES:
            with self.subTest(resource=relative):
                omitted = dict(complete)
                del omitted["specroad/" + relative]
                self.assertNotEqual(reference_digest(omitted), actual)
                corrupted = dict(complete)
                corrupted["specroad/" + relative] += b"\0"
                self.assertNotEqual(reference_digest(corrupted), actual)
