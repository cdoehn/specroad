"""Explicit selected-test gates: observations, never whole-suite evidence."""
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
from .identity import source_identity
from .process_environment import test_environment
from .ci_reference import _load_report


def selected_files(root, names):
    root = Path(root).absolute()
    names = tuple(names)
    if not names or any(type(n) is not str for n in names) or len(set(names)) != len(names):
        raise ValueError("Select distinct test files explicitly")
    for name in names:
        path = PurePosixPath(name)
        if (path.is_absolute() or path.as_posix() != name or len(path.parts) < 2
                or path.parts[0] != "tests" or any(p in (".", "..") for p in path.parts)
                or "\\" in name or "::" in name or not path.name.startswith("test_")
                or not path.name.endswith(".py")):
            raise ValueError("Only explicit repository-relative test files are accepted")
        candidate = root
        for i, part in enumerate(path.parts):
            candidate /= part
            mode = candidate.lstat().st_mode
            if not (stat.S_ISREG(mode) if i == len(path.parts)-1 else stat.S_ISDIR(mode)):
                raise ValueError("Linked/special test paths are not allowed")
    return names


def verify_observation(value, names, expected):
    if type(value) is not dict:
        raise ValueError("Missing selected-run observation")
    ids = value.get("nodeids", [])
    aliases = value.get("nodeid_to_test_id", {})
    outcomes = value.get("test_outcomes", {})
    counts = value.get("worker_test_counts", {})
    if (type(ids) is not list or not ids or any(type(n) is not str for n in ids)
            or len(ids) != expected or len(set(ids)) != expected
            or {n.split("::", 1)[0] for n in ids} != set(names)
            or set(aliases) != set(ids) or len(set(aliases.values())) != expected
            or set(outcomes) != set(aliases.values())
            or any(v != "passed" for v in outcomes.values())
            or value.get("suite_passed") is not True or value.get("errors") != []
            or value.get("tests_run") != expected or value.get("pytest_exit_code") != 0
            or not counts or any(type(v) is not int or v < 0 for v in counts.values())
            or sum(counts.values()) != expected):
        raise ValueError("Incomplete, unexpected or nonpassing selected tests")


def run_selected(root, names, outdir, *, expected, workers=4, runner=None, environment=None):
    root = Path(root).absolute()
    names = selected_files(root, names)
    if type(expected) is not int or expected < 1 or type(workers) is not int or workers < 1:
        raise ValueError("Positive selected count and parallel worker count required")
    outdir = Path(outdir).absolute()
    try:
        relative = outdir.relative_to(root)
    except ValueError:
        relative = None
    if relative is not None and (not relative.parts or relative.parts[0] not in ("build", "dist")):
        raise ValueError("Test reports must be outside source inputs")
    binding = source_identity(root)
    outdir.mkdir(parents=True, exist_ok=False)
    observed = outdir / "observations.json"
    command = [sys.executable, "-I", "-B", str(root / "tools/pytest_entry.py"),
               "-o", "addopts=", "--disable-plugin-autoload", "-p", "no:cacheprovider",
               "-p", "no:doctest", "-p", "xdist.plugin", "-n", str(workers),
               "--dist", "load", "--max-worker-restart=0", "--sr-observations", str(observed),
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
