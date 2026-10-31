"""Plan, execute and aggregate manually dispatched duration-weighted CI jobs."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from verification_support.ci_packages import DEFAULT_RULES, matrix
from verification_support.ci_reference import _load_report
from verification_support.ci_package_runtime import (
    aggregate, export_estimates, plan_run, preserve_history, run_package, write_json,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='action', required=True)
    export = subs.add_parser('export')
    export.add_argument('--database', type=Path, required=True)
    export.add_argument('--catalog', type=Path, required=True)
    export.add_argument('--output', type=Path, required=True)
    plan = subs.add_parser('plan')
    plan.add_argument('--outdir', type=Path, required=True)
    plan.add_argument('--estimates', type=Path, default=ROOT/'verification/ci_runtime_estimates.json')
    plan.add_argument('--target-minutes', type=int, default=180)
    plan.add_argument('--duration-factor', type=float, default=1.5)
    combine = subs.add_parser('matrix')
    combine.add_argument('--plans', type=Path, required=True)
    run = subs.add_parser('run')
    run.add_argument('--plan', type=Path, required=True)
    run.add_argument('--shard', type=int, required=True)
    run.add_argument('--outdir', type=Path, required=True)
    merge = subs.add_parser('aggregate')
    merge.add_argument('--plan', type=Path, required=True)
    merge.add_argument('--receipts', type=Path, required=True)
    merge.add_argument('--outdir', type=Path, required=True)
    save = subs.add_parser('preserve-history')
    save.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == 'export':
            catalog = _load_report(args.catalog)
            if catalog.get('catalog_valid') is not True:
                raise ValueError('Valid catalog required')
            write_json(args.output, export_estimates(args.database, catalog['nodeid_to_test_id'].values()))
        elif args.action == 'plan':
            rules = {**DEFAULT_RULES, 'target_seconds':args.target_minutes*60,
                     'duration_factor':args.duration_factor}
            value = plan_run(ROOT,args.outdir,args.estimates,rules=rules)
            print(json.dumps({'python':value['context']['python'], 'packages':len(value['shards']),
                              'tests':len(value['tests']), 'plan_sha256':value['plan_sha256'],
                              'estimated_seconds':[s['estimated_seconds'] for s in value['shards']]}))
        elif args.action == 'matrix':
            paths = sorted(args.plans.glob('*/plan.json'))
            value = matrix([_load_report(p) for p in paths])
            encoded = json.dumps(value,separators=(',',':'))
            with Path(os.environ['GITHUB_OUTPUT']).open('a',encoding='utf-8') as stream:
                stream.write('matrix='+encoded+'\n')
            print(encoded)
        elif args.action == 'run':
            return run_package(ROOT,args.plan,args.shard,args.outdir)['exit_code']
        elif args.action == 'aggregate':
            value = aggregate(ROOT,args.plan,sorted(args.receipts.glob('*/package-result.json')),args.outdir)
            print(json.dumps({'tests_run':value['tests_run'],'suite_passed':value['suite_passed'],
                              'ci_packages':value['ci_packages']}))
        else:
            preserve_history(ROOT,args.output)
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print('CI package operation failed: '+str(error),file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
