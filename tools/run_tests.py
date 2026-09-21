"""Run pytest through a full-catalog gate, without scheduling tests ourselves."""

import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
# -I deliberately excludes script-directory imports; add only this trusted root.
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
from verification_support.process_environment import test_environment
from verification_support.execution_policy import DEFAULT_WORKERS


def worker_count(value):
    if value == "auto":
        return value
    try:
        number = int(value)
    except (ValueError, TypeError) as error:
        raise argparse.ArgumentTypeError("Workers must be auto or a nonnegative integer") from error
    if number < 0:
        raise argparse.ArgumentTypeError("Workers must be auto or a nonnegative integer")
    return str(number)


def pytest_arguments(args):
    arguments = ["-o", "addopts=", "--disable-plugin-autoload",
                 "-p", "no:cacheprovider", "-p", "no:doctest"]
    if args.workers != "0":
        arguments += ["-p", "xdist.plugin", "-n", args.workers,
                      "--dist", args.dist, "--max-worker-restart=0"]
    arguments += ["--sr-gate", str(ROOT / "tests")]
    for option, value in (("--sr-evidence", args.evidence),
                          ("--sr-observations", args.observations),
                          ("--sr-expected-tests", args.expected_tests)):
        if value is not None:
            arguments += [option, str(value)]
    return arguments


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", "-n", type=worker_count, default=str(DEFAULT_WORKERS))
    parser.add_argument("--dist", choices=("load", "worksteal", "loadscope", "loadfile"), default="load")
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--expected-tests", type=int)
    args = parser.parse_args(argv)
    if args.expected_tests is not None and args.expected_tests <= 0:
        parser.error("Expected tests must be positive")
    # Publication paths are interpreted relative to the caller, not a later cwd.
    for name in ("evidence", "observations"):
        value = getattr(args, name)
        if value is not None:
            setattr(args, name, value.absolute())
    environment = test_environment(os.environ)
    auto = environment.get("PYTEST_XDIST_AUTO_NUM_WORKERS")
    if args.workers == "auto" and auto is not None and (not auto.isdecimal() or int(auto) <= 0):
        parser.error("PYTEST_XDIST_AUTO_NUM_WORKERS must be a positive integer")
    command = [sys.executable, "-I", "-B", str(ROOT / "tools/pytest_entry.py"), *pytest_arguments(args)]
    try:
        return subprocess.run(command, cwd=ROOT, env=environment,
                              stdin=subprocess.DEVNULL, check=False).returncode
    except OSError:
        print("Could not start the development test interpreter.", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
