"""Check real adapter measurements without starting a benchmark or granting release.

A hash binds bytes, not authorship. Evidence must come from a trusted measurement.
The historical observation stays historical; current builds must match exactly.
"""
import gzip
import re
import statistics

MODEL = 'f4f4a2c3465ca1f081541037f9cac23021d68151c2f709c55ae5eedfca522963'
from .records import TRIALS, require, digest, object_bytes, number, load, time_values

__all__ = ("assess", "check", "resource_status", "digest", "load", "object_bytes", "time_values",
           "process_inventory", "verify_process_samples")
LIMIT = 512 * 1024**2


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
    qualify_platform(platform, package, summary)
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
    require(len(fixture['cases']) == 1000 and fixture['text_truncation'] is False, 'wrong_fixture_scope')
    require(sorted((c['id'], c['utf8_sha256'], c['codepoints']) for c in fixture['cases']) ==
            sorted((s['artifact_id'], digest(s['value'].encode('utf-8')), len(s['value'])) for s in subjects), 'fixture_subject_mismatch')
    require(summary['subjects_per_run'] == 1000, 'wrong_summary_subject_count')
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
        verify_trial(records, prefix, row, parent, worker, report, platform, outer, inner, samples)
        measurements.append(dict(cpu=cpu, upper=upper, peak=peak, wall=number(row['wall_seconds'])))
    measured = measurements[1:]
    cpu_max = max(r['cpu'] for r in measured)
    upper_max = max(r['upper'] for r in measured)
    peak_max = max(r['peak'] for r in measured)
    require(summary['cpu_max_seconds'] == cpu_max and summary['rss_conservative_upper_bound_max_bytes'] == upper_max
            and summary['sampled_simultaneous_rss_max_bytes'] == peak_max
            and summary['wall_median_seconds'] == statistics.median(r['wall'] for r in measured), 'series_summary_mismatch')
    status = resource_status(cpu_max, peak_max, upper_max)
    return dict(status=status, build_sha256=expected_build, cpu_max_seconds=cpu_max,
                wall_median_seconds=statistics.median(r['wall'] for r in measured),
                sampled_simultaneous_rss_max_bytes=peak_max, rss_upper_bound_bytes=upper_max,
                scope='historical_reference_adapter_measurement', release_approved=False,
                human_corpus_review_completed=False)


def qualify_platform(platform, package, summary):
    require(platform['format_version'] == 1 and platform['kind'] == 'analyzer-benchmark-public-projection',
            'unknown_platform_format')
    require(platform['physical_cores'] >= 1 and len(platform['available_cpus']) >= 4
            and len(set(platform['available_cpus'])) == len(platform['available_cpus']), 'insufficient_reference_cpus')
    require(platform['cpu'] and all(all(c.get(k) for k in ('model name', 'stepping', 'microcode', 'core id'))
            for c in platform['cpu']), 'missing_cpu_identity')
    require(platform['os_release'] and platform['kernel']['release'] and platform['kernel']['version'],
            'missing_os_identity')
    require(platform['ram_speed_available'] is False or bool(platform['ram_speed_observation']), 'missing_ram_speed')
    python = platform['python']
    require(python['implementation'] == 'cpython' and python['build']
            and re.fullmatch(r'[0-9a-f]{64}', python['executable_sha256']) is not None
            and '.'.join(python['version'].split('.')[:2]) == package['python_minor'], 'wrong_measurement_runtime')
    require(platform['source_commit'] == summary['source_commit']
            and platform['source_result_sha256'] == summary['source_result_sha256']
            and platform['measurement_scripts_sha256'] == summary['measurement_scripts_sha256'], 'wrong_series_binding')
    baseline = platform['baseline_environment']
    require(bool(baseline['thermal_throttle_counts']), 'unobserved_throttling')
    filesystems = platform['filesystem']
    require(len(filesystems) == 1 and filesystems[0]['fstype'] in ('ext4', 'xfs', 'btrfs')
            and filesystems[0]['options'], 'unqualified_filesystem')
    device = filesystems[0]['source'].rsplit('/', 1)[-1]
    def contains(row):
        return row['name'] == device or any(contains(child) for child in row.get('children', []))
    disks = [d for d in platform['block_devices'] if contains(d)]
    require(len(disks) == 1 and disks[0]['type'] == 'disk' and disks[0]['rota'] is False
            and disks[0]['model'], 'unqualified_local_ssd')


def verify_trial(records, prefix, row, parent, worker, report, platform, outer, inner, samples):
    from specroad.runtime.resource_profiles import profile_targets
    require(parent['resource_profile'] == profile_targets('standard', source='cli'), 'wrong_core_profile')
    require(type(worker['model_loads']) is int and type(row['rss_sample_count']) is int, 'invalid_measurement_counts')
    report_hash = digest(records[prefix + 'report.json'])
    require(parent['report_sha256'] == worker['report_package_sha256'] == report_hash,
            'wrong_report_binding')
    require(parent['coverage'] == report['coverage']['counts'] and row['parent'] == parent,
            'wrong_parent_binding')
    require(parent['engine'] == report['extensions']['specroad.engine_inventory']
            and parent['engine']['runtime']['python_version'] == platform['python']['version'], 'wrong_trial_runtime')
    require(parent['cache'] == 'off' and parent['api_scope'] == 'full_adapter_via_native_transport_operator_bootstrap',
            'wrong_trial_scope')
    require(row['complete_subjects'] == 1000 and row['model_loads'] == worker['model_loads'] == 1,
            'wrong_trial_workload')
    require(row['gnu_time_tree'] == outer and row['gnu_time_worker'] == inner, 'wrong_time_binding')
    for label, facts, timing in (('parent', parent, outer), ('worker', worker, inner)):
        cpu = number(facts['user_seconds']) + number(facts['system_seconds'])
        require(cpu > 0 and abs(cpu - number(row[label + '_cpu_seconds'])) < 1e-6, 'missing_separate_cpu')
        require(number(facts['self_maxrss_kib']) * 1024 <= timing['maxrss_bytes'], 'rss_unit_mismatch')
    require(number(parent['waited_children_user_seconds']) + number(parent['waited_children_system_seconds']) > 0,
            'missing_child_cpu_accounting')
    require(row['cpu_total_seconds'] >= row['parent_cpu_seconds'] + row['worker_cpu_seconds']
            and row['cpu_total_seconds'] >= inner['user_seconds'] + inner['system_seconds'], 'parent_only_cpu')
    require(row['environment_qualified'] is True and row['cpu_resolution_seconds'] == 0.01,
            'unqualified_observation')


def check(directory, *, expected_build):
    """Malformed/unknown/unmeasurable inputs cannot produce a pass."""
    try:
        return assess(load(directory), expected_build=expected_build)
    except (OSError, ValueError, TypeError, KeyError, IndexError, EOFError, RecursionError) as error:
        return dict(status='blocked', reason=type(error).__name__ + ': ' + str(error),
                    scope='historical_reference_adapter_measurement', release_approved=False,
                    human_corpus_review_completed=False)


def resource_status(cpu, peak, upper):
    require(number(cpu) > 0 and number(peak) > 0 and number(upper) >= peak,
            'missing_or_inconsistent_resource_bound')
    return ('failed' if cpu + 0.02 > 120 or peak > LIMIT else
            'inconclusive' if upper > LIMIT else 'passed')
