"""Check real adapter measurements without starting a benchmark or granting release.

A hash binds bytes, not authorship. Evidence must come from a trusted measurement.
The historical observation stays historical; current builds must match exactly.
"""
import gzip
from hashlib import sha256
import json
import math
from pathlib import Path, PurePosixPath
import re
import statistics

MODEL = 'f4f4a2c3465ca1f081541037f9cac23021d68151c2f709c55ae5eedfca522963'
TRIALS = ('warmup', 'run-1', 'run-2', 'run-3', 'run-4', 'run-5')
LIMIT = 512 * 1024**2


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(raw):
    return sha256(raw).hexdigest()


def object_bytes(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('nonfinite_json_number')
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    require(type(value) is dict, 'expected_object')
    return value


def number(value):
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
            'invalid_resource_number')
    return value


def read_limited(path):
    require(path.is_file() and not path.is_symlink(), 'missing_regular_evidence')
    with gzip.open(path, 'rb') as stream:
        raw = stream.read(16 * 1024**2 + 1)
    require(len(raw) <= 16 * 1024**2, 'oversized_evidence')
    return raw


def load(directory):
    directory = Path(directory)
    receipt = object_bytes((directory / 'receipt.json').read_bytes())
    require(receipt['format_version'] == 1 and receipt['kind'] == 'analyzer-resource-evidence-export',
            'unknown_evidence_format')
    records = {}
    require(type(receipt['files']) is dict and len(receipt['files']) <= 100, 'invalid_evidence_inventory')
    for name, entry in receipt['files'].items():
        parts = PurePosixPath(name).parts
        require(parts and not name.startswith('/') and '..' not in parts and '\\' not in name,
                'unsafe_evidence_path')
        path = directory / (name + '.gz')
        require(not any(p.is_symlink() for p in (path, *path.parents)), 'linked_evidence_path')
        raw = read_limited(path)
        require(digest(raw) == entry['exported_sha256'], 'changed_evidence_bytes')
        if entry['transform'] == 'identity':
            require(digest(raw) == entry['original_sha256'], 'changed_original_bytes')
        else:
            require((name == 'benchmark-platform.json' and entry['transform'] == 'platform-field-allowlist-v1')
                    or (name.endswith('.time') and entry['transform'] == 'remove-command-prefix-v1'),
                    'unknown_projection')
        records[name] = raw
    require(digest(records['summary.json']) == receipt['original_summary_sha256'], 'changed_summary')
    summary = object_bytes(records['summary.json'])
    require(summary['platform_sha256'] == receipt['files']['benchmark-platform.json']['original_sha256'],
            'wrong_platform_origin')
    for trial in TRIALS:
        prefix = 'results/' + trial + '/'
        raw = records[prefix + 'result.json']
        require(digest(raw) == summary['raw_results_sha256'][trial], 'wrong_trial_origin')
        row = object_bytes(raw)
        for name in ('parent.json', 'worker.json', 'report.json', 'rss-samples.jsonl.gz', 'tree.time', 'worker.time'):
            require(row['files_sha256'][name] == receipt['files'][prefix + name]['original_sha256'],
                    'wrong_measurement_origin')
    return records


def time_values(raw):
    text = raw.decode('utf-8')
    def field(label):
        matches = re.findall(r'^\s*' + re.escape(label) + r':\s*([0-9.]+)\s*$', text, re.M)
        require(len(matches) == 1, 'missing_or_duplicate_time_field')
        return number(float(matches[0]))
    return dict(user_seconds=field('User time (seconds)'), system_seconds=field('System time (seconds)'),
                maxrss_bytes=field('Maximum resident set size (kbytes)') * 1024,
                exit_status=field('Exit status'))


