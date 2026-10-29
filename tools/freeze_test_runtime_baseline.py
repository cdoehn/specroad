"""Freeze one explicitly measured full suite; never run tests or replace a baseline."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
from verification_support.runtime_baseline import BASELINE, freeze


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measurement", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        value = freeze(args.measurement, ROOT)
    except (OSError, ValueError, TypeError, KeyError):
        print("Baseline was not published; existing data remains unchanged.", file=sys.stderr)
        return 4
    print(str(ROOT / BASELINE) + ": " + str(len(value["excluded_test_ids"]))
          + " of " + str(len(value["tests"])) + " measured tests excluded from automatic Apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
