"""Current executable inventory, not Markdown, display or release-approval tests."""
import json
import pytest

from support.acceptance_catalog import seed, materialize
from support.catalog_project import execute, NATIVE_IDS, LEGACY_ID
from support.read_only import inventory
from verification_support.acceptance import assemble_acceptance
from verification_support.common import CatalogError, json_bytes, sha256


@pytest.fixture(scope='module')
def prepared(tmp_path_factory):
    return seed(tmp_path_factory.mktemp('acceptance-observed'))


@pytest.fixture
def current(tmp_path, prepared):
    return materialize(tmp_path / 'project', prepared)


def test_complete_mapping_and_collection_do_not_claim_execution(current):
    root, collection, _, _ = current
    before = inventory(root)
    report = assemble_acceptance(root, collection)
    assert report['catalog_complete'] and report['mapped_requirements'] == 3
    assert report['collected_tests'] == report['mapped_tests'] == 4
    assert report['unmapped_test_ids'] == []
    assert report['requirement_counts']['open'] == 3
    assert all(r['evidence_id'] is None for r in report['cases'])
    assert report['run_status'] == 'not_supplied'
    assert not report['behavior_evidence_complete'] and not report['release_approved']
    assert inventory(root) == before


def test_actual_native_and_legacy_results_bind_every_requirement(current):
    root, collection, binding, evidence = current
    before = inventory(root)
    report = assemble_acceptance(root, collection, binding=binding, report=evidence)
    assert report['run_status'] == 'current'
    assert [r['status'] for r in report['cases']] == ['passed', 'partial', 'open']
    assert report['cases'][0]['test_ids'] == NATIVE_IDS
    assert report['cases'][1]['test_ids'] == [LEGACY_ID]
    assert report['cases'][2]['test_ids'] == []
    assert report['cases'][2]['not_automated_by_user_policy'] == 'TD-001'
    assert report['cases'][2]['policy_excluded_scope'] == ['human_document_rendering']
    assert report['evidence_sha256'] == sha256(json_bytes(evidence))
    assert report['specification_sha256'] == evidence['specification_sha256']
    assert report['catalog_sha256'] == evidence['catalog_sha256']
    assert all(r['evidence_id'].startswith(binding['run_id'] + '/') for r in report['cases'][:2])
    assert report['cases'][2]['evidence_id'] is None
    assert not report['original_specification_accepted'] and not report['release_approved']
    assert inventory(root) == before


@pytest.mark.parametrize('field', ['run_id', 'tool_build_sha256', 'specification_sha256',
                                 'catalog_sha256', 'platform_sha256', 'configuration_sha256'])
def test_old_or_different_run_binding_cannot_be_relabelled_current(current, field):
    root, collection, binding, evidence = current
    evidence[field] = 'f' * 64
    before = json_bytes(evidence)
    report = assemble_acceptance(root, collection, binding=binding, report=evidence)
    assert report['run_status'] == 'stale'
    assert all(r['status'] == 'stale' and r['evidence_id'] is None for r in report['cases'])
    assert json_bytes(evidence) == before


@pytest.mark.parametrize('relative', ['tests/test_subject.py', 'verification/fixtures.json',
                                     'docs/specification/SpecRoad_Spezifikation.md'])
def test_changed_test_fixture_or_specification_rejects_old_collection(current, relative):
    root, collection, binding, evidence = current
    path = root / relative
    path.write_bytes(path.read_bytes() + b'\n')
    before = inventory(root)
    with pytest.raises(CatalogError):
        assemble_acceptance(root, collection, binding=binding, report=evidence)
    assert inventory(root) == before


def test_wrong_or_missing_case_evidence_cannot_be_hidden_by_suite_passed(current):
    root, collection, binding, evidence = current
    evidence['cases'].pop()
    report = assemble_acceptance(root, collection, binding=binding, report=evidence)
    assert report['run_status'] == 'invalid' and report['requirement_counts']['invalid'] == 3


def test_runtime_and_execution_hashes_bind_actual_original_data(current):
    root, collection, binding, evidence = current
    evidence['runtime']['implementation'] = 'other-runtime'
    report = assemble_acceptance(root, collection, binding=binding, report=evidence)
    assert report['run_status'] == 'invalid'


def test_cli_only_reads_existing_inputs_and_publishes_once(current):
    root, collection, binding, evidence = current
    build = root / 'build'; build.mkdir()
    for name, value in [('collection', collection), ('binding', binding), ('evidence', evidence)]:
        (build / (name + '.json')).write_bytes(json_bytes(value))
    args = ['--collection', str(build / 'collection.json'), '--binding', str(build / 'binding.json'),
            '--evidence', str(build / 'evidence.json'), '--output', str(build / 'acceptance.json')]
    before = inventory(root)
    result = execute(root, 'acceptance_catalog.py', args)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    report = json.loads((build / 'acceptance.json').read_bytes())
    assert report['run_status'] == 'current' and report['requirement_counts']['passed'] == 1
    original = (build / 'acceptance.json').read_bytes()
    assert execute(root, 'acceptance_catalog.py', args).returncode == 4
    assert (build / 'acceptance.json').read_bytes() == original
    before = {row[0]: row[1:] for row in before}
    after = {row[0]: row[1:] for row in inventory(root)}
    assert set(after) - set(before) == {'build/acceptance.json'}
    assert all(after[n] == v for n, v in before.items())