def process_inventory(row, parent, worker):
    """Resolve v1's final cmdline label against independent process identities.

    The observer overwrote its final row even without a readable RSS sample.
    That row can label an exiting parent as worker. Its PID/start identity,
    wrapper ancestry and the actual RSS observations must still agree.
    Never modify the archived measurement or infer an unobserved process.
    """
    identities = (parent['pid'], worker['pid'], parent['ppid'], worker['ppid'])
    require(all(type(pid) is int and pid > 0 for pid in identities), 'invalid_process_identity')
    require(len(set(identities)) == 4, 'duplicate_process_identity')
    processes = row['processes']
    require(all(type(p['pid']) is int and p['pid'] > 0
                and type(p['ppid']) is int and p['ppid'] > 0
                and type(p['start_ticks']) is int and p['start_ticks'] > 0
                for p in processes), 'invalid_process_identity')
    known = {p['pid']: dict(p) for p in processes}
    require(len(known) == len(processes), 'duplicate_process_identity')
    require(set(known) == set(identities), 'incomplete_process_set')
    require(known[parent['pid']]['ppid'] == parent['ppid']
            and known[worker['pid']]['ppid'] == worker['ppid']
            and known[worker['ppid']]['ppid'] == parent['pid']
            and known[parent['ppid']]['ppid'] not in known, 'wrong_process_ancestry')
    for pid in (parent['ppid'], worker['ppid']):
        require(known[pid]['comm'] == 'time'
                and known[pid]['role'] == 'gnu-time-observer', 'unknown_measurement_observer')
    require(known[parent['pid']]['role'] in ('parent', 'worker')
            and known[worker['pid']]['role'] == 'worker'
            and all(known[pid]['comm'] != 'time' for pid in (parent['pid'], worker['pid'])),
            'wrong_process_role')
    known[parent['pid']]['role'] = 'parent'
    return known


def verify_process_samples(samples, known, parent_pid, worker_pid):
    """Both measured roles need matching PID, start ticks and RSS observations."""
    seen = set()
    for sample in samples:
        require(type(sample['start_ns']) is int and type(sample['end_ns']) is int
                and sample['end_ns'] >= sample['start_ns'], 'invalid_rss_interval')
        processes = sample['processes']
        require(processes and all(type(p['pid']) is int and p['pid'] in (parent_pid, worker_pid)
                                  for p in processes), 'unknown_rss_process')
        require(len({p['pid'] for p in processes}) == len(processes), 'duplicate_rss_process')
        for p in processes:
            require(type(p['start_ticks']) is int and p['start_ticks'] == known[p['pid']]['start_ticks']
                    and p['role'] == known[p['pid']]['role']
                    and type(p['ppid']) is int and p['ppid'] == known[p['pid']]['ppid'],
                    'reused_or_mislabelled_pid')
            seen.add(p['pid'])
        require(number(sample['rss_bytes']) == sum(number(p['rss_bytes']) for p in processes),
                'rss_sum_mismatch')
    require(seen == {parent_pid, worker_pid}, 'missing_parent_or_worker_rss')


