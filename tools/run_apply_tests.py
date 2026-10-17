"""Run the next stable test group after each successful Apply commit."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
from verification_support.apply_rotation import run_apply_partition


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    # Compatibility only: the last commit follows the same rotation.
    parser.add_argument("--final-bundle-state", action="store_true")
    parser.add_argument("--outdir", type=Path)
    args = parser.parse_args(argv)
    outdir = args.outdir or Path(tempfile.mkdtemp(prefix="specroad-apply-tests-")) / "gate"
    try:
        result = run_apply_partition(ROOT, outdir)
        print(json.dumps({**{k: v for k, v in result.items() if k != "nodeid_to_test_id"},
                          "report_directory": str(outdir)}, sort_keys=True))
        return result["exit_code"]
    except (OSError, ValueError, TypeError, KeyError):
        # Preflight failures have no accepted policy binding; retain the
        # existing machine-readable error envelope for callers.
        print(json.dumps({"purpose": "alternating_apply_tests", "selected_passed": False,
                          "full_suite_passed": None, "exit_code": 4,
                          "error": "apply_partition_rejected", "report_directory": str(outdir)},
                         sort_keys=True))
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
