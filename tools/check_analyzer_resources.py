"""Validate the current resource obligation without running a benchmark."""
import argparse
import ast
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'src'))
from analyzer_benchmark.acceptance import evaluate
from build_core import build_core


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--commit-id')
    parser.add_argument('--final', action='store_true')
    args = parser.parse_args(argv)
    try:
        with tempfile.TemporaryDirectory(prefix='specroad-resource-binding-') as scratch:
            module, _ = build_core(ROOT / 'src', Path(scratch) / 'core')
            node = ast.parse((module / 'specroad/_build.py').read_bytes()).body[-1]
            build = ast.literal_eval(node.value)['build_sha256']
        result = evaluate(ROOT, expected_build=build, commit_id=args.commit_id, final=args.final)
    except (OSError, ValueError, TypeError, KeyError, IndexError, EOFError, RecursionError):
        result = {'status': 'blocked', 'reason': 'invalid_resource_acceptance_inputs',
                  'final_obligation': 'pending', 'release_approved': False,
                  'human_corpus_review_completed': False}
    print('SPECROAD_RESOURCE_OBLIGATION ' + json.dumps(result, sort_keys=True))
    return 0 if result['status'] in ('passed', 'deferred') else 2


if __name__ == '__main__':
    raise SystemExit(main())
