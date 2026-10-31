"""Core behavior: isolated import and a real interpreter prerequisite check."""

from pathlib import Path
import os
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "src"


from support.import_guards import CORE_STDLIB_IMPORT_GUARD
from support import run_core
from support.virtualenvs import create_no_pip_venv


class CoreHarness:
    def run_core(self, body, cwd, *, python=None, expose_cwd=False):
        return run_core(body, cwd, python=python, expose_cwd=expose_cwd)


class CoreTests(CoreHarness, unittest.TestCase):
    def test_isolated_standard_library_only_import(self):
        # The child cannot import an installed dependency, even accidentally.
        body = CORE_STDLIB_IMPORT_GUARD + """
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


class CoreRobustnessTests(CoreHarness, unittest.TestCase):
    def test_old_python_is_rejected_by_runtime_check(self):
        body = """
import specroad
sys.version_info = (3, 9, 99, 'final', 0)
try:
    specroad.check_runtime()
except specroad.UnsupportedRuntimeError:
    pass
else:
    raise AssertionError('unsupported runtime accepted')
"""
        with tempfile.TemporaryDirectory() as tmp:
            r = self.run_core(body, tmp)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_non_cpython_is_rejected_by_runtime_check(self):
        body = """
import specroad
from types import SimpleNamespace
sys.implementation = SimpleNamespace(name='pypy')
try:
    specroad.check_runtime()
except specroad.UnsupportedRuntimeError:
    pass
else:
    raise AssertionError('unsupported interpreter accepted')
"""
        with tempfile.TemporaryDirectory() as tmp:
            r = self.run_core(body, tmp)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_unsupported_runtime_is_rejected_during_import(self):
        body = """
sys.version_info = (3, 9, 99, 'final', 0)
try:
    import specroad
except RuntimeError:
    pass
else:
    raise AssertionError('bootstrap accepted an unsupported runtime')
"""
        with tempfile.TemporaryDirectory() as tmp:
            r = self.run_core(body, tmp)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_poisoned_project_directory_cannot_supply_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sentinel = root / 'FOREIGN_CODE_EXECUTED'
            poison = "open(" + repr(str(sentinel)) + ", 'w').write('executed')\nraise RuntimeError('foreign module')\n"
            for module in ('typing', 'json', 'platform', 'rich', 'numpy', 'py3langid',
                           'setuptools', 'pip', 'sitecustomize'):
                (root / (module + '.py')).write_text(poison)
            (root / 'specroad').mkdir()
            (root / 'specroad' / '__init__.py').write_text(poison)
            before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            r = self.run_core("import specroad;specroad.check_runtime()", root, expose_cwd=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse(sentinel.exists())
            self.assertEqual(before, {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_no_installer_shell_network_or_write_during_import(self):
        body = """
import os

def deny_external_effects(event, args):
    if event in {'subprocess.Popen', 'os.system', 'os.posix_spawn', 'socket.connect',
                 'socket.getaddrinfo', 'os.mkdir', 'os.remove', 'os.rename'}:
        raise AssertionError('unexpected effect: ' + event)
    if event == 'open':
        mode = args[1]
        flags = args[2]
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        ):
            raise AssertionError('unexpected file write')
sys.addaudithook(deny_external_effects)
import specroad
assert specroad.check_runtime() is None
"""
        with tempfile.TemporaryDirectory() as tmp:
            r = self.run_core(body, tmp)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_unactivated_virtual_environment_without_pip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            python = create_no_pip_venv(root / 'env')
            project = root / 'project'
            project.mkdir()
            r = self.run_core("import specroad;specroad.check_runtime()", project, python=python)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(list(project.iterdir()), [])
