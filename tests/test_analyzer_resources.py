"""Actual full reference measurements, bound to the current native build."""
import ast
import gzip
from pathlib import Path

from analyzer_benchmark.verify import assess, digest, load, object_bytes, process_inventory, verify_process_samples
from build_core import build_core

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'verification/fixtures/analyzer-resources-20261121'


def test_measured_full_adapter_stays_within_total_cpu_and_memory_limits(tmp_path):
    module, _ = build_core(ROOT / 'src', tmp_path / 'core')
    node = ast.parse((module / 'specroad/_build.py').read_bytes()).body[-1]
    build = ast.literal_eval(node.value)['build_sha256']
    records = load(EVIDENCE)
    for trial in ('run-3', 'run-4'):
        prefix = 'results/' + trial + '/'
        row = object_bytes(records[prefix + 'result.json'])
        parent = object_bytes(records[prefix + 'parent.json'])
        worker = object_bytes(records[prefix + 'worker.json'])
        original = [dict(p) for p in row['processes']]
        assert next(p for p in original if p['pid'] == parent['pid'])['role'] == 'worker'
        known = process_inventory(row, parent, worker)
        assert known[parent['pid']]['role'] == 'parent'
        assert known[worker['pid']]['role'] == 'worker'
        samples = [object_bytes(line) for line in gzip.decompress(records[prefix + 'rss-samples.jsonl.gz']).splitlines()]
        verify_process_samples(samples, known, parent['pid'], worker['pid'])
        assert row['processes'] == original
    result = assess(records, expected_build=build)
    assert result['status'] == 'passed'
    assert result['cpu_max_seconds'] == 6.92
    assert result['cpu_max_seconds'] <= 120
    assert result['sampled_simultaneous_rss_max_bytes'] == 236290048
    assert result['rss_upper_bound_bytes'] == 381419520 <= 512 * 1024**2
    assert result['release_approved'] is result['human_corpus_review_completed'] is False


def test_measured_sources_and_all_original_hash_chains_are_preserved():
    records = load(EVIDENCE)
    summary = object_bytes(records['summary.json'])
    for name, expected in summary['measurement_scripts_sha256'].items():
        assert digest(gzip.decompress((ROOT / 'tools/analyzer_benchmark/measured_v1' / (name + '.gz')).read_bytes())) == expected
    assert summary['apply_gate_passed'] is False
    assert summary['release_approved'] is summary['human_corpus_review_completed'] is False
