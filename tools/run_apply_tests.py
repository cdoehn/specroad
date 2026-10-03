"""Run full parallel Apply tests, adding serial tests for the final bundle state."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final-bundle-state", action="store_true")
    args = parser.parse_args(argv)
    modes = [("parallel", "4")]
    if args.final_bundle_state:
        modes.append(("serial", "0"))
    checks = []
    for mode, workers in modes:
        command = [sys.executable, "-I", "-B", str(ROOT / "tools/run_tests.py"),
                   "--workers", workers]
        try:
            code = subprocess.run(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                                  check=False).returncode
        except OSError:
            code = 4
        checks.append({"mode": mode, "exit_code": code})
    passed = all(check["exit_code"] == 0 for check in checks)
    print(json.dumps({"checks": checks, "suite_passed": passed}, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
