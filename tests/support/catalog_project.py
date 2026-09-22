"""Small real framework projects for catalog and startup regressions."""
import json
from pathlib import Path
import subprocess
import sys

from verification_support.common import sha256
from verification_support.process_environment import test_environment
from test_verification import manifest

ROOT = Path(__file__).resolve().parents[2]
NATIVE_IDS = ["tests/test_subject.py::test_native",
              "tests/test_subject.py::test_parameter[first]",
              "tests/test_subject.py::test_parameter[second]"]
LEGACY_ID = "test_subject.LegacyTests.test_legacy"
SOURCE = '''import unittest
from pathlib import Path
import pytest

@pytest.fixture(autouse=True)
def body_fixture():
    Path("build/fixture_started").write_text("yes")

class LegacyTests(unittest.TestCase):
    def test_legacy(self):
        Path("build/legacy_started").write_text("yes")

@pytest.mark.parametrize("value", [1, 2], ids=["first", "second"])
def test_parameter(value):
    assert value > 0
    Path("build/parameter_started").write_text("yes")

def test_native():
    Path("build/native_started").write_text("yes")
'''


def make_catalog_project(root, *, ids=None, source=SOURCE):
    root = Path(root)
    for directory in ("src/specroad", "tools", "tests", "verification/requirements",
                      "docs/specification", "build"):
        (root / directory).mkdir(parents=True, exist_ok=True)
    # Byte copies avoid platform-specific fast-copy syscalls under PRoot.
    for path in (ROOT / "tools").rglob("*.py"):
        target = root / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    (root / "src/specroad/__init__.py").write_text("")
    (root / "pyproject.toml").write_text('[tool.pytest.ini_options]\n'
        'pythonpath = ["src", "tests", "tools"]\n'
        'addopts = "-p xdist.plugin -n 4"\n')
    (root / "conftest.py").write_text('pytest_plugins = ("verification_support.pytest_backend",)\n')
    (root / "tests/test_subject.py").write_text(source)
    spec = b"fixture specification\n"
    (root / "docs/specification/SpecRoad_Spezifikation.md").write_bytes(spec)
    spec_hash = sha256(spec)
    data = manifest(state="partial", test_ids=[*NATIVE_IDS, LEGACY_ID] if ids is None else ids)
    data.update(specification_sha256=spec_hash, evidence_kind="specroad-dev-pytest-v1")
    files = {
        "catalog.json": {"catalog_format_version": 1, "specification_sha256": spec_hash,
                         "test_case_ids": ["SR-TC-0001"], "complete": True},
        "fixtures.json": {"fixture_format_version": 1, "fixture_ids": ["temporary-v1"]},
        "requirements/SR-TC-0001.json": data,
    }
    for name, value in files.items():
        (root / "verification" / name).write_text(json.dumps(value))
    return root


def execute(root, script, args=(), *, environment=None):
    import os
    env = test_environment(os.environ)
    env.update(environment or {})
    return subprocess.run([sys.executable, "-I", "-B", str(root / "tools" / script), *args],
        cwd=root, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False)


def check(root, name="preflight.json", *, environment=None):
    output = root / "build" / name
    process = execute(root, "check_test_catalog.py", ["--output", str(output)], environment=environment)
    return process.returncode, json.loads(output.read_text()) if output.exists() else None


def effects(root):
    return sorted(path.name for path in (root / "build").glob("*_started"))
