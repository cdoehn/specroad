"""Run one full parallel Apply test suite for every bundle state."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    # Retained for existing entrypoints; the final state uses the same parallel gate.
    parser.add_argument("--final-bundle-state", action="store_true")
    parser.parse_args(argv)
    command = [sys.executable, "-I", "-B", str(ROOT / "tools/run_tests.py"),
               "--workers", "4"]
    try:
        code = subprocess.run(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                              check=False).returncode
    except OSError:
        code = 4
    checks = [{"mode": "parallel", "exit_code": code}]
    passed = code == 0
    print(json.dumps({"checks": checks, "suite_passed": passed}, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
