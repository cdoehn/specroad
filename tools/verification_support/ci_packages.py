"""Deterministic duration-weighted CI packages; no test execution or scheduling."""
from copy import deepcopy
from hashlib import sha256
import heapq
import math
import re

from .common import json_bytes
from .selected_contract import verify_observation

PYTHONS = ('3.10', '3.11', '3.12', '3.13', '3.14')
DEFAULT_RULES = dict(workers=4, target_seconds=10800, overhead_seconds=900,
                     duration_factor=1.5, unknown_seconds=300, max_matrix_jobs=256)


def digest(value):
    return sha256(json_bytes(value)).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checked_context(value):
    keys = {'format_version', 'repository', 'branch', 'event', 'mode', 'python',
            'test_commit_sha', 'workflow_commit_sha', 'run_id', 'run_attempt'}
    require(type(value) is dict and keys <= value.keys(), 'Missing CI execution context')
    require(type(value['format_version']) is int and value['format_version'] == 1
            and value['repository'] == 'cdoehn/specroad' and value['branch'] == 'dev'
            and value['event'] == 'workflow_dispatch' and value['mode'] == 'parallel'
            and value['python'] in PYTHONS, 'Invalid manual CI context')
    for key in ('test_commit_sha', 'workflow_commit_sha'):
        require(type(value[key]) is str and re.fullmatch('[0-9a-f]{40}', value[key]),
                'Full CI commit required')
    for key in ('run_id', 'run_attempt'):
        require(type(value[key]) is int and value[key] > 0, 'Invalid CI attempt')
    return {k: value[k] for k in sorted(keys)}


def checked_rules(rules):
    require(type(rules) is dict and set(rules) == set(DEFAULT_RULES), 'Invalid package rules')
    for key in set(rules) - {'duration_factor'}:
        require(type(rules[key]) is int and rules[key] > 0, 'Positive integer rule required')
    require(rules['workers'] == 4 and rules['max_matrix_jobs'] <= 256
            and rules['overhead_seconds'] < rules['target_seconds'] <= 18000,
            'Invalid worker, matrix or time budget')
    factor = rules['duration_factor']
    require(type(factor) in (int, float) and math.isfinite(factor) and factor >= 1,
            'Invalid duration factor')
    return dict(rules)


def checked_estimates(value):
    require(type(value) is dict and value.get('format_version') == 1
            and type(value['format_version']) is int
            and value.get('kind') == 'specroad-ci-runtime-estimates-v1'
            and type(value.get('tests')) is list, 'Invalid runtime estimates')
    result = {}
    for row in value['tests']:
        require(type(row) is dict and set(row) == {'test_id', 'duration_ns'}
                and type(row['test_id']) is str and row['test_id']
                and row['test_id'] not in result, 'Invalid or duplicate runtime identity')
        duration = row['duration_ns']
        require(duration is None or type(duration) is int and duration >= 0,
                'Invalid runtime duration')
        result[row['test_id']] = duration
    return result


def _worker_order(indices, tests, workers):
    """Balance equal-count initial worksteal queues, longest tests first per queue.

    xdist owns execution and subsequent stealing. Its initial queues divide the
    collection by remaining test count / remaining workers. Matching these sizes
    avoids putting every long test into the first contiguous initial queue.
    """
    remaining = len(indices)
    capacities = []
    for left in range(workers, 0, -1):
        capacity = remaining // left
        capacities.append(capacity)
        remaining -= capacity
    lanes = [[] for _ in capacities]
    loads = [0] * workers
    for index in sorted(indices, key=lambda i: (-tests[i]['estimate_ns'], tests[i]['nodeid'])):
        lane = min((i for i in range(workers) if len(lanes[i]) < capacities[i]),
                   key=lambda i: (loads[i], i))
        lanes[lane].append(index)
        loads[lane] += tests[index]['estimate_ns']
    return [i for lane in lanes for i in lane], max(loads)


