"""Durable runtime measurement: all tests, arbitrary groups, or missing tests only."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'tools') not in sys.path:
    sys.path.insert(0, str(ROOT / 'tools'))
from verification_support.identity import source_identity
from verification_support.publication import publish_report
from verification_support.runtime_runner import run_measurement
from verification_support.runtime_store import read_store, measurement_from_store


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--journal', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--all', action='store_true')
    mode.add_argument('--remaining', action='store_true')
    mode.add_argument('--status', action='store_true')
    mode.add_argument('--export', type=Path)
    parser.add_argument('--test-file', action='append', default=[])
    parser.add_argument('--test-id', action='append', default=[])
    parser.add_argument('--selection-file', action='append', default=[], type=Path)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args(argv)
    explicit = bool(args.test_file or args.test_id or args.selection_file)
    if (args.status or args.export) and explicit:
        parser.error('Status/export cannot start a measurement')
    try:
        journal = args.journal.absolute()
        if args.export:
            value = measurement_from_store(journal, ROOT, source_identity(ROOT))
            publish_report(args.export.absolute(), ROOT, value)
            print(json.dumps({'coverage_complete': True, 'measured_tests': len(value['tests']),
                              'full_suite_passed': None}))
            return 0
        code = 0
        if not args.status:
            code = run_measurement(ROOT, journal, args.workers, all_tests=args.all,
                remaining=args.remaining, files=args.test_file, identities=args.test_id,
                selections=args.selection_file)
        meta, complete, info = read_store(journal, ROOT)
        missing = {n: i for n, i in meta['pairs'].items() if n not in complete}
        print(json.dumps({'measured_tests': len(complete), 'expected_tests': len(meta['pairs']),
            'missing_tests': len(missing), 'missing_test_ids': sorted(missing.values()),
            'source_matches': source_identity(ROOT) == meta['source_sha256'],
            'full_suite_passed': None, **info}, sort_keys=True))
        return code
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
        print('Timing measurement failed; saved records remain: ' + str(error), file=sys.stderr)
        return 4


if __name__ == '__main__':
    raise SystemExit(main())
