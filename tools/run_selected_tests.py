"""Run explicit whole test files in parallel, without claiming a full regression."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
from verification_support.selected import run_selected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-file", action="append", required=True)
    parser.add_argument("--expected-tests", type=int, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    try:
        result = run_selected(ROOT, args.test_file, args.outdir,
                              expected=args.expected_tests, workers=args.workers)
        print(json.dumps({k:v for k,v in result.items() if k != "observation"}, sort_keys=True))
        return result["exit_code"]
    except (OSError, ValueError):
        print("Selected test gate rejected; no whole-suite pass is asserted.", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
