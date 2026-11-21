"""Absent/nonpassing results, malformed originals and passive publication limits."""
import json
import pytest

from support.acceptance_catalog import seed, materialize
from support.catalog_project import execute, NATIVE_IDS
from support.read_only import inventory, no_write_attempts
from verification_support.acceptance import assemble_acceptance
from verification_support.common import CatalogError, json_bytes


@pytest.fixture(scope='module', params=['passed', 'failed', 'skipped', 'expected_failure'])
def observed(request, tmp_path_factory):
    if request.param == 'failed':
        return request.param, request.getfixturevalue('failed_original')
    return request.param, seed(tmp_path_factory.mktemp('acceptance-boundary'), outcome=request.param)


@pytest.fixture(scope='module')
def failed_original(tmp_path_factory):
    return seed(tmp_path_factory.mktemp('acceptance-failed'), outcome='failed')


def test_real_nonpassing_run_keeps_exact_outcome_without_promoting_inventory(observed, tmp_path):
    outcome, prepared = observed
    root, collection, binding, evidence = materialize(tmp_path / 'project', prepared)
    observation = evidence['observation']
    assert observation['errors'] == (['worker_nonzero_exit'] if outcome == 'failed' else [])
    assert observation['pytest_exit_code'] == (1 if outcome == 'failed' else 0)
    before = inventory(root)
    with no_write_attempts():
        report = assemble_acceptance(root, collection, binding=binding, report=evidence)
    assert report['run_status'] == 'current'
    expected = {'passed': 'passed', 'failed': 'failed', 'skipped': 'open', 'expected_failure': 'open'}[outcome]
    assert report['cases'][0]['status'] == expected
    assert evidence['test_outcomes'][NATIVE_IDS[0]] == outcome
    assert report['cases'][1]['status'] == 'partial'
    assert report['cases'][2]['status'] == 'open'
    assert report['cases'][2]['excluded_scope_status'] == 'not_automated_by_user_policy'
    assert not any(c['original_requirement_accepted'] for c in report['cases'])
    assert not report['behavior_evidence_complete'] and not report['release_approved']
    assert inventory(root) == before


@pytest.mark.parametrize('mutation', [
    'worker_crash', 'collection_error', 'unknown_error', 'duplicate_marker',
    'zero_exit', 'infrastructure_exit', 'fake_suite_pass', 'fake_observed_pass',
    'all_passed', 'only_skipped', 'only_expected_failure',
])
def test_worker_failure_marker_cannot_hide_invalid_or_promoted_evidence(failed_original, tmp_path, mutation):
    root, collection, binding, evidence = materialize(tmp_path / 'project', failed_original)
    observed = evidence['observation']
    assert observed['errors'] == ['worker_nonzero_exit']
    assert observed['pytest_exit_code'] == 1 and not evidence['suite_passed']
    if mutation in ('worker_crash', 'collection_error', 'unknown_error'):
        observed['errors'].append(mutation)
    elif mutation == 'duplicate_marker': observed['errors'].append('worker_nonzero_exit')
    elif mutation == 'zero_exit': observed['pytest_exit_code'] = 0
    elif mutation == 'infrastructure_exit': observed['pytest_exit_code'] = 3
    elif mutation == 'fake_suite_pass': evidence['suite_passed'] = True
    elif mutation == 'fake_observed_pass': observed['suite_passed'] = True
    else:
        # Keep per-case counts and outcomes consistent; only the unexplained
        # nonzero worker exit must prevent this report from becoming current.
        outcome = {'all_passed': 'passed', 'only_skipped': 'skipped',
                   'only_expected_failure': 'expected_failure'}[mutation]
        for outcomes in (evidence['test_outcomes'], observed['test_outcomes'],
                         evidence['cases'][0]['test_outcomes']):
            outcomes[NATIVE_IDS[0]] = outcome
        status = 'passed' if outcome == 'passed' else 'open'
        evidence['cases'][0]['status'] = status
        evidence['requirement_counts']['failed'] -= 1
        evidence['requirement_counts'][status] += 1
    original = json_bytes(evidence)
    before = inventory(root)
    with no_write_attempts():
        report = assemble_acceptance(root, collection, binding=binding, report=evidence)
    assert report['run_status'] == 'invalid'
    assert all(c['status'] == 'invalid' and c['evidence_id'] is None for c in report['cases'])
    assert not report['behavior_evidence_complete'] and not report['release_approved']
    assert json_bytes(evidence) == original and inventory(root) == before


@pytest.fixture(scope='module')
def original(tmp_path_factory):
    return seed(tmp_path_factory.mktemp('acceptance-original'))


@pytest.fixture
def current(tmp_path, original):
    return materialize(tmp_path / 'project', original)


