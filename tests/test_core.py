"""Core behavior: isolated import and a real interpreter prerequisite check."""

from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "src"


class CoreHarness:
    def run_core(self, body, cwd, *, python=None, expose_cwd=False):
        prefix = "import sys;sys.path.insert(0," + repr(str(SOURCE)) + ");\n"
        if expose_cwd:
            prefix += "sys.path.append(" + repr(str(cwd)) + ");\n"
        env = dict(os.environ)
        env["PATH"] = ""
        env.pop("VIRTUAL_ENV", None)
        return subprocess.run(
            [str(python or sys.executable), "-I", "-S", "-B", "-c", prefix + body],
            cwd=cwd, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )

class CoreTests(CoreHarness, unittest.TestCase):
    def test_isolated_standard_library_only_import(self):
        # The child cannot import an installed dependency, even accidentally.
        body = """
class OnlyCoreAndStdlib:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] not in sys.stdlib_module_names | {'specroad'}:
            raise AssertionError('third-party import attempted: ' + fullname)
sys.meta_path.insert(0, OnlyCoreAndStdlib())
import specroad
assert specroad.check_runtime() is None
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_core(body, tmp)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_core_check_has_no_project_side_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = b'{"untouched":true}\n'
            (root / "specroad.json").write_bytes(original)
            result = self.run_core("import specroad;specroad.check_runtime()", root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / "specroad.json").read_bytes(), original)
            self.assertEqual({p.name for p in root.iterdir()}, {"specroad.json"})