def assess(records, *, expected_build):
    """Return measured pass/fail/inconclusive, or reject incomplete/unbound evidence."""
    from specroad.analyzers.requests import AnalyzerRequest
    from specroad.analyzers.packages import ReportPackage

    platform = object_bytes(records['benchmark-platform.json'])
    summary = object_bytes(records['summary.json'])
    fixture = object_bytes(records['fixture-manifest.json'])
    package = object_bytes(records['package-manifest.json'])
    require(platform['specroad_build']['build_sha256'] == package['core_build']['build_sha256'] == expected_build,
            'unmeasured_build')
    require(platform['model_sha256'] == package['model']['sha256'] == MODEL, 'unmeasured_model')
    require(platform['architecture'] == 'x86_64' and platform['kernel']['system'] == 'Linux'
            and platform['logical_cpus'] >= 4 and platform['ram_total_kib'] >= 8 * 1024**2,
            'unsupported_reference_platform')
    baseline = platform['baseline_environment']
    require(baseline['governors'] and set(baseline['governors'].values()) == {'performance'}
            and not baseline['swap'] and not baseline['competing_processes'], 'unqualified_reference_platform')
    require(platform['expected_environment'] == dict(LC_ALL='C', TZ='UTC', cache='off', resource_profile='standard'),
            'wrong_measurement_profile')
    require(summary['status'] == 'completed' and summary['warmup_count'] == 1
            and summary['measured_run_count'] == 5, 'incomplete_measurement_series')
    require(digest(records['fixture-manifest.json']) == summary['fixture_manifest_sha256']
            == platform['fixture_manifest_sha256'], 'changed_fixture')
    request = AnalyzerRequest(records['request.json'])
    require(digest(records['request.json']) == fixture['request_sha256'], 'changed_request')
    subjects = sorted(request.data['subjects'], key=lambda s: s['subject_key'])
    require(len(subjects) == fixture['subjects'] == 1000
            and all(100 <= len(s['value']) <= 500 for s in subjects), 'incomplete_fulltext_workload')
    expected_ranked = [dict(sha256=s['value_sha256'], codepoints=len(s['value'])) for s in subjects]
    measurements = []
    for trial in TRIALS:
        prefix = 'results/' + trial + '/'
        row = object_bytes(records[prefix + 'result.json'])
        parent = object_bytes(records[prefix + 'parent.json'])
        worker = object_bytes(records[prefix + 'worker.json'])
        report = ReportPackage(records[prefix + 'report.json'], request=request).reports[0].data
        require(row['status'] == 'measured' and row['trial'] == trial and row['project_bytes_unchanged'] is True,
                'incomplete_trial')
        require(parent['request_sha256'] == fixture['request_sha256'] and worker['model_loads'] == 1
                and worker['ranked'] == expected_ranked, 'incomplete_or_truncated_execution')
        require(parent['model_sha256'] == report['engine']['model_sha256']['value'] == MODEL, 'wrong_trial_model')
        counts = report['coverage']['counts']
        require(report['run_status'] == 'complete' and counts['expected'] == 1000
                and counts['done'] + counts['undetermined'] == 1000
                and counts['open'] == counts['failed'] == 0, 'incomplete_report')
        known = process_inventory(row, parent, worker)
        outer, inner = [time_values(records[prefix + name]) for name in ('tree.time', 'worker.time')]
        require(outer['exit_status'] == inner['exit_status'] == 0, 'workload_failed')
        cpu = outer['user_seconds'] + outer['system_seconds']
        upper = outer['maxrss_bytes'] + inner['maxrss_bytes']
        require(abs(cpu - number(row['cpu_total_seconds'])) < 1e-6
                and upper == number(row['rss_conservative_upper_bound_bytes']), 'resource_summary_mismatch')
        samples = [object_bytes(line) for line in gzip.decompress(records[prefix + 'rss-samples.jsonl.gz']).splitlines()]
        require(bool(samples) and len(samples) == row['rss_sample_count'], 'missing_rss_observations')
        verify_process_samples(samples, known, parent['pid'], worker['pid'])
        peak = max(s['rss_bytes'] for s in samples)
        require(peak == row['sampled_simultaneous_rss_peak_bytes'] and peak <= upper, 'rss_peak_mismatch')
        require(row['environment'] and all(not e['swap'] and not e['competing_processes']
                and e['governors'] == baseline['governors']
                and e['thermal_throttle_counts'] == baseline['thermal_throttle_counts'] for e in row['environment']),
                'unqualified_trial_environment')
        measurements.append(dict(cpu=cpu, upper=upper, peak=peak, wall=number(row['wall_seconds'])))
    measured = measurements[1:]
    cpu_max = max(r['cpu'] for r in measured)
    upper_max = max(r['upper'] for r in measured)
    peak_max = max(r['peak'] for r in measured)
    status = resource_status(cpu_max, peak_max, upper_max)
    return dict(status=status, build_sha256=expected_build, cpu_max_seconds=cpu_max,
                wall_median_seconds=statistics.median(r['wall'] for r in measured),
                sampled_simultaneous_rss_max_bytes=peak_max, rss_upper_bound_bytes=upper_max,
                scope='historical_reference_adapter_measurement', release_approved=False,
                human_corpus_review_completed=False)


def resource_status(cpu, peak, upper):
    require(number(cpu) > 0 and number(peak) > 0 and number(upper) >= peak,
            'missing_or_inconsistent_resource_bound')
    return ('failed' if cpu + 0.02 > 120 or peak > LIMIT else
            'inconclusive' if upper > LIMIT else 'passed')
