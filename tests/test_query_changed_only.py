"""Real Git-derived changes, native validation closure and bound profile rules."""
from copy import deepcopy
import importlib

import pytest

from specroad.model.errors import ModelError
from specroad.query import check_changed_sources
from specroad.validation import ModelGate
from support.domain import approved_value, domain_value
from support.model import configuration_value
from support.model_validation import edge
from support.profile_composition import lint
from support.profiles import encoded, profile_data
from support.read_only import inventory, no_write_attempts
from support.relations import aid
from test_query_comparison_sources import capture, source, source_files

module = importlib.import_module('specroad.query.changed_only')
PROFILE_PATHS = {'core@0.2.0': 'profiles/core.json'}


def goal(number, **changes):
    return domain_value('goal', id=aid('goal', number=number), **changes)


def pair(tmp_path, before, after, *, old_profile=None, new_profile=None,
         old_config=None, new_config=None, old_extra=None, new_extra=None):
    profile = profile_data(profile_id='core') if old_profile is None else old_profile
    later = profile if new_profile is None else new_profile
    old_files = source_files(*before, configuration=old_config,
        extra={'profiles/core.json': encoded(profile), **(old_extra or {})})
    new_files = source_files(*after, configuration=new_config,
        extra={'profiles/core.json': encoded(later), **(new_extra or {})})
    return (capture(source(tmp_path / 'before', 'git', old_files)),
            capture(source(tmp_path / 'after', 'local', new_files)))


def run(before, after, **options):
    return check_changed_sources(before, after, profile_paths=PROFILE_PATHS,
                                 core_key='core@0.2.0', **options).data


def stages(result):
    return {stage['stage']: stage for stage in result['validation']['stages']}


def rule(value, *, severity='error'):
    result = lint('fixture:goal', value=value, severity=severity)
    result['artifact_types'] = ['goal']
    return result


def test_changed_target_pulls_incoming_and_transitive_dependencies(tmp_path):
    a, b, c, outside = [goal(i) for i in range(1, 5)]
    a['relations'] = [edge(b, number=1)]
    b['relations'] = [edge(c, number=2)]
    current = deepcopy([a, b, c, outside]);current[2]['statement'] = 'Changed target'
    before, after = pair(tmp_path, [a, b, c, outside], current)
    original = inventory(tmp_path)
    with no_write_attempts():
        result = run(before, after)
    expected = sorted(v['id'] for v in (a, b, c))
    assert result['changed_artifact_ids'] == result['seed_artifact_ids'] == [c['id']]
    assert result['checked_artifact_ids'] == expected
    assert result['dependency_artifact_ids'] == sorted((a['id'], b['id']))
    assert result['validation']['requested_ids'] == [c['id']]
    assert result['validation']['checked_ids'] == result['core_lint']['checked_ids'] == expected
    assert result['validation']['source_count'] == 4
    assert result['validation']['structural_scope'] == 'all_supplied_documents'
    assert result['validation']['validation_scope'] == 'dependency_expanded_loaded_scope'
    assert result['passed'] is True and result['checks_complete']
    assert not result['full_project_validation'] and not result['full_lint']
    assert not result['approval_granted'] and not result['write_authorized']
    assert inventory(tmp_path) == original


def test_native_profile_rule_edit_checks_unchanged_artifacts_and_finds_failure(tmp_path):
    values = [goal(1), goal(2)]
    old = profile_data(profile_id='core', lint_rules=[rule(True)])
    new = profile_data(profile_id='core', lint_rules=[rule(False)])
    before, after = pair(tmp_path, values, values, old_profile=old, new_profile=new)
    result = run(before, after)
    expected = sorted(v['id'] for v in values)
    assert result['changed_artifact_ids'] == []
    assert result['changed_resource_paths'] == ['profiles/core.json']
    assert result['seed_reasons'] == ['profile_resources_changed_conservative']
    assert result['seed_artifact_ids'] == result['checked_artifact_ids'] == expected
    findings = stages(result)['profile_lint']['diagnostics']
    assert {d['artifact_id'] for d in findings} == set(expected)
    assert {d['code'] for d in findings} == {'PROFILE_LINT'}
    assert {d['reason'] for d in findings} == {'profile_lint_predicate_false'}
    assert result['checks_complete'] and result['passed'] is False