def _packages(tests, rules):
    workers = rules['workers']
    budget = (rules['target_seconds'] - rules['overhead_seconds']) * 1_000_000_000
    require(max(t['estimate_ns'] for t in tests) <= budget,
            'A single test exceeds the estimated job target; more packages cannot divide it')
    maximum = min(len(tests), rules['max_matrix_jobs'] // len(PYTHONS))
    count = max(1, math.ceil(sum(t['estimate_ns'] for t in tests) / (workers * budget)))
    ordered = sorted(range(len(tests)), key=lambda i: (-tests[i]['estimate_ns'], tests[i]['nodeid']))
    while count <= maximum:
        heap = [(0, j, w) for j in range(count) for w in range(workers)]
        heapq.heapify(heap)
        groups = [[] for _ in range(count)]
        for index in ordered:
            load, group, worker = heapq.heappop(heap)
            groups[group].append(index)
            heapq.heappush(heap, (load + tests[index]['estimate_ns'], group, worker))
        result = []
        for shard, indices in enumerate(groups):
            if not indices:
                break
            order, load = _worker_order(indices, tests, workers)
            result.append(dict(shard=shard, tests=order,
                               estimated_seconds=math.ceil(load / 1e9) + rules['overhead_seconds']))
        if len(result) == count and max(p['estimated_seconds'] for p in result) <= rules['target_seconds']:
            return result
        count += 1
    raise ValueError('The estimated target requires more than 256 matrix jobs; no tests were omitted')


def make_plan(collection, estimates, context, *, rules=None):
    context = checked_context(context)
    rules = checked_rules(DEFAULT_RULES if rules is None else rules)
    require(type(collection) is dict and collection.get('catalog_valid') is True
            and collection.get('errors') == [] and collection.get('tests_run') == 0
            and collection.get('collection_exit_code') == 0
            and collection.get('full_suite_passed') is None, 'Complete collection required')
    pairs = collection.get('nodeid_to_test_id')
    require(type(pairs) is dict and pairs and len(pairs) == collection.get('collected_tests')
            and len(set(pairs.values())) == len(pairs), 'Unique complete collection required')
    measured = checked_estimates(estimates)
    tests = []
    for node, identity in sorted(pairs.items()):
        require(type(node) is str and node.startswith('tests/') and '::' in node
                and '\n' not in node and '\r' not in node
                and type(identity) is str and identity, 'Invalid test identity')
        duration = measured.get(identity)
        base = rules['unknown_seconds'] * 1_000_000_000 if duration is None else duration
        tests.append(dict(nodeid=node, test_id=identity, duration_ns=duration,
                          estimate_ns=max(1, math.ceil(base * rules['duration_factor']))))
    bindings = {k: collection[k] for k in ('source_sha256', 'specification_sha256', 'catalog_sha256')}
    for v in bindings.values():
        require(type(v) is str and re.fullmatch('[0-9a-f]{64}', v), 'Invalid collection binding')
    plan = dict(format_version=1, kind='specroad-ci-package-plan-v1', context=context,
                bindings=bindings, rules=rules, runtime_estimates_sha256=digest(estimates),
                tests=tests, shards=_packages(tests, rules))
    plan['plan_sha256'] = digest(plan)
    return plan


def validate_plan(plan):
    require(type(plan) is dict and set(plan) == {'format_version', 'kind', 'context', 'bindings',
            'rules', 'runtime_estimates_sha256', 'tests', 'shards', 'plan_sha256'}
            and type(plan['format_version']) is int and plan['format_version'] == 1
            and plan['kind'] == 'specroad-ci-package-plan-v1', 'Invalid CI package plan')
    require(plan['plan_sha256'] == digest({k:v for k,v in plan.items() if k != 'plan_sha256'}),
            'Changed package plan')
    checked_context(plan['context']); rules = checked_rules(plan['rules'])
    require(type(plan['bindings']) is dict and set(plan['bindings']) ==
            {'source_sha256', 'specification_sha256', 'catalog_sha256'}, 'Invalid plan bindings')
    for value in [*plan['bindings'].values(), plan['runtime_estimates_sha256']]:
        require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value), 'Invalid plan hash')
    tests = plan['tests']
    require(type(tests) is list and tests, 'Empty CI plan')
    nodes, ids = [], []
    for row in tests:
        require(type(row) is dict and set(row) == {'nodeid','test_id','duration_ns','estimate_ns'},
                'Invalid planned test')
        require(type(row['nodeid']) is str and row['nodeid'].startswith('tests/')
                and '::' in row['nodeid'] and '\n' not in row['nodeid'] and '\r' not in row['nodeid']
                and type(row['test_id']) is str and row['test_id'], 'Invalid planned identity')
        d = row['duration_ns']
        require(d is None or type(d) is int and d >= 0, 'Invalid planned duration')
        base = rules['unknown_seconds'] * 1_000_000_000 if d is None else d
        require(type(row['estimate_ns']) is int and row['estimate_ns'] ==
                max(1, math.ceil(base * rules['duration_factor'])), 'Invalid test estimate')
        nodes.append(row['nodeid']); ids.append(row['test_id'])
    require(nodes == sorted(set(nodes)) and len(set(ids)) == len(ids), 'Duplicate planned test')
    require(plan['shards'] == _packages(tests, rules), 'Noncanonical or incomplete package assignment')
    return plan


