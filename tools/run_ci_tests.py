"""Run full parallel/serial references in GitHub CI, never in local bundles."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
from verification_support.ci_reference import run_reference
from verification_support.execution_policy import DEFAULT_WORKERS


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
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
