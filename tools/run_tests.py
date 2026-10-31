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
from verification_support.execution_policy import DEFAULT_WORKERS, DEFAULT_DISTRIBUTION
from verification_support.runtime_runner import prepare_request


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
                          ("--sr-expected-tests", args.expected_tests),
                          ("--sr-runtimes", getattr(args, "runtime_measurement", None)),
                          ("--sr-runtime-journal", getattr(args, "runtime_journal", None)),
                          ("--sr-timing-request", getattr(args, "timing_request", None))):
        if value is not None:
            arguments += [option, str(value)]
    return arguments


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", "-n", type=worker_count, default=str(DEFAULT_WORKERS))
    parser.add_argument("--dist", choices=("load", "worksteal", "loadscope", "loadfile"), default=DEFAULT_DISTRIBUTION)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--expected-tests", type=int)
    parser.add_argument("--runtime-measurement", type=Path)
    parser.add_argument("--runtime-journal", type=Path)
    args = parser.parse_args(argv)
    if args.expected_tests is not None and args.expected_tests <= 0:
        parser.error("Expected tests must be positive")
    # Publication paths are interpreted relative to the caller, not a later cwd.
    if args.runtime_measurement is not None and args.workers in ("0", "1"):
        parser.error("One-time calibration requires parallel workers")
    for name in ("evidence", "observations", "runtime_measurement", "runtime_journal"):
        value = getattr(args, name)
        if value is not None:
            setattr(args, name, value.absolute())
    environment = test_environment(os.environ)
    auto = environment.get("PYTEST_XDIST_AUTO_NUM_WORKERS")
    if args.workers == "auto" and auto is not None and (not auto.isdecimal() or int(auto) <= 0):
        parser.error("PYTEST_XDIST_AUTO_NUM_WORKERS must be a positive integer")
    if args.runtime_journal is not None and args.runtime_measurement is None:
        parser.error("Use measure_test_runtimes.py for selected/recovery measurements")
    if args.runtime_measurement is not None:
        from verification_support.publication import evidence_target
        try:
            evidence_target(args.runtime_measurement, ROOT)
            if args.workers == "auto":
                parser.error("Calibration needs an explicit parallel worker count")
            args.runtime_journal = args.runtime_journal or args.runtime_measurement.with_suffix(".sqlite3")
            if args.runtime_journal == args.runtime_measurement:
                parser.error("Measurement and timing journal need separate paths")
            args.timing_request, request = prepare_request(ROOT, args.runtime_journal,
                int(args.workers), all_tests=True, keep_complete=True)
            if args.expected_tests is None:
                args.expected_tests = len(request["selected"])
        except (OSError, ValueError) as error:
            parser.error(str(error))
    command = [sys.executable, "-I", "-B", str(ROOT / "tools/pytest_entry.py"), *pytest_arguments(args)]
    try:
        return subprocess.run(command, cwd=ROOT, env=environment,
                              stdin=subprocess.DEVNULL, check=False).returncode
    except OSError:
        print("Could not start the development test interpreter.", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
