"""CI reference orchestration; no framework scheduler and no CLI parsing."""

import json
import os
from pathlib import Path
import stat
import subprocess
import sys

from compare_test_runs import compare_reports
from .process_environment import test_environment
from .execution_policy import DEFAULT_WORKERS

ROOT = Path(__file__).resolve().parents[2]


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate report key")
        result[key] = value
    return result


def _load_report(path):
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("CI report must be a regular file")
    def invalid_number(value):
        raise ValueError("Non-finite report value")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object,
                      parse_constant=invalid_number)


def run_reference(outdir, *, workers=DEFAULT_WORKERS, environment=None, runner=None):
    """Run two independent whole-suite gates, never retry or hide failures.

    The environment flag prevents an accidental local reference run. It is not
    authentication. Evidence is always created in a new caller-owned directory.
    Tests inject a runner; production defaults to the real subprocess boundary.
    """
    environment = dict(os.environ if environment is None else environment)
    if environment.get("GITHUB_ACTIONS") != "true":
        raise ValueError("Full serial references are reserved for GitHub Actions")
    if type(workers) is not int or workers <= 0:
        raise ValueError("The parallel reference needs a positive worker count")
    outdir = Path(outdir).absolute()
    outdir.mkdir(parents=True, exist_ok=False)
    runner = subprocess.run if runner is None else runner
    checks = []
    paths = []
    for name, count, seed in (("parallel", workers, "117"), ("serial", 0, "901")):
        path = outdir / (name + "-evidence.json")
        paths.append(path)
        env = test_environment(environment)
        env["PYTHONHASHSEED"] = seed
        command = [sys.executable, "-I", "-B", str(ROOT / "tools/run_tests.py"),
                   "--workers", str(count), "--evidence", str(path)]
        try:
            code = runner(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                          check=False).returncode
        except OSError:
            code = 4
        checks.append({"mode": name, "workers": count, "exit_code": code})
    comparison = None
    errors = []
    if all(check["exit_code"] == 0 for check in checks):
        try:
            comparison = compare_reports([_load_report(path) for path in paths])
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
            errors.append("invalid_or_non_equivalent_evidence")
    else:
        errors.append("gate_failed")
    result = {"format_version": 1, "checks": checks, "comparison": comparison,
              "errors": errors, "suite_passed": comparison is not None,
              "exit_code": 0 if comparison is not None else 1}
    # Only this controller publishes the summary, without replacing any artifact.
    with (outdir / "summary.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, sort_keys=True, allow_nan=False)
        stream.write("\n")
    return result

