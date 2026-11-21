"""Binding-engine fixtures describe their tiny subject, not the real 47 contracts."""
import json
import pytest

from support.acceptance_catalog import seed, materialize
from support.catalog_project import check
from support.read_only import inventory
from verification_support.acceptance import assemble_acceptance
from verification_support.common import CatalogError, json_bytes
from verification_support.regressions import load_regressions


@pytest.fixture(scope='module')
def observed(tmp_path_factory):
    return seed(tmp_path_factory.mktemp('regression-observed'), regressions=True)


@pytest.fixture
def current(tmp_path, observed):
    return materialize(tmp_path / 'project', observed)


def test_all_bindings_remain_open_without_execution(current):
    root, collection, _, _ = current
    before = inventory(root)
    result = assemble_acceptance(root, collection)['regressions']
    assert result['counts']['open'] == 47 and not result['all_passed']
    assert all(r['test_outcomes'] == {} and r['evidence_id'] is None for r in result['regressions'])
    assert inventory(root) == before


def test_actual_run_retains_every_exact_regression_identity_and_outcome(current):
    root, collection, binding, evidence = current
    before = inventory(root)
    result = assemble_acceptance(root, collection, binding=binding, report=evidence)['regressions']
    assert [r['regression_id'] for r in result['regressions']] == ['R-%02d' % i for i in range(1, 48)]
    assert result['counts']['passed'] == 47 and result['all_passed']
    for row in result['regressions']:
        assert row['test_outcomes'] == {t: evidence['test_outcomes'][t] for t in row['test_ids']}
        assert row['evidence_id'] == binding['run_id'] + '/' + row['regression_id']
    assert not result['release_approved'] and inventory(root) == before


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'empty', 'uncollected', 'duplicate_test',
    'wrong_requirement', 'wrong_verification', 'wrong_spec', 'bad_version', 'unknown_field'])
def test_incomplete_or_ambiguous_bindings_cannot_stand_for_all_contracts(current, fault):
    root, collection, _, _ = current
    path = root / 'verification/regressions.json'
    value = json.loads(path.read_bytes())
    row = value['regressions'][0]
    if fault == 'missing': value['regressions'].pop()
    elif fault == 'duplicate': value['regressions'][-1] = row
    elif fault == 'empty': row['test_ids'] = []
    elif fault == 'uncollected': row['test_ids'] = ['tests/not_collected.py::test_unknown']
    elif fault == 'duplicate_test': row['test_ids'] *= 2
    elif fault == 'wrong_requirement': row['requirement_id'] = 'SR-REQ-0001'
    elif fault == 'wrong_verification': row['verification_id'] = 'SR-VER-0001'
    elif fault == 'wrong_spec': value['specification_sha256'] = 'f' * 64
    elif fault == 'bad_version': value['format_version'] = True
    elif fault == 'unknown_field': row['passed'] = True
    path.write_bytes(json_bytes(value))
    before = inventory(root)
    with pytest.raises(CatalogError): load_regressions(root, collection)
    assert inventory(root) == before


def test_edited_bindings_do_not_reuse_an_old_current_report(current):
    root, collection, binding, evidence = current
    path = root / 'verification/regressions.json'
    value = json.loads(path.read_bytes()); value['regressions'][0]['test_ids'] = value['regressions'][1]['test_ids']
    path.write_bytes(json_bytes(value))
    with pytest.raises(CatalogError):
        assemble_acceptance(root, collection, binding=binding, report=evidence)
    (root / 'build').mkdir()
    code, fresh = check(root)
    assert code == 0 and fresh['tests_run'] == 0
    result = assemble_acceptance(root, fresh, binding=binding, report=evidence)['regressions']
    assert result['counts']['stale'] == 47 and not result['all_passed']
