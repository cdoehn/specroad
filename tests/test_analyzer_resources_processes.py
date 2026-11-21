"""Reconcile the recorded v1 label race without dropping process evidence."""
from copy import deepcopy
import gzip

import pytest

from analyzer_benchmark.verify import load, object_bytes, process_inventory, verify_process_samples
from test_analyzer_resources import EVIDENCE


@pytest.fixture(scope='module')
def observed():
    records = load(EVIDENCE)
    prefix = 'results/run-3/'
    return (object_bytes(records[prefix + 'result.json']),
            object_bytes(records[prefix + 'parent.json']),
            object_bytes(records[prefix + 'worker.json']),
            [object_bytes(line) for line in gzip.decompress(records[prefix + 'rss-samples.jsonl.gz']).splitlines()])


@pytest.mark.parametrize('fault,reason', [
    ('missing-parent', 'incomplete_process_set'),
    ('missing-worker', 'incomplete_process_set'),
    ('missing-wrapper', 'incomplete_process_set'),
    ('extra-worker', 'incomplete_process_set'),
    ('extra-observer', 'incomplete_process_set'),
    ('duplicate-pid', 'duplicate_process_identity'),
    ('reused-pid', 'duplicate_process_identity'),
    ('same-parent-worker', 'duplicate_process_identity'),
    ('boolean-pid', 'invalid_process_identity'),
    ('zero-start', 'invalid_process_identity'),
    ('foreign-parent-label', 'wrong_process_role'),
    ('swapped-worker-label', 'wrong_process_role'),
    ('fake-observer-command', 'unknown_measurement_observer'),
    ('fake-observer-label', 'unknown_measurement_observer'),
    ('different-parent-ppid', 'wrong_process_ancestry'),
    ('disconnected-worker', 'wrong_process_ancestry'),
    ('cyclic-ancestry', 'wrong_process_ancestry'),
])
def test_final_label_reconciliation_never_hides_changed_process_membership(observed, fault, reason):
    row, parent, worker, _ = deepcopy(observed)
    known = {p['pid']: p for p in row['processes']}
    if fault.startswith('missing-'):
        target = {'missing-parent': parent['pid'], 'missing-worker': worker['pid'],
                  'missing-wrapper': worker['ppid']}[fault]
        row['processes'] = [p for p in row['processes'] if p['pid'] != target]
    elif fault.startswith('extra-'):
        row['processes'].append(dict(known[worker['pid']], pid=999999, role=(
            'worker' if fault == 'extra-worker' else 'gnu-time-observer')))
    elif fault in ('duplicate-pid', 'reused-pid'):
        duplicate = dict(known[parent['pid']])
        if fault == 'reused-pid':
            duplicate['start_ticks'] += 1
        row['processes'].append(duplicate)
    elif fault == 'same-parent-worker':
        worker['pid'] = parent['pid']
    elif fault == 'boolean-pid':
        known[parent['pid']]['pid'] = True
    elif fault == 'zero-start':
        known[parent['pid']]['start_ticks'] = 0
    elif fault == 'foreign-parent-label':
        known[parent['pid']]['role'] = 'unaccounted'
    elif fault == 'swapped-worker-label':
        known[worker['pid']]['role'] = 'parent'
    elif fault == 'fake-observer-command':
        known[worker['ppid']]['comm'] = 'another-program'
    elif fault == 'fake-observer-label':
        known[worker['ppid']]['role'] = 'worker'
    elif fault == 'different-parent-ppid':
        known[parent['pid']]['ppid'] = 999999
    elif fault == 'disconnected-worker':
        known[worker['ppid']]['ppid'] = parent['ppid']
    else:
        known[parent['ppid']]['ppid'] = worker['pid']
    with pytest.raises(ValueError, match=reason):
        process_inventory(row, parent, worker)


@pytest.mark.parametrize('fault,reason', [
    ('missing-parent', 'missing_parent_or_worker_rss'),
    ('missing-worker', 'missing_parent_or_worker_rss'),
    ('missing-all', 'missing_parent_or_worker_rss'),
    ('unknown-pid', 'unknown_rss_process'),
    ('observer-rss', 'unknown_rss_process'),
    ('duplicate-pid', 'duplicate_rss_process'),
    ('reused-pid', 'reused_or_mislabelled_pid'),
    ('swapped-role', 'reused_or_mislabelled_pid'),
    ('different-ppid', 'reused_or_mislabelled_pid'),
    ('wrong-sum', 'rss_sum_mismatch'),
    ('reversed-interval', 'invalid_rss_interval'),
])
def test_final_label_reconciliation_requires_both_consistent_observed_processes(observed, fault, reason):
    row, parent, worker, samples = deepcopy(observed)
    known = process_inventory(row, parent, worker)
    if fault in ('missing-parent', 'missing-worker'):
        target = parent['pid'] if fault == 'missing-parent' else worker['pid']
        for sample in samples:
            sample['processes'] = [p for p in sample['processes'] if p['pid'] != target]
            sample['rss_bytes'] = sum(p['rss_bytes'] for p in sample['processes'])
        samples = [s for s in samples if s['processes']]
    elif fault == 'missing-all':
        samples = []
    else:
        sample = next(s for s in samples if len(s['processes']) == 2)
        process = next(p for p in sample['processes'] if p['pid'] == parent['pid'])
        if fault == 'unknown-pid':
            process['pid'] = 999999
        elif fault == 'observer-rss':
            process['pid'] = parent['ppid']
        elif fault == 'duplicate-pid':
            sample['processes'].append(dict(process))
            sample['rss_bytes'] += process['rss_bytes']
        elif fault == 'reused-pid':
            process['start_ticks'] += 1
        elif fault == 'swapped-role':
            process['role'] = 'worker'
        elif fault == 'different-ppid':
            process['ppid'] = 999999
        elif fault == 'wrong-sum':
            sample['rss_bytes'] += 1
        else:
            sample['end_ns'] = sample['start_ns'] - 1
    with pytest.raises(ValueError, match=reason):
        verify_process_samples(samples, known, parent['pid'], worker['pid'])