@pytest.mark.parametrize('mutation', [
    'empty_outcomes', 'missing_node', 'wrong_alias', 'duplicate_node', 'fake_suite_success',
    'missing_worker', 'duplicate_worker', 'wrong_worker_count', 'boolean_worker_count',
    'boolean_requirement_count', 'wrong_case_outcome', 'unknown_outcome', 'collection_error',
    'wrong_exit', 'unsupported_version', 'changed_execution', 'wrong_case_status', 'duplicate_case',
])
def test_internally_inconsistent_original_run_never_passes(current, mutation):
    root, collection, binding, evidence = current
    observed = evidence['observation']
    if mutation == 'empty_outcomes': evidence['test_outcomes'] = {}
    elif mutation == 'missing_node': observed['nodeids'].pop()
    elif mutation == 'wrong_alias': observed['nodeid_to_test_id'][observed['nodeids'][0]] = 'uncollected'
    elif mutation == 'duplicate_node': observed['nodeids'][-1] = observed['nodeids'][0]
    elif mutation == 'fake_suite_success': evidence['suite_passed'] = 1
    elif mutation == 'missing_worker': observed['workers'].pop()
    elif mutation == 'duplicate_worker': observed['workers'].append(observed['workers'][0])
    elif mutation == 'wrong_worker_count': observed['worker_test_counts'][observed['workers'][0]] += 1
    elif mutation == 'boolean_worker_count': observed['worker_test_counts'][observed['workers'][0]] = True
    elif mutation == 'boolean_requirement_count': evidence['requirement_counts']['passed'] = True
    elif mutation == 'wrong_case_outcome': evidence['cases'][0]['test_outcomes'][NATIVE_IDS[0]] = 'failed'
    elif mutation == 'unknown_outcome': evidence['test_outcomes'][NATIVE_IDS[0]] = 'invented_success'
    elif mutation == 'collection_error': observed['errors'].append('inconsistent_worker_collection')
    elif mutation == 'wrong_exit': observed['pytest_exit_code'] = 5
    elif mutation == 'unsupported_version': evidence['report_format_version'] = 3
    elif mutation == 'changed_execution': evidence['execution']['workers'] += 1
    elif mutation == 'wrong_case_status': evidence['cases'][1]['status'] = 'passed'
    elif mutation == 'duplicate_case': evidence['cases'][-1] = evidence['cases'][0]
    original_bytes = json_bytes(evidence)
    report = assemble_acceptance(root, collection, binding=binding, report=evidence)
    assert report['run_status'] == 'invalid'
    assert all(c['status'] == 'invalid' and c['evidence_id'] is None for c in report['cases'])
    assert json_bytes(evidence) == original_bytes and not report['behavior_evidence_complete']


@pytest.mark.parametrize('mutation', ['absent', 'incomplete', 'bad_uuid', 'missing_hash'])
def test_explicit_complete_selected_binding_is_required(current, mutation):
    root, collection, binding, evidence = current
    if mutation == 'absent': binding = None
    elif mutation == 'incomplete': binding.pop('configuration_sha256')
    elif mutation == 'bad_uuid': binding['run_id'] = 'old'
    elif mutation == 'missing_hash': binding['platform_sha256'] = None
    with pytest.raises(CatalogError):
        assemble_acceptance(root, collection, binding=binding, report=evidence)


@pytest.mark.parametrize('variant', ['duplicate_key', 'nonfinite', 'linked_input', 'protected_output'])
def test_cli_rejects_invalid_files_without_changing_owned_inputs(current, variant):
    root, collection, _, _ = current
    build = root / 'build'; build.mkdir()
    source = build / 'collection.json'
    source.write_bytes(json_bytes(collection))
    target = build / 'acceptance.json'
    if variant == 'duplicate_key': source.write_bytes(b'{"format_version":1,"format_version":1}')
    elif variant == 'nonfinite': source.write_bytes(b'{"value":NaN}')
    elif variant == 'linked_input':
        link = build / 'linked.json'; link.symlink_to(source); source = link
    elif variant == 'protected_output': target = root / 'tests/acceptance.json'
    before = inventory(root)
    result = execute(root, 'acceptance_catalog.py', ['--collection', str(source), '--output', str(target)])
    assert result.returncode == 4
    assert inventory(root) == before


def test_original_selected_report_is_never_changed_when_inventory_is_published(current):
    root, collection, binding, evidence = current
    build = root / 'build'; build.mkdir()
    originals = {'collection': collection, 'binding': binding, 'evidence': evidence}
    for name, value in originals.items():
        (build / (name + '.json')).write_bytes(json_bytes(value))
    evidence['catalog_sha256'] = 'f' * 64
    (build / 'evidence.json').write_bytes(json_bytes(evidence))
    before = inventory(root)
    args = ['--collection', str(build / 'collection.json'), '--evidence', str(build / 'evidence.json'),
            '--binding', str(build / 'binding.json'), '--output', str(build / 'acceptance.json')]
    assert execute(root, 'acceptance_catalog.py', args).returncode == 1
    report = json.loads((build / 'acceptance.json').read_bytes())
    assert report['run_status'] == 'stale' and report['requirement_counts']['stale'] == 3
    after = {r[0]: r[1:] for r in inventory(root)}
    assert all(after[r[0]] == r[1:] for r in before)