def test_declared_gate_dependency_can_find_failure_outside_the_changed_file(tmp_path):
    a, b, outside = goal(1, title='forbidden'), goal(2), goal(3)
    current = deepcopy([a, b, outside]);current[1]['statement'] = 'Changed input'
    before, after = pair(tmp_path, [a, b, outside], current)

    def dependencies(context):
        return context.dependency_result({i: [b['id']] if i == a['id'] else [] for i in context.subjects})

    def check(context):
        return context.result([{'reason': 'forbidden_title', 'severity': 'error', 'artifact_id': i}
                               for i in context.subjects if context.artifact(i)['title'] == 'forbidden'])

    result = run(before, after, gates=[ModelGate('extension:titles', 'v1', dependencies, check)])
    assert result['seed_artifact_ids'] == [b['id']]
    assert result['checked_artifact_ids'] == sorted((a['id'], b['id']))
    assert result['dependency_artifact_ids'] == [a['id']]
    assert stages(result)['extension:titles']['diagnostics'][0]['artifact_id'] == a['id']
    assert result['passed'] is False


def test_added_artifact_is_selected_without_a_disconnected_unchanged_artifact(tmp_path):
    before, after = pair(tmp_path, [goal(1)], [goal(1), goal(2)])
    result = run(before, after)
    assert result['changed_artifact_ids'] == result['checked_artifact_ids'] == [goal(2)['id']]
    assert result['dependency_artifact_ids'] == []
    assert result['passed'] is True


def test_semantic_configuration_change_conservatively_selects_current_artifacts(tmp_path):
    values = [goal(1), goal(2)]
    before, after = pair(tmp_path, values, values,
        new_config=configuration_value(validation_policy={'fail_on': 'warning'}))
    result = run(before, after)
    assert result['configuration_changed'] and result['changed_artifact_ids'] == []
    assert result['seed_reasons'] == ['project_configuration_changed_conservative']
    assert result['checked_artifact_ids'] == sorted(v['id'] for v in values)
    assert not result['full_project_validation']


def test_presentation_only_configuration_change_does_not_claim_a_validation_run(tmp_path):
    values = [goal(1)]
    before, after = pair(tmp_path, values, values, new_config=configuration_value(default_locale='en-US'))
    result = run(before, after)
    assert result['status'] == 'no_changes' and not result['configuration_changed']
    assert result['checked_artifact_ids'] == [] and result['validation'] is None
    assert result['passed'] is None and not result['checks_complete']


def test_no_changes_do_not_execute_semantic_callbacks_or_claim_a_full_project_pass(tmp_path):
    before, after = pair(tmp_path, [goal(1)], [goal(1)])
    def forbidden(context):
        pytest.fail('No changed scope must not pretend to have executed semantic checks')
    result = run(before, after, gates=[ModelGate('extension:probe', 'v1', forbidden, forbidden)])
    assert result['status'] == 'no_changes'
    assert result['validation'] is result['validation_assessment'] is result['core_lint'] is None
    assert result['passed'] is None and not result['full_project_validation']


def test_removed_target_preserves_native_dangling_reference_failure(tmp_path):
    a, b = goal(1), goal(2);a['relations'] = [edge(b)]
    before, after = pair(tmp_path, [a, b], [a])
    result = run(before, after)
    assert result['removed_artifact_ids'] == [b['id']]
    assert result['seed_artifact_ids'] == [a['id']]
    assert result['seed_reasons'] == ['removed_artifacts_conservative']
    assert result['passed'] is False and result['core_lint'] is None
    assert result['validation']['model_valid'] is False
    assert stages(result)['identities_references']['status'] == 'failed'


def test_complete_removal_reports_empty_current_scope_without_fabricated_checks(tmp_path):
    before, after = pair(tmp_path, [goal(1)], [])
    result = run(before, after)
    assert result['status'] == 'no_current_artifacts'
    assert result['removed_artifact_ids'] == [goal(1)['id']]
    assert result['checked_artifact_ids'] == [] and result['validation'] is None
    assert result['passed'] is None and not result['checks_complete']


@pytest.mark.parametrize('path', ['rules/other.json', 'mappings/other.json', 'profiles/unused.json'])
def test_unsupported_resource_delta_cannot_disappear_from_the_check(tmp_path, path):
    before, after = pair(tmp_path, [goal(1)], [goal(1)],
                         old_extra={path: b'old'}, new_extra={path: b'new'})
    with pytest.raises(ModelError) as caught:
        run(before, after)
    assert caught.value.reason == 'changed_resource_semantics_unavailable' and caught.value.path == path


