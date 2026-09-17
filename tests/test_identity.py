"""Version behavior and data identity; no human presentation assertions."""

from pathlib import Path
import hashlib
import io
import json
import platform
import sys
import tempfile
import unittest
from unittest.mock import patch

from specroad import __version__
from specroad.cli import main
from specroad.cli.application import dispatch_result
from specroad.cli.results import thaw
from specroad.runtime.identity import version_info
from support.portable import build_distribution, copy_source_fixture, files_under
from support.processes import run_python, run_core


class IdentityWorkTests(unittest.TestCase):
    def test_runtime_is_the_executing_interpreter(self):
        payload = version_info()
        self.assertEqual(payload["program_version"], __version__)
        self.assertEqual(payload["runtime"]["python_version"], platform.python_version())
        self.assertEqual(payload["runtime"]["implementation"], sys.implementation.name)
        self.assertEqual(payload["python_support"]["minimum_minor"], "3.10")

    def test_version_json_is_a_real_command_result(self):
        output = io.StringIO()
        self.assertEqual(main(["version", "--format", "json"], stdout=output, stderr=io.StringIO()), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["command"], "version")
        self.assertEqual(result["result"], version_info())
        self.assertIsNone(result["project"])

    def test_unsealed_source_does_not_invent_a_hash(self):
        result = version_info()
        self.assertIsNone(result["build_id"])
        self.assertIsNone(result["build_sha256"])
        self.assertEqual(result["build_identity_status"], "unrecorded")

    def test_version_needs_no_project_cwd_or_git(self):
        with patch("pathlib.Path.cwd", side_effect=AssertionError("project discovery")), \
             patch("subprocess.Popen", side_effect=AssertionError("external process")):
            outcome = dispatch_result(["version", "--format", "json"])
        self.assertEqual(outcome.exit_code, 0)
        self.assertIsNone(outcome.project)

    def test_only_implemented_formats_and_schemas_are_advertised(self):
        from specroad.cli.results import FORMAT_VERSION
        result = version_info()
        self.assertEqual(result["supported_schema_versions"], [])
        self.assertEqual(result["supported_output_format_versions"]["json"], [FORMAT_VERSION])
        self.assertEqual(result["supported_output_format_versions"]["sarif"], ["2.1.0"])

    def test_portable_module_and_zipapp_share_the_recorded_payload_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module, archive = build_distribution(root / "build")
            before = files_under(root / "build")
            values = []
            for entry in (module, archive):
                completed = run_python(["-I", "-S", "-B", str(entry), "version", "--format", "json"], root, capture=True)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                values.append(json.loads(completed.stdout)["result"])
            self.assertEqual(values[0]["distribution_kind"], "module")
            self.assertEqual(values[1]["distribution_kind"], "zipapp")
            self.assertEqual(values[0]["build_sha256"], values[1]["build_sha256"])
            self.assertRegex(values[0]["build_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(before, files_under(root / "build"))

    def test_version_is_read_only_in_a_poisoned_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "specroad.json").write_bytes(b"not valid JSON")
            (root / "_build.py").write_text("raise RuntimeError('must not load')")
            before = files_under(root)
            child = run_core("from specroad.cli import main;sys.exit(main(['version','--format','json']))", root, capture=True)
            self.assertEqual(child.returncode, 0, child.stderr)
            self.assertEqual(json.loads(child.stdout)["result"]["build_identity_status"], "unrecorded")
            self.assertEqual(before, files_under(root))

    def test_invalid_version_options_do_not_succeed(self):
        for args in (["version", "--project", "."], ["version", "--format", "sarif"], ["version", "extra"]):
            with self.subTest(args=args):
                self.assertEqual(dispatch_result(args).exit_code, 2)


class IdentityRobustnessTests(unittest.TestCase):
    def test_declaration_and_actual_verification_are_distinct(self):
        result = version_info()
        support = result["python_support"]
        self.assertEqual(support["declared_minors"], ["3.10", "3.11", "3.12", "3.13", "3.14"])
        self.assertEqual(support["maximum_declared_minor"], "3.14")
        self.assertEqual(support["tested_minors"], [])
        self.assertIsNone(support["maximum_tested_minor"])
        self.assertEqual(support["fully_verified_minors"], [])
        self.assertEqual(support["evidence_refs"], [])
        self.assertFalse(result["release_approved"])

    def test_invalid_bundled_records_fail_without_exposing_data(self):
        from specroad import _build
        valid = {"format_version": 1, "hash_algorithm": "specroad-dev-payload-v1", "build_sha256": "a" * 64}
        records = [[], {}, {**valid, "format_version": True}, {**valid, "format_version": 2},
                   {**valid, "build_sha256": "short"}, {**valid, "build_sha256": "A" * 64},
                   {**valid, "hash_algorithm": "future"}, {**valid, "tested_minors": ["3.14"]},
                   {**valid, "secret": "PRIVATE-BUILD-INPUT"}]
        for record in records:
            with self.subTest(record=record), patch.object(_build, "BUILD_METADATA", record):
                outcome = dispatch_result(["version"])
                self.assertEqual(outcome.exit_code, 5)
                self.assertIsNone(outcome.result)
                # Machine error fields cannot leak untrusted build values.
                self.assertNotIn("PRIVATE-BUILD-INPUT", json.dumps(outcome.as_dict()))

    def test_valid_record_is_not_promoted_to_release_evidence(self):
        from specroad import _build
        record = {"format_version": 1, "hash_algorithm": "specroad-dev-payload-v1", "build_sha256": "a" * 64}
        with patch.object(_build, "BUILD_METADATA", record):
            payload = version_info()
        self.assertEqual(payload["build_sha256"], "a" * 64)
        self.assertEqual(payload["build_id"], "dev-" + "a" * 12)
        self.assertEqual(payload["python_support"]["tested_minors"], [])
        self.assertFalse(payload["release_approved"])

    def test_payload_hash_binds_program_bytes_not_paths_or_timestamps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = copy_source_fixture(root / "source")
            module, archive = build_distribution(root / "first", source)
            manifest = {"specroad/" + name: hashlib.sha256(data).hexdigest()
                        for name, data in files_under(source / "specroad").items()
                        if (name.endswith(".py") or name in {"language_data/registry.txt", "language_data/snapshot.json",
                            "language_data/packages.json", "language_data/minimum_corpus.json",
                            "language_data/packages/de.json", "language_data/packages/en.json", "language_data/packages/hi.json", "language_data/packages/id.json", "language_data/packages/pt.json", "language_data/packages/es.json", "language_data/packages/ru.json", "language_data/packages/ja.json", "language_data/packages/zh-Hans.json"}) and name != "_build.py"}
            manifest["__main__.py"] = hashlib.sha256((module / "__main__.py").read_bytes()).hexdigest()
            expected = hashlib.sha256(b"specroad-dev-payload-v1\0" + json.dumps(
                manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()
            result = run_python(["-I", "-S", "-B", str(archive), "version", "--format", "json"], root, capture=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["result"]["build_sha256"], expected)
            _, second = build_distribution(root / "second", source)
            repeated = run_python(["-I", "-S", "-B", str(second), "version", "--format", "json"], root, capture=True)
            self.assertEqual(repeated.returncode, 0, repeated.stderr)
            self.assertEqual(json.loads(repeated.stdout)["result"]["build_sha256"], expected)

    def test_changing_payload_changes_identity_without_executing_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = copy_source_fixture(root / "source")
            _, first = build_distribution(root / "first", source)
            sentinel = root / "FOREIGN_CODE_EXECUTED"
            (source / "specroad" / "never_imported.py").write_text("open(" + repr(str(sentinel)) + ", 'w').write('bad')")
            _, second = build_distribution(root / "second", source)
            hashes = []
            for archive in (first, second):
                result = run_python(["-I", "-S", "-B", str(archive), "version", "--format", "json"], root, capture=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                hashes.append(json.loads(result.stdout)["result"]["build_sha256"])
            self.assertNotEqual(*hashes)
            self.assertFalse(sentinel.exists())

    def test_moving_distribution_preserves_build_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, archive = build_distribution(root / "before")
            first = run_python(["-I", "-S", "-B", str(archive), "version", "--format", "json"], root, capture=True)
            (root / "before").rename(root / "after")
            second = run_python(["-I", "-S", "-B", str(root / "after/specroad.pyz"), "version", "--format", "json"], root, capture=True)
            for result in (first, second):
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(first.stdout)["result"], json.loads(second.stdout)["result"])

    def test_environment_cannot_assert_a_build_or_test_matrix(self):
        import os
        before = version_info()
        with patch.dict(os.environ, {"SPECROAD_BUILD_SHA256": "f" * 64, "SPECROAD_TESTED_PYTHON": "3.99",
                                     "GIT_COMMIT": "f" * 40, "SECRET": "PRIVATE-ENVIRONMENT"}):
            after = version_info()
        self.assertEqual(after, before)
        self.assertNotIn("PRIVATE-ENVIRONMENT", json.dumps(after))

    def test_returned_data_cannot_mutate_later_identity_results(self):
        first = version_info()
        first["python_support"]["declared_minors"].clear()
        first["supported_output_format_versions"]["json"].append("fake")
        second = version_info()
        self.assertEqual(len(second["python_support"]["declared_minors"]), 5)
        self.assertNotIn("fake", second["supported_output_format_versions"]["json"])

    def test_display_policy_does_not_change_version_identity(self):
        plain = dispatch_result(["version"])
        quiet = dispatch_result(["version", "--quiet", "--no-color", "--format", "json"])
        self.assertEqual(thaw(plain.result), thaw(quiet.result))
        self.assertEqual(plain.exit_code, quiet.exit_code)

    def test_bootstrap_reads_no_model_or_distribution_tree(self):
        body = r"""
import os
from pathlib import Path
root = str(Path.cwd())
def guard(event, args):
    if event in {"subprocess.Popen", "os.system", "os.posix_spawn", "socket.connect", "socket.getaddrinfo", "os.scandir", "os.listdir"}:
        raise AssertionError("forbidden effect: " + event)
    if event == "open":
        path, mode, flags = args
        if isinstance(path, str) and os.path.abspath(path).startswith(root + os.sep):
            raise AssertionError("project read")
        if (isinstance(mode, str) and any(char in mode for char in "wax+")) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
            raise AssertionError("write")
# Preload ordinary import metadata, not project data; audit covers the command.
from specroad.cli.application import dispatch_result
from specroad.runtime.identity import version_info
sys.addaudithook(guard)
assert dispatch_result(["version"]).exit_code == 0
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = run_core(body, tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
