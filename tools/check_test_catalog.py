"""Bind every catalog reference to real pytest collection; run no test bodies."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for child in ("src", "tests", "tools"):
    path = str(ROOT / child)
    if path not in sys.path:
        sys.path.insert(0, path)
sys.dont_write_bytecode = True
from verification_support.catalog_check import collect_catalog


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = collect_catalog(ROOT, args.output)
        print(json.dumps({k: v for k, v in result.items() if k != "nodeid_to_test_id"}, sort_keys=True))
        return 0 if result["catalog_valid"] else 4
    except (OSError, ValueError):
        print("Catalog preflight could not publish a fresh report.", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
