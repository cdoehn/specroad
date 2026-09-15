"""Run real pytest processes in exclusively owned fixture directories."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from run_tests import test_environment

REPOSITORY = Path(__file__).resolve().parents[2]


def run_pytest_fixture(source, *, workers="0", extra=(), gate=False):
    # No tests are skipped when xdist is absent: explicit parallel runs fail.
    with tempfile.TemporaryDirectory(prefix="specroad-pytest-contract-") as directory:
        root = Path(directory)
        (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        (root / "test_subject.py").write_text(source, encoding="utf-8")
        output = root / "observation.json"
        arguments = [sys.executable, "-I", "-B", str(REPOSITORY / "tools/pytest_entry.py"),
                     "-c", str(root / "pytest.ini"), "--confcutdir", str(root),
                     "-p", "no:cacheprovider", "-p", "no:doctest",
                     "-p", "verification_support.pytest_backend", "--sr-observations", str(output)]
        if workers != "0":
            arguments += ["-p", "xdist.plugin", "-n", str(workers), "--max-worker-restart=0"]
        if gate:
            arguments += ["--sr-gate"]
        arguments += [*extra, str(root / "test_subject.py")]
        completed = subprocess.run(arguments, cwd=root, env=test_environment(os.environ),
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, check=False)
        data = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else None
        return completed.returncode, data
