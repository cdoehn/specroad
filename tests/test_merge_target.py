"""17.j.W: native full-project gates over real read-only merge candidates."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.merge import prepare_merge_target
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.errors import ModelError
from specroad.recovery._validation import validate_project
from support.merge_target import small_seed as seed, replace, inputs, target
from support.profile_composition import profile, lint
from support.read_only import inventory
from support.relations import aid, edge
from test_merge_sources import read_only_sources


@pytest.mark.parametrize('mode', ['unchanged', 'adopted', 'combined'])
def test_complete_valid_target_preserves_exact_candidates_and_native_root_without_writes(tmp_path, mode):
    original = seed(tmp_path/'seed')
    ours = replace(original, 'goal', title='ours', revision=3) if mode == 'combined' else original
    theirs = replace(original, 'goal', owner='theirs', revision=7) if mode != 'unchanged' else original
    values = inputs(tmp_path/'inputs', [original, ours, theirs])
    metadata = values[-1]
    before = inventory(tmp_path)
    with read_only_sources():
        result = target(values)
        model, root = validate_project(result.files)
    assert inventory(tmp_path) == before
    assert result.target_validated and result.data['checks_complete']
    assert result.files == metadata.files
    assert result.data['expected_target_model_root_sha256'] == root
    assert result.data['metadata_candidate_sha256'] == metadata.sha256
    assert result.data['input_plan_sha256'] == values[2].sha256
    assert result.data['source_bindings_sha256'] == values[0].sha256
    report = result.data['validation']['source_report']
    assert report['requested_ids'] is None and report['document_role_scope'] == 'full_project'
    assert report['source_count'] == len(model.documents)
    assert report['model_valid'] is True and report['checks_complete']
    assert result.data['conflicts'] == [] and result.data['pending_gates'] == ['publication']
    assert not result.ready and not result.write_authorized and not result.approval_granted
    assert sha256(result.canonical_bytes).hexdigest() == result.sha256


@pytest.mark.parametrize('fail_on,valid', [('error', True), ('warning', False), ('info', False)])
def test_bound_target_project_policy_controls_real_profile_warning(tmp_path, fail_on, valid):
    rule = lint('target:warning', value=False); rule['artifact_types'] = ['goal']
    files = seed(tmp_path/'seed', profiles=(profile('target-policy', lint_rules=[rule]),), fail_on=fail_on)
    values = inputs(tmp_path/'inputs', [files]*3)
    with read_only_sources():
        result = target(values)
    assert result.target_validated is valid
    findings = result.data['validation']['source_report']['stages']
    assert any(d['reason'] == 'profile_lint_predicate_false' for s in findings for d in s['diagnostics'])
    assert result.data['checks_complete']
    if not valid:
        with pytest.raises(ModelError, match='merge_target_not_validated'):
            result.files
    from specroad.cli.result_schemas import validate_result_document
    validate_result_document('model-validation-v1',result.data['validation'])
    assert result.data['validation']['fail_on'] == fail_on
    # Preserve this stable test identity while checking the actual info and
    # empty-finding boundaries through native profile execution as well.
    for satisfied in (False, True):
        info_rule = lint('target:info',severity='info',value=satisfied)
        info_rule['artifact_types'] = ['goal']
        name = 'satisfied' if satisfied else 'info-only'
        info_files = seed(tmp_path/name,profiles=(profile('target-info',lint_rules=[info_rule]),),fail_on=fail_on)
        info_values = inputs(tmp_path/(name+'-inputs'),[info_files]*3)
        before = inventory(tmp_path)
        with read_only_sources(): info_result = target(info_values)
        assert inventory(tmp_path) == before
        assert info_result.target_validated is (satisfied or fail_on != 'info')
        assessed = info_result.data['validation']
        assert assessed['fail_on'] == fail_on and assessed['source_report']['model_valid'] is True
        assert info_result.data['checks_complete']
        if satisfied:
            assert not assessed['diagnostics']
        else:
            assert assessed['diagnostics'] and {d['severity'] for d in assessed['diagnostics']} == {'info'}
        validate_result_document('model-validation-v1',assessed)
        assert not info_result.ready and not info_result.approval_granted and not info_result.write_authorized
        if info_result.target_validated:
            assert info_result.files == info_values[-1].files
        else:
            with pytest.raises(ModelError,match='merge_target_not_validated'): info_result.files


def test_unresolved_field_conflict_has_no_target_or_native_validation_claim(tmp_path):
    files = seed(tmp_path/'seed')
    values = inputs(tmp_path/'inputs', [replace(files,'goal',title=role) for role in ('base','ours','theirs')])
    before = inventory(tmp_path)
    with read_only_sources(): result = target(values)
    assert not result.target_validated and not result.data['checks_complete']
    assert result.data['validation'] is None and result.data['conflicts'] == values[-1].data['conflicts']
    assert result.data['expected_target_model_root_sha256'] is None
    assert result.data['pending_gates'] == ['target_validation', 'publication']
    with pytest.raises(ModelError): result.files
    assert inventory(tmp_path) == before


def test_unchanged_artifacts_with_hierarchy_cycle_are_still_checked(tmp_path):
    from support.domain import domain_value
    from support.records import record_value
    first = domain_value('need', id=aid('need', 1),
        relations=[edge(kind='refines', target=aid('need', 2), number=1)])
    second = domain_value('need', id=aid('need', 2),
        relations=[edge(kind='refines', target=aid('need', 1), number=2)])
    files = seed(tmp_path/'seed', values=[record_value('document'), first, second])
    values = inputs(tmp_path/'inputs', [files]*3)
    assert values[-1].data['metadata_complete']
    with read_only_sources(): result = target(values)
    assert not result.target_validated
    assert any(c['reason'] == 'relation_hierarchy_cycle' for c in result.data['conflicts'])
    with pytest.raises(ModelError): result.files


def test_profile_error_and_absent_primary_document_cannot_be_ignored(tmp_path):
    from support.domain import domain_value
    rule = lint('target:error', value=False, severity='error'); rule['artifact_types'] = ['goal']
    files = seed(tmp_path/'seed', profiles=(profile('target-policy',lint_rules=[rule]),))
    values = inputs(tmp_path/'policy', [files]*3)
    with read_only_sources(): result = target(values)
    assert not result.target_validated
    assert any(c['reason'] == 'profile_lint_predicate_false' for c in result.data['conflicts'])
    incomplete = seed(tmp_path/'without-document', values=[domain_value('goal')])
    values = inputs(tmp_path/'missing-document', [incomplete]*3)
    with read_only_sources(): result = target(values)
    assert not result.target_validated
    assert result.data['conflicts'] and 'target_validation' in result.data['pending_gates']


@pytest.mark.parametrize('which', ['plan', 'metadata'])
def test_input_byte_hash_is_checked_before_any_target_claim(tmp_path, which):
    files = seed(tmp_path/'seed'); sources, history, plan, metadata = inputs(tmp_path/'inputs', [files]*3)
    expected = {'expected_plan_sha256':plan.sha256, 'expected_metadata_sha256':metadata.sha256}
    expected['expected_'+which+'_sha256'] = '0'*64
    with read_only_sources(), pytest.raises(ModelError, match='hash_mismatch'):
        prepare_merge_target(metadata.canonical_bytes, plan.canonical_bytes, sources, history=history, **expected)


def test_forged_metadata_is_recomputed_even_with_updated_outer_hash(tmp_path):
    files = seed(tmp_path/'seed'); sources, history, plan, metadata = inputs(tmp_path/'inputs', [files]*3)
    value = metadata.data; value['expected_target_model_root_sha256'] = '0'*64; raw = jcs(value)
    with read_only_sources(), pytest.raises(ModelError, match='merge_metadata_binding_mismatch'):
        prepare_merge_target(raw, plan.canonical_bytes, sources, history=history,
            expected_metadata_sha256=sha256(raw).hexdigest(), expected_plan_sha256=plan.sha256)


def test_passive_values_are_detached_and_no_truthiness_claims_publication(tmp_path):
    files = seed(tmp_path/'seed'); values = inputs(tmp_path/'inputs', [files]*3)
    result = target(values); original = result.canonical_bytes
    result.data['target_validated'] = False; result.files.clear()
    assert result.canonical_bytes == original and result.files == files
    with pytest.raises(FrozenInstanceError): result._encoded = b'{}'
    with pytest.raises(TypeError): bool(result)
