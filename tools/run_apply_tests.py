"""Run the required rotation/commit-test union before the next Apply commit."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
from verification_support.apply_rotation import run_apply_partition
from verification_support.host_execution import add_worker_limit, DEFAULT_WORKER_LIMIT


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    # Compatibility only: the last commit follows the same rotation.
    parser.add_argument("--final-bundle-state", action="store_true")
    parser.add_argument("--outdir", type=Path)
    parser.add_argument("--test-plan", type=Path)
    parser.add_argument("--commit-id")
    targets = parser.add_mutually_exclusive_group()
    targets.add_argument('--hosts', type=Path, help='Local host pool configuration (Apply only)')
    targets.add_argument('--local', action='store_true', help='Use the existing local runner without a host pool')
    add_worker_limit(parser)
    args = parser.parse_args(argv)
    outdir = args.outdir or Path(tempfile.mkdtemp(prefix="specroad-apply-tests-")) / "gate"
    try:
        options = {} if args.test_plan is None and args.commit_id is None else {
            'test_plan': args.test_plan, 'commit_id': args.commit_id}
        if args.worker_limit != DEFAULT_WORKER_LIMIT:
            options["worker_limit"] = args.worker_limit
        if not args.local and (args.hosts is not None or os.environ.get('SPECROAD_NESTED_TEST_RUN') != '1'):
            path = Path(args.hosts or os.environ.get('SPECROAD_TEST_HOSTS') or Path.home() / '.config/specroad/test-hosts.json').expanduser()
            if args.hosts is not None or path.exists():
                options['hosts'] = path
        result = run_apply_partition(ROOT, outdir, **options)
        print(json.dumps({**{k: v for k, v in result.items() if k not in (
                              "nodeid_to_test_id", "selection_binding", "runtime_filter", "required_tests")},
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
