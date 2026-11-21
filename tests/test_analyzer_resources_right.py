"""Host blockers and falsified measurement evidence never satisfy T.10."""
import gzip
import json
import shutil

import pytest

from analyzer_benchmark.verify import assess, check, load, object_bytes, time_values, resource_status
from test_analyzer_resources import EVIDENCE

BUILD = '797fa5577f38ce87e0e62df7cecbe03fca370f1bbfa65efb7781b9592575663f'


@pytest.fixture(scope='module')
def evidence():
    return load(EVIDENCE)


def altered(evidence, file, mutate):
    records = dict(evidence)
    value = object_bytes(records[file])
    mutate(value)
    records[file] = json.dumps(value, ensure_ascii=False).encode()
    return records


@pytest.mark.parametrize('field,value', [
    ('logical_cpus', 2), ('ram_total_kib', 1024), ('architecture', 'unknown'),
    ('physical_cores', 0), ('available_cpus', [0, 1]), ('cpu', []),
    ('os_release', ''), ('block_devices', []), ('filesystem', []),
    ('python', {}), ('format_version', 99), ('ram_speed_observation', []),
])
def test_small_or_unknown_reference_host_is_not_a_pass(evidence, field, value):
    records = altered(evidence, 'benchmark-platform.json', lambda p: p.update({field: value}))
    with pytest.raises((ValueError, KeyError)):
        assess(records, expected_build=BUILD)


def test_changed_product_needs_a_new_real_measurement(evidence):
    with pytest.raises(ValueError, match='unmeasured_build'):
        assess(evidence, expected_build='0' * 64)


@pytest.mark.parametrize('fault', ['missing', 'truncated', 'foreign-model', 'extra-process',
                                  'cpu-parent-only', 'rss-kib-as-bytes', 'warmup-only', 'swap',
                                  'throttle', 'wrong-runtime', 'no-worker-rss'])
def test_incomplete_or_inconsistent_observation_is_rejected(evidence, fault):
    records = dict(evidence)
    prefix = 'results/warmup/'
    if fault == 'missing':
        del records[prefix + 'parent.json']
    elif fault == 'truncated':
        records = altered(records, prefix + 'worker.json', lambda w: w['ranked'].pop())
    elif fault == 'foreign-model':
        records = altered(records, 'benchmark-platform.json', lambda p: p.update(model_sha256='0' * 64))
    elif fault == 'extra-process':
        records = altered(records, prefix + 'result.json', lambda r: r['processes'].append(dict(pid=99,role='worker')))
    elif fault == 'cpu-parent-only':
        records = altered(records, prefix + 'result.json', lambda r: r.update(cpu_total_seconds=r['parent_cpu_seconds']))
    elif fault == 'rss-kib-as-bytes':
        records = altered(records, prefix + 'result.json', lambda r: r.update(rss_conservative_upper_bound_bytes=200000))
    elif fault == 'warmup-only':
        records = altered(records, 'summary.json', lambda s: s.update(measured_run_count=0))
    elif fault in ('swap', 'throttle'):
        def mutate(row):
            row['environment'][0]['swap' if fault == 'swap' else 'thermal_throttle_counts'] = ['changed']
        records = altered(records, prefix + 'result.json', mutate)
    elif fault == 'wrong-runtime':
        records = altered(records, prefix + 'parent.json', lambda p: p['engine']['runtime'].update(python_version='3.9.0'))
    else:
        samples = [json.loads(line) for line in gzip.decompress(records[prefix + 'rss-samples.jsonl.gz']).splitlines()]
        for sample in samples:
            sample['processes'] = [p for p in sample['processes'] if p['role'] == 'parent']
            sample['rss_bytes'] = sum(p['rss_bytes'] for p in sample['processes'])
        records[prefix + 'rss-samples.jsonl.gz'] = gzip.compress(b'\n'.join(json.dumps(x).encode() for x in samples))
    with pytest.raises((ValueError, KeyError)):
        assess(records, expected_build=BUILD)


def test_absent_or_changed_evidence_is_blocked_without_creating_outputs(tmp_path):
    missing = tmp_path / 'absent'
    result = check(missing, expected_build=BUILD)
    assert result['status'] == 'blocked' and not missing.exists()
    shutil.copytree(EVIDENCE, tmp_path / 'copy')
    target = tmp_path / 'copy/request.json.gz'
    target.write_bytes(gzip.compress(b'{}'))
    before = target.read_bytes()
    assert check(tmp_path / 'copy', expected_build=BUILD)['status'] == 'blocked'
    assert target.read_bytes() == before


@pytest.mark.parametrize('bad', [b'{}', b'User time (seconds): nan', b'User time (seconds): -1'])
def test_unmeasured_time_has_no_zero_default(bad):
    with pytest.raises(ValueError):
        time_values(bad)


@pytest.mark.parametrize('cpu,peak,upper,expected', [
    (119.98, 512 * 1024**2, 512 * 1024**2, 'passed'),
    (120, 1000, 2000, 'failed'),
    (6, 512 * 1024**2 + 1, 512 * 1024**2 + 1, 'failed'),
    (6, 1000, 512 * 1024**2 + 1, 'inconclusive'),
])
def test_cpu_and_simultaneous_rss_limits_do_not_confuse_observed_peak_with_upper_bound(cpu, peak, upper, expected):
    assert resource_status(cpu, peak, upper) == expected


@pytest.mark.parametrize('cpu,peak,upper', [(0, 1, 1), (True, 1, 1), (6, 0, 1), (6, 2, 1), (float('inf'), 1, 1)])
def test_absent_or_impossible_resource_counters_are_not_passed(cpu, peak, upper):
    with pytest.raises(ValueError):
        resource_status(cpu, peak, upper)
