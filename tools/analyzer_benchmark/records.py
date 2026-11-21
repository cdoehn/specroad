"""Bound measurement bytes and numeric decoding; no analyzer execution."""
import gzip
from hashlib import sha256
import json
import math
from pathlib import Path, PurePosixPath
import re

TRIALS = ('warmup', 'run-1', 'run-2', 'run-3', 'run-4', 'run-5')


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
    require(type(receipt['format_version']) is int and receipt['format_version'] == 1 and receipt['kind'] == 'analyzer-resource-evidence-export',
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
