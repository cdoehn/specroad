"""GitHub-only full reference checks; xdist remains the sole test scheduler."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
from compare_test_runs import compare_reports
from verification_support.process_environment import test_environment


def run_reference(outdir, *, workers=4, environment=None, runner=None):
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
    if all(check["exit_code"] == 0 for check in checks):
        try:
            comparison = compare_reports([json.loads(path.read_text(encoding="utf-8")) for path in paths])
        except (OSError, ValueError, TypeError, KeyError):
            pass
    return {"format_version": 1, "checks": checks, "comparison": comparison,
            "suite_passed": comparison is not None,
            "exit_code": 0 if comparison is not None else 1}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    try:
        result = run_reference(args.outdir, workers=args.workers)
        print(json.dumps(result, sort_keys=True))
        return result["exit_code"]
    except (ValueError, OSError):
        print("CI reference could not start; existing files remain unchanged.", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
