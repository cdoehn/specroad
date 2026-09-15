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
