"""Read and verify one completed Apply gate; never start tests or make commits."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from verification_support.apply_gate import verify_commit_gate
from verification_support.commit_tests import read_object


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gate', type=Path, required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--head', required=True)
    parser.add_argument('--test-plan', type=Path, required=True)
    args = parser.parse_args(argv)
    _, plan = read_object(args.test_plan)
    proof = verify_commit_gate(ROOT, args.gate, source=args.source, head=args.head, test_plan=plan)
    print(json.dumps(proof, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
