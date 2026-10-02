"""Run both complete laptop gates in order; commit orchestration stays with Apply."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    checks = []
    for mode, workers in (("parallel", "4"), ("serial", "0")):
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
