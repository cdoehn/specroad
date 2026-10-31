"""Execute/collect explicit CI packages and preserve their native observations."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import uuid

from .catalog import load_catalog
from .catalog_check import run_catalog_preflight
from .catalog_contract import validate_preflight_report
from .ci_reference import _load_report
from .ci_packages import (DEFAULT_RULES, checked_context, digest, make_plan, merge_shards,
                          require, selected_pairs, validate_plan, verify_aggregate)
from .common import json_bytes, sha256
from .evidence import make_report
from .identity import source_identity, platform_identity
from .outcomes import ObservedExecution
from .process_environment import test_environment
from .runtime_history import policy, LOCAL
from .runtime_store import journal_path
from .selected_contract import new_report_directory, verify_observation


def write_json(path, value):
    with Path(path).open('xb') as stream:
        stream.write(json_bytes(value)); stream.flush(); os.fsync(stream.fileno())


def history_path(root):
    config = policy(root)
    return journal_path(Path(root) / (config['database'] if config else LOCAL), root)


def export_estimates(database, identities):
    """Read a consistent generation; never create a DB or fall back from a bad attempt."""
    database = Path(database).absolute()
    # The existing path guard rejects links and nonregular files.
    journal_path(database, database.parent / 'unused-source-root')
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        require(db.execute('PRAGMA quick_check').fetchall() == [('ok',)]
                and db.execute('SELECT version FROM metadata WHERE id=1').fetchall() == [(1,)],
                'Invalid runtime database')
        db.execute('BEGIN')
        attempts = db.execute('''SELECT a.test,a.invalid,a.complete,SUM(p.duration)
            FROM attempts a LEFT JOIN phases p ON p.attempt=a.id
            WHERE a.id IN (SELECT MAX(id) FROM attempts GROUP BY test) GROUP BY a.id''').fetchall()
        seeds = db.execute('''SELECT test,duration FROM seeds
            WHERE id IN (SELECT MAX(id) FROM seeds GROUP BY test)''').fetchall()
        db.rollback()
    latest = {t: d if not invalid and complete else None for t,invalid,complete,d in attempts}
    historic = dict(seeds)
    return dict(format_version=1, kind='specroad-ci-runtime-estimates-v1',
                captured_at=datetime.now(timezone.utc).isoformat(),
                tests=[dict(test_id=t, duration_ns=latest.get(t, historic.get(t)))
                       for t in sorted(set(identities))])


def execution_context(root, environment):
    require(environment.get('GITHUB_ACTIONS') == 'true', 'CI execution requires GitHub Actions')
    head = subprocess.run(['git','rev-parse','HEAD'], cwd=root, check=True,
                          capture_output=True, text=True).stdout.strip()
    require(head == environment.get('SR_TEST_SHA')
            and environment.get('GITHUB_REF') == 'refs/heads/dev', 'CI checkout differs from dispatch')
    context = dict(format_version=1, repository=environment.get('GITHUB_REPOSITORY'), branch='dev',
                   event=environment.get('GITHUB_EVENT_NAME'), mode='parallel',
                   python=f'{sys.version_info.major}.{sys.version_info.minor}',
                   test_commit_sha=head, workflow_commit_sha=environment.get('GITHUB_SHA'),
                   run_id=int(environment.get('GITHUB_RUN_ID', '0')),
                   run_attempt=int(environment.get('GITHUB_RUN_ATTEMPT', '0')))
    return checked_context(context)


def plan_run(root, outdir, estimates_path, *, rules=None, environment=None):
    root = Path(root).resolve()
    context = execution_context(root, os.environ if environment is None else environment)
    outdir = new_report_directory(outdir, root)
    catalog_path = outdir / 'catalog.json'
    require(run_catalog_preflight(root, catalog_path), 'CI collection failed; no packages started')
    plan = make_plan(_load_report(catalog_path), _load_report(estimates_path), context, rules=rules)
    write_json(outdir / 'plan.json', plan)
    return plan


def verify_plan_inputs(root, plan, context, collection):
    validate_plan(plan)
    source = source_identity(root)
    require(context == plan['context'] and source == plan['bindings']['source_sha256']
            and validate_preflight_report(root, collection, source), 'Stale CI plan or collection')
    require(all(collection[k] == v for k,v in plan['bindings'].items())
            and collection['nodeid_to_test_id'] == {t['nodeid']:t['test_id'] for t in plan['tests']},
            'Plan differs from actual complete collection')


def run_package(root, plan_path, shard, outdir, *, environment=None, runner=None):
    root = Path(root).resolve(); plan_path = Path(plan_path).absolute()
    env = dict(os.environ if environment is None else environment)
    context = execution_context(root, env)
    plan = validate_plan(_load_report(plan_path)); pairs = selected_pairs(plan, shard)
    outdir = new_report_directory(outdir, root)
    write_json(outdir / 'run-context.json', context)
    collection_path = outdir / 'catalog.json'
    require(run_catalog_preflight(root, collection_path), 'CI collection failed')
    verify_plan_inputs(root, plan, context, _load_report(collection_path))
    observed_path = outdir / 'observations.json'
    command = [sys.executable, '-I', '-B', str(root/'tools/pytest_entry.py'),
        '-o','addopts=', '--disable-plugin-autoload', '-p','no:cacheprovider', '-p','no:doctest',
        '-p','xdist.plugin', '-n',str(plan['rules']['workers']), '--dist','worksteal',
        '--max-worker-restart=0', '--sr-observations',str(observed_path),
        '--sr-expected-tests',str(len(pairs)), '--sr-ci-plan',str(plan_path),
        '--sr-ci-shard',str(shard), str(root/'tests')]
    runner = subprocess.run if runner is None else runner
    process_env = test_environment(env); process_env['PYTHONHASHSEED'] = '117'
    errors = []; observation = None
    try:
        code = runner(command, cwd=root, env=process_env, stdin=subprocess.DEVNULL,
                      check=False).returncode
    except OSError:
        code = None
        errors.append('package_process_not_started')
    try:
        observation = _load_report(observed_path)
        verify_observation(observation, sorted({n.split('::',1)[0] for n in pairs}), len(pairs))
        require(code == 0 and observation['nodeid_to_test_id'] == pairs
                and source_identity(root) == plan['bindings']['source_sha256']
                and _load_report(plan_path) == plan, 'Changed inputs or failed CI package')
    except (OSError, ValueError, TypeError, KeyError):
        errors.append('nonpassing_or_unbound_package')
    receipt = dict(format_version=1, kind='specroad-ci-package-result-v1', context=context,
        plan_sha256=plan['plan_sha256'], bindings=plan['bindings'], shard=shard,
        workers=plan['rules']['workers'], distribution='worksteal', runtime=platform_identity(),
        selected_passed=not errors, full_suite_passed=None, exit_code=0 if not errors else 1,
        process_exit_code=code, errors=errors, observation=observation)
    write_json(outdir / 'package-result.json', receipt)
    return receipt


def aggregate(root, plan_path, receipt_paths, outdir, *, environment=None):
    root = Path(root).resolve()
    plan = validate_plan(_load_report(plan_path))
    context = execution_context(root, os.environ if environment is None else environment)
    require(context == plan['context'] and source_identity(root) == plan['bindings']['source_sha256'],
            'Aggregate checkout or run does not match packages')
    receipts = [_load_report(p) for p in receipt_paths]
    observation, runtime = merge_shards(plan, receipts)
    catalog = load_catalog(root/'verification')
    require(catalog.catalog_sha256 == plan['bindings']['catalog_sha256']
            and catalog.specification_sha256 == plan['bindings']['specification_sha256'],
            'Aggregate catalog changed')
    execution = dict(engine='pytest', workers=plan['rules']['workers'], distribution='worksteal',
                     ci_shards=len(plan['shards']), test_timeout=None, suite_timeout=None)
    binding = dict(run_id=str(uuid.uuid4()), tool_build_sha256=plan['bindings']['source_sha256'],
                   platform_sha256=digest(runtime), configuration_sha256=digest(execution))
    observed = ObservedExecution(observation['test_outcomes'], observation['tests_run'], 0, ())
    report = make_report(catalog, binding, observed, list(observation['test_outcomes']))
    report.update(report_format_version=2, observation=observation, runtime=runtime,
                  execution=execution, ci_packages=dict(plan_sha256=plan['plan_sha256'], count=len(receipts)))
    verify_aggregate(plan, receipts, report)
    from compare_test_runs import _signature
    _signature(report)
    outdir = new_report_directory(outdir, root)
    for name, value in [('parallel-evidence.json',report), ('ci-plan.json',plan),
                        ('shard-receipts.json',receipts), ('run-context.json',context),
                        ('summary.json',dict(format_version=1,suite_passed=True,exit_code=0,
                                             errors=[],comparison=None,package_count=len(receipts)))]:
        write_json(outdir/name, value)
    return report


def preserve_history(root, output):
    """A consistent copy also preserves incomplete attempts; it is not pass evidence."""
    source = history_path(root); output = journal_path(output, root)
    require(source.is_file(), 'No runtime history was created')
    output.parent.mkdir(parents=True, exist_ok=True)
    journal_path(output, root)
    with output.open('xb'):
        pass
    with sqlite3.connect(source.as_uri()+'?mode=ro', uri=True) as db:
        with sqlite3.connect(output) as copy:
            db.backup(copy)
