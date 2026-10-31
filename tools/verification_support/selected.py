"""Explicit selected-test gates: observations, never whole-suite evidence."""
import json
import os
from pathlib import Path
import subprocess
import sys
from .identity import source_identity
from .process_environment import test_environment
from .ci_reference import _load_report


from .selected_contract import selected_files, verify_observation, new_report_directory


def run_selected(root, names, outdir, *, expected, workers=4, runner=None, environment=None):
    root = Path(root).absolute()
    names = selected_files(root, names)
    if type(expected) is not int or expected < 1 or type(workers) is not int or workers < 1:
        raise ValueError("Positive selected count and parallel worker count required")
    binding = source_identity(root)
    outdir = new_report_directory(outdir, root)
    observed = outdir / "observations.json"
    command = [sys.executable, "-I", "-B", str(root / "tools/pytest_entry.py"),
               "-o", "addopts=", "--disable-plugin-autoload", "-p", "no:cacheprovider",
               "-p", "no:doctest", "-p", "xdist.plugin", "-n", str(workers),
               "--dist", "worksteal", "--max-worker-restart=0", "--sr-observations", str(observed),
               "--sr-expected-tests", str(expected), *names]
    runner = subprocess.run if runner is None else runner
    errors = []
    try:
        code = runner(command, cwd=root,
                      env=test_environment(os.environ if environment is None else environment),
                      stdin=subprocess.DEVNULL, check=False).returncode
    except OSError:
        code = 4
    observation = None
    try:
        observation = _load_report(observed)
        verify_observation(observation, names, expected)
        if code != 0 or source_identity(root) != binding:
            raise ValueError("Gate failed or source changed")
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        errors.append("nonpassing_or_unbound_selection")
    result = {"format_version": 1, "purpose": "selected_development_tests",
              "test_scope": "selected_files_only", "full_suite_passed": None,
              "selected_passed": not errors, "source_sha256": binding,
              "selected_files": list(names), "expected_tests": expected,
              "workers": workers, "process_exit_code": code, "errors": errors,
              "observation": observation, "exit_code": 0 if not errors else 1}
    with (outdir / "selection.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, allow_nan=False, sort_keys=True)
        stream.write("\n")
    return result