@pytest.mark.parametrize('paths,reason', [({}, 'changed_profile_paths_required'),
    ({'core@0.2.0': 'profiles/absent.json'}, 'changed_profile_source_missing'),
    ({'wrong@0.2.0': 'profiles/core.json'}, 'changed_profile_identity_mismatch'),
    ({'core@0.2.0': 'specroad.json'}, 'changed_profile_source_missing')])
def test_profile_inputs_must_bind_exact_captured_resource_bytes(tmp_path, paths, reason):
    before, after = pair(tmp_path, [goal(1)], [goal(1, statement='Changed')])
    with pytest.raises(ModelError) as caught:
        check_changed_sources(before, after, profile_paths=paths, core_key='core@0.2.0')
    assert caught.value.reason == reason


@pytest.mark.parametrize('base', [None, {}, 'HEAD'])
def test_missing_or_unresolved_base_fails_before_any_validation(tmp_path, monkeypatch, base):
    _, after = pair(tmp_path, [goal(1)], [goal(1, statement='Changed')])
    monkeypatch.setattr(module, 'validate_model', lambda *a, **k: pytest.fail('No base was resolved'))
    with pytest.raises(ModelError) as caught:
        run(base, after)
    assert caught.value.reason == 'changed_comparison_sources_required'


def test_local_snapshot_cannot_substitute_for_a_git_base(tmp_path):
    _, after = pair(tmp_path, [goal(1)], [goal(1)])
    with pytest.raises(ModelError) as caught:
        run(after, after)
    assert caught.value.reason == 'changed_git_base_required'


def test_foreign_project_identity_is_rejected_before_semantic_checks(tmp_path, monkeypatch):
    before, after = pair(tmp_path, [goal(1)], [goal(1)], new_config=configuration_value(project_id='foreign'))
    monkeypatch.setattr(module, 'validate_model', lambda *a, **k: pytest.fail('Foreign comparison'))
    with pytest.raises(ModelError) as caught:
        run(before, after)
    assert caught.value.reason == 'comparison_project_mismatch'


@pytest.mark.parametrize('fail_on,strict,passed', [('error', False, True), ('warning', False, False), ('error', True, False)])
def test_native_profile_warning_obeys_the_selected_failure_threshold(tmp_path, fail_on, strict, passed):
    old = profile_data(profile_id='core', lint_rules=[rule(True, severity='warning')])
    new = profile_data(profile_id='core', lint_rules=[rule(False, severity='warning')])
    before, after = pair(tmp_path, [goal(1)], [goal(1)], old_profile=old, new_profile=new)
    result = run(before, after, fail_on=fail_on, strict=strict)
    assert result['passed'] is passed and result['checks_complete']
    assert result['validation_assessment']['source_report'] == result['validation']
    assert stages(result)['profile_lint']['diagnostics'][0]['severity'] == 'warning'


def test_unavailable_required_semantic_services_remain_incomplete(tmp_path):
    current = approved_value('goal', id=goal(1)['id'])
    before, after = pair(tmp_path, [goal(1)], [current])
    result = run(before, after)
    assert result['status'] == 'incomplete' and not result['checks_complete']
    assert result['passed'] is not True
    assert any(s['status'] == 'unavailable' for s in result['validation']['stages'])
    assert result['core_lint'] is not None


def test_result_is_owned_and_bound_to_both_sources_and_actual_checked_bytes(tmp_path):
    before, after = pair(tmp_path, [goal(1)], [goal(1, statement='Changed')])
    result = check_changed_sources(before, after, profile_paths=PROFILE_PATHS, core_key='core@0.2.0')
    original = result.sha256
    data = result.data
    assert data['base_commit'] == before.commit_id
    assert data['before_source_sha256'] == before.sha256 and data['after_source_sha256'] == after.sha256
    assert data['artifact_bindings'] == data['validation']['source_bindings']
    data['checked_artifact_ids'].clear();data['validation']['stages'].clear()
    assert result.sha256 == original and result.data['checked_artifact_ids'] == [goal(1)['id']]
    assert not result.data['project_files_verified'] and not result.data['atomic_snapshot']
