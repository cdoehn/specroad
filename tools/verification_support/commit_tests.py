"""Required tests for one Apply commit; selection does not execute tests."""
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import stat

from .ci_reference import _unique_object
from .common import json_bytes

POLICY = 'verification/apply_commit_policy.json'
POLICY_VALUE = {'format_version': 1, 'test_execution': 'apply_only',
                'selection': 'rotation_plus_required'}
SCOPE = 'stable_modulo_partition_with_latest_runtime_filter_and_required_tests'


def read_object(path):
    path = Path(path).absolute()
    for parent in path.parents:
        if not stat.S_ISDIR(parent.lstat().st_mode):
            raise ValueError('Linked test-plan parent')
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 2 * 1024 * 1024:
        raise ValueError('Unsafe test-plan file')
    raw = path.read_bytes()
    after = path.lstat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError('Test plan changed while reading')
    if raw.startswith(b'\xef\xbb\xbf'):
        raise ValueError('Test-plan BOM')
    def reject(value):
        raise ValueError('Nonfinite test-plan number')
    value = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=reject)
    if type(value) is not dict:
        raise ValueError('Expected a test-plan object')
    return raw, value


def plan_required(root):
    path = Path(root) / POLICY
    if not path.exists() and not path.is_symlink():
        return False  # Historical fixtures and pre-migration states.
    _, value = read_object(path)
    if value != POLICY_VALUE or type(value.get('format_version')) is not int:
        raise ValueError('Unknown Apply commit policy')
    return True


def validate_plan(value, commit_id):
    if (type(value) is not dict or set(value) != {
            'format_version', 'commit_id', 'test_ids', 'test_files', 'reason'}
            or type(value['format_version']) is not int or value['format_version'] != 1
            or type(commit_id) is not str or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', commit_id)
            or value['commit_id'] != commit_id
            or type(value['reason']) is not str or not value['reason'].strip()
            or len(value['reason']) > 4000):
        raise ValueError('Invalid or wrong-commit required test plan')
    for key in ('test_ids', 'test_files'):
        items = value[key]
        if (type(items) is not list or any(type(i) is not str or not i or '\n' in i or '\r' in i
                                         or '\0' in i for i in items)
                or len(items) != len(set(items))):
            raise ValueError('Invalid or duplicate required selectors')
    for name in value['test_files']:
        parts = PurePosixPath(name).parts
        if (not name.startswith('tests/') or not name.endswith('.py') or '\\' in name
                or '..' in parts or str(PurePosixPath(name)) != name):
            raise ValueError('Unsafe required test file')
    if not value['test_ids'] and not value['test_files']:
        raise ValueError('Each commit requires a justified nonempty test selection')
    return value


def resolve_required(plan, pairs):
    validate_plan(plan, plan.get('commit_id'))
    available_ids = set(pairs.values())
    available_files = {n.split('::', 1)[0] for n in pairs}
    if not set(plan['test_ids']) <= available_ids or not set(plan['test_files']) <= available_files:
        raise ValueError('Required test is unknown, removed or not collected')
    required = {n: i for n, i in sorted(pairs.items()) if i in plan['test_ids']
                or n.split('::', 1)[0] in plan['test_files']}
    if not required:
        raise ValueError('Empty required test selection')
    return required


def union_selection(filtered, pairs, plan, runtime_filter):
    required = resolve_required(plan, pairs)
    selected = dict(sorted({**filtered, **required}.items()))
    excluded = set(runtime_filter['excluded_test_ids'])
    evidence = {'test_plan': plan, 'test_plan_sha256': sha256(json_bytes(plan)).hexdigest(),
                'nodeid_to_test_id': required, 'rotation_tests': len(filtered),
                'extra_test_ids': sorted(set(required.values()) - set(filtered.values())),
                'restored_slow_test_ids': sorted(set(required.values()) & excluded)}
    return selected, evidence
