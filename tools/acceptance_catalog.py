"""Build a passive acceptance inventory from an existing native collection."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.dont_write_bytecode = True
from verification_support.acceptance import assemble_acceptance
from verification_support.common import read_object
from verification_support.publication import evidence_target, publish_report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collection', type=Path, required=True)
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('--binding', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if (args.evidence is None) != (args.binding is None):
        parser.error('Evidence and its explicitly selected run binding must be supplied together')
    try:
        target = evidence_target(args.output, ROOT)
        collection = read_object(args.collection)[0]
        evidence = read_object(args.evidence)[0] if args.evidence is not None else None
        binding = read_object(args.binding)[0] if args.binding is not None else None
        report = assemble_acceptance(ROOT, collection, binding=binding, report=evidence)
        publish_report(target, ROOT, report)
        print(json.dumps({'run_status': report['run_status'],
                          'mapped_requirements': report['mapped_requirements'],
                          'release_approved': False}, sort_keys=True))
        return 0 if report['run_status'] in ('current', 'not_supplied') else 1
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        return 4


if __name__ == '__main__':
    raise SystemExit(main())