def selected_pairs(plan, shard):
    require(type(shard) is int and 0 <= shard < len(plan['shards']), 'Unknown CI package')
    return {plan['tests'][i]['nodeid']: plan['tests'][i]['test_id']
            for i in plan['shards'][shard]['tests']}


def matrix(plans):
    require(type(plans) is list and len(plans) == len(PYTHONS), 'All Python plans required')
    contexts = []; versions = []; include = []
    for plan in plans:
        validate_plan(plan)
        context = dict(plan['context']); version = context.pop('python')
        versions.append(version); contexts.append(context)
        include.extend(dict(python=version, shard=s['shard']) for s in plan['shards'])
    require(sorted(versions) == list(PYTHONS) and all(c == contexts[0] for c in contexts),
            'Mixed, duplicate or missing Python plans')
    require(len(include) <= 256, 'Matrix exceeds 256 jobs')
    return {'include': sorted(include, key=lambda r: (PYTHONS.index(r['python']), r['shard']))}


def merge_shards(plan, receipts):
    validate_plan(plan)
    require(type(receipts) is list and len(receipts) == len(plan['shards']), 'Missing CI packages')
    found = {}; runtime = None
    all_pairs = {}; outcomes = {}; counts = {}
    for receipt in receipts:
        require(type(receipt) is dict and receipt.get('kind') == 'specroad-ci-package-result-v1'
                and receipt.get('format_version') == 1 and type(receipt['format_version']) is int
                and receipt.get('context') == plan['context']
                and receipt.get('plan_sha256') == plan['plan_sha256']
                and receipt.get('bindings') == plan['bindings']
                and receipt.get('workers') == plan['rules']['workers']
                and receipt.get('distribution') == 'worksteal'
                and receipt.get('full_suite_passed') is None
                and receipt.get('selected_passed') is True
                and type(receipt.get('exit_code')) is int and receipt['exit_code'] == 0,
                'Failed, unbound or incompatible CI package')
        shard = receipt.get('shard'); pairs = selected_pairs(plan, shard)
        require(shard not in found, 'Duplicate CI package')
        found[shard] = receipt
        observed = receipt.get('observation')
        verify_observation(observed, sorted({n.split('::',1)[0] for n in pairs}), len(pairs))
        require(observed['nodeid_to_test_id'] == pairs, 'Unexpected package test identities')
        actual_runtime = receipt.get('runtime')
        require(type(actual_runtime) is dict and actual_runtime.get('implementation') == 'cpython'
                and type(actual_runtime.get('python')) is str
                and actual_runtime['python'].startswith(plan['context']['python'] + '.'),
                'Wrong package interpreter')
        if runtime is None:
            runtime = actual_runtime
        require(runtime == actual_runtime, 'Mixed package platforms')
        for worker, count in observed['worker_test_counts'].items():
            require(re.fullmatch('gw[0-9]+', worker) and int(worker[2:]) < plan['rules']['workers'],
                    'Unexpected package worker')
            counts[f'shard{shard}-{worker}'] = count
        require(not set(all_pairs) & set(pairs), 'Overlapping CI packages')
        all_pairs.update(pairs); outcomes.update(observed['test_outcomes'])
    expected = {t['nodeid']: t['test_id'] for t in plan['tests']}
    require(all_pairs == expected and set(found) == set(range(len(plan['shards']))),
            'Incomplete full regression')
    observation = dict(observation_format_version=1, engine='pytest', nodeids=sorted(all_pairs),
        nodeid_to_test_id=dict(sorted(all_pairs.items())), test_outcomes=dict(sorted(outcomes.items())),
        tests_run=len(all_pairs), suite_passed=True, pytest_exit_code=0,
        workers=sorted(counts), worker_test_counts=dict(sorted(counts.items())), errors=[])
    return observation, runtime


def verify_aggregate(plan, receipts, report):
    observation, runtime = merge_shards(plan, receipts)
    require(report.get('observation') == observation and report.get('runtime') == runtime
            and report.get('test_outcomes') == observation['test_outcomes']
            and report.get('tests_run') == len(plan['tests'])
            and report.get('tool_build_sha256') == plan['bindings']['source_sha256']
            and all(report.get(k) == plan['bindings'][k] for k in ('catalog_sha256','specification_sha256'))
            and report.get('ci_packages') == {'plan_sha256': plan['plan_sha256'],
                                             'count': len(plan['shards'])},
            'Aggregate does not match its complete native package receipts')
