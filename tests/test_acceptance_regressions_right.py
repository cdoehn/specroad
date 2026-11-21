"""Nonpassing real observations and mandatory Apply union use one current binding."""
import pytest
from support.acceptance_catalog import seed, materialize
from support.catalog_project import NATIVE_IDS, LEGACY_ID
from support.read_only import inventory, no_write_attempts
from verification_support.acceptance import assemble_acceptance
from verification_support.common import CatalogError
from verification_support.commit_tests import resolve_required, union_selection
from verification_support.regressions import required_regression_plan


@pytest.fixture(scope='module', params=['passed', 'failed', 'skipped', 'expected_failure'])
def observed(request, tmp_path_factory):
    return request.param, seed(tmp_path_factory.mktemp('regression-run'), outcome=request.param, regressions=True)


def test_exact_real_failure_skip_and_xfail_remain_nonpassing_by_regression(observed, tmp_path):
    outcome, original = observed
    root, collection, binding, evidence = materialize(tmp_path / 'project', original)
    before = inventory(root)
    result = assemble_acceptance(root, collection, binding=binding, report=evidence)['regressions']
    status = {'passed': 'passed', 'failed': 'failed', 'skipped': 'open', 'expected_failure': 'open'}[outcome]
    assert result['all_passed'] is (outcome == 'passed')
    assert result['counts'][status] == (47 if outcome == 'passed' else 24)
    for index, row in enumerate(result['regressions']):
        assert row['status'] == (status if index % 2 == 0 else 'passed')
    assert not result['release_approved'] and inventory(root) == before


@pytest.fixture(scope='module')
def original(tmp_path_factory):
    return seed(tmp_path_factory.mktemp('regression-selection'), regressions=True)


def test_native_required_union_restores_every_slow_regression_and_deduplicates_overlap(original, tmp_path):
    root, collection, _, _ = materialize(tmp_path / 'project', original)
    before = inventory(root)
    with no_write_attempts():
        plan = required_regression_plan(root, collection, '20.c.R')
    pairs = collection['nodeid_to_test_id']
    required = resolve_required(plan, pairs)
    assert set(required.values()) == {NATIVE_IDS[0], LEGACY_ID}
    native_node = next(n for n, i in pairs.items() if i == NATIVE_IDS[0])
    selected, receipt = union_selection({native_node: NATIVE_IDS[0]}, pairs, plan,
        {'excluded_test_ids': [NATIVE_IDS[0], LEGACY_ID]})
    assert selected == required and len(selected) == 2
    assert receipt['restored_slow_test_ids'] == sorted([NATIVE_IDS[0], LEGACY_ID])
    assert inventory(root) == before


@pytest.mark.parametrize('fault', ['missing_inventory', 'changed_inventory', 'stale_collection', 'wrong_commit'])
def test_selection_cannot_hide_missing_or_stale_contract_inputs(original, tmp_path, fault):
    root, collection, _, _ = materialize(tmp_path / 'project', original)
    commit = '20.c.R'
    if fault == 'missing_inventory': (root / 'verification/regressions.json').unlink()
    elif fault == 'changed_inventory':
        path = root / 'verification/regressions.json'; path.write_bytes(path.read_bytes() + b'\n')
    elif fault == 'stale_collection': collection['source_sha256'] = 'a' * 64
    elif fault == 'wrong_commit': commit = '../not-a-commit'
    before = inventory(root)
    with pytest.raises((CatalogError, ValueError)): required_regression_plan(root, collection, commit)
    assert inventory(root) == before
