"""Small real runner fixture; its evidence describes only the owned toy subject."""
import json
from pathlib import Path

from support.catalog_project import make_catalog_project, execute, check, NATIVE_IDS, LEGACY_ID
from verification_support.common import json_bytes

SUBJECT = '''import unittest
from pathlib import Path
import pytest

def test_native():
    p = Path("build/native_started")
    p.write_bytes(b"complete native result")
    assert p.read_bytes() == b"complete native result"

@pytest.mark.parametrize("value", [1, 2], ids=["first", "second"])
def test_parameter(value):
    p = Path("build/parameter_" + str(value))
    p.write_bytes(bytes([value]))
    assert p.read_bytes() == bytes([value])

class LegacyTests(unittest.TestCase):
    def test_legacy(self):
        p = Path("build/legacy_started")
        p.write_bytes(b"legacy result")
        self.assertEqual(p.read_bytes(), b"legacy result")
'''


def seed(root):
    root = make_catalog_project(root, ids=NATIVE_IDS, source=SUBJECT)
    directory = root / 'verification'
    first = json.loads((directory / 'requirements/SR-TC-0001.json').read_bytes())
    first.update(implementation_status='implemented', open_items=[])
    partial = {**first, 'test_case_id': 'SR-TC-0002', 'requirement_id': 'SR-REQ-0002',
               'implementation_status': 'partial', 'test_ids': [LEGACY_ID],
               'open_items': ['Remaining behavior is deliberately unimplemented.']}
    manual = {**first, 'test_case_id': 'SR-TC-0003', 'requirement_id': 'SR-REQ-0003',
              'implementation_status': 'open', 'method': 'manual_presentation',
              'oracle': {'kind': 'manual_presentation'}, 'test_ids': [],
              'not_automated_by_user_policy': 'TD-001', 'policy_excluded_scope': ['human_document_rendering'],
              'open_items': ['Actual human review remains absent.']}
    for case in (first, partial, manual):
        (directory / 'requirements' / (case['test_case_id'] + '.json')).write_bytes(json_bytes(case))
    index = json.loads((directory / 'catalog.json').read_bytes())
    index['test_case_ids'] = [c['test_case_id'] for c in (first, partial, manual)]
    index['required_test_case_ids'] = index['test_case_ids']
    (directory / 'catalog.json').write_bytes(json_bytes(index))
    code, collection = check(root)
    assert code == 0 and collection['tests_run'] == 0
    target = root / 'build/evidence.json'
    run = execute(root, 'run_tests.py', ['--workers', '2', '--evidence', str(target)])
    assert run.returncode == 0, run.stderr.decode(errors='replace')
    report = json.loads(target.read_bytes())
    assert report['suite_passed'] and report['tests_run'] == 4
    # Immutable bytes only; every caller gets fresh files and decoded values.
    files = tuple((p.relative_to(root).as_posix(), p.read_bytes()) for p in root.rglob('*')
                  if p.is_file() and p.relative_to(root).parts[0] != 'build'
                  and '__pycache__' not in p.parts)
    return files, json_bytes(collection), json_bytes(report)


def materialize(root, prepared):
    files, collected, evidence = prepared
    for name, raw in files:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    collection, report = json.loads(collected), json.loads(evidence)
    binding = {k: report[k] for k in ('run_id', 'tool_build_sha256', 'platform_sha256', 'configuration_sha256')}
    return root, collection, binding, report
