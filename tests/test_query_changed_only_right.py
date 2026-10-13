"""Outside-file rule failures, failed discovery and honest partial observations."""
from copy import deepcopy

import pytest

from specroad.model.errors import ModelError
from specroad.query import ComparisonSourceSnapshot, check_changed_sources
from specroad.validation import GateDependencies, GateResult, ModelGate
from support.domain import approved_value
from support.model_validation import edge
from support.profiles import encoded, profile_data
from support.read_only import inventory, no_write_attempts
from support.srx import binary, field, literal
from support.srx_graph import incoming, reach
from test_query_changed_only import PROFILE_PATHS, goal, module, pair, rule, run, stages
from test_query_comparison_sources import source, source_files


def unchanged_rule(expression):
    value = rule(True)
    value['program']['expression'] = expression
    return profile_data(profile_id='core', lint_rules=[value])


def test_changed_target_causes_actual_srx_failure_in_unchanged_source(tmp_path):
    a, b, outside = goal(1), goal(2, title='Allowed'), goal(3)
    a['relations'] = [edge(b)]
    profile = unchanged_rule({'op': 'or', 'args': [
        {'op': 'not', 'arg': binary('eq', field('/id'), literal(a['id']))},
        reach(depth=1, where=binary('eq', field('/title'), literal('Allowed')))]})
    current = deepcopy([a, b, outside]);current[1]['title'] = 'Forbidden'
    before, after = pair(tmp_path, [a, b, outside], current, old_profile=profile)
    result = run(before, after)
    findings = stages(result)['profile_lint']['diagnostics']
    assert result['changed_artifact_ids'] == result['seed_artifact_ids'] == [b['id']]
    assert result['changed_resource_paths'] == []
    assert [(d['artifact_id'], d['code'], d['reason']) for d in findings] == [
        (a['id'], 'PROFILE_LINT', 'profile_lint_predicate_false')]
    assert result['checked_artifact_ids'] == sorted(v['id'] for v in (a, b, outside))
    assert result['checks_complete'] and result['passed'] is False
    assert not result['full_project_validation'] and not result['full_lint']


def test_removed_edge_breaks_actual_incoming_rule_on_unchanged_target(tmp_path):
    a, b = goal(1), goal(2);a['relations'] = [edge(b)]
    profile = unchanged_rule({'op': 'or', 'args': [
        {'op': 'not', 'arg': binary('eq', field('/id'), literal(b['id']))},
        binary('gt', incoming(), literal(0))]})
    current = deepcopy([a, b]);current[0]['relations'] = []
    before, after = pair(tmp_path, [a, b], current, old_profile=profile)
    result = run(before, after)
    assert result['seed_artifact_ids'] == [a['id']]
    assert result['dependency_artifact_ids'] == [b['id']]
    assert [d['artifact_id'] for d in stages(result)['profile_lint']['diagnostics']] == [b['id']]
    assert result['checks_complete'] and result['passed'] is False


@pytest.mark.parametrize('fail_on,strict,expected', [
    ('error', False, None), ('warning', False, False), ('error', True, False)])
def test_known_warning_threshold_failure_survives_unavailable_other_checks(tmp_path, fail_on, strict, expected):
    value = approved_value('goal', id=goal(1)['id'])
    current = deepcopy(value);current['statement'] = 'Changed approved goal'
    profile = profile_data(profile_id='core', lint_rules=[rule(False, severity='warning')])
    before, after = pair(tmp_path, [value], [current], old_profile=profile)
    result = run(before, after, fail_on=fail_on, strict=strict)
    native = stages(result)
    assert native['lifecycle']['status'] == 'unavailable'
    assert native['profile_lint']['status'] == 'passed'
    assert native['profile_lint']['diagnostics'][0]['severity'] == 'warning'
    assert result['validation']['model_valid'] is None
    assert result['validation_assessment']['source_report'] == result['validation']
    assert result['validation_assessment']['exit_code'] == 5
    assert result['core_lint']['core_checks_passed']
    assert result['status'] == 'incomplete' and not result['checks_complete']
    assert result['passed'] is expected
    assert not result['full_project_validation'] and not result['full_lint']


def test_unavailability_alone_is_not_a_known_model_failure_even_with_strict(tmp_path):
    value = approved_value('goal', id=goal(1)['id'])
    current = deepcopy(value);current['statement'] = 'Changed approved goal'
    before, after = pair(tmp_path, [value], [current])
    result = run(before, after, strict=True)
    assert stages(result)['lifecycle']['status'] == 'unavailable'
    assert result['validation']['model_valid'] is None
    assert result['core_lint']['core_checks_passed']
    assert result['passed'] is None and not result['checks_complete']


def test_known_error_remains_failure_alongside_unavailable_semantics(tmp_path):
    value = approved_value('goal', id=goal(1)['id'])
    current = deepcopy(value);current['statement'] = 'Changed approved goal'
    profile = profile_data(profile_id='core', lint_rules=[rule(False)])
    before, after = pair(tmp_path, [value], [current], old_profile=profile)
    result = run(before, after)
    assert stages(result)['lifecycle']['status'] == 'unavailable'
    assert stages(result)['profile_lint']['status'] == 'failed'
    assert result['passed'] is False and not result['checks_complete']
    assert not result['approval_granted'] and not result['write_authorized']


def test_unchanged_outside_reference_failure_blocks_narrow_semantic_checks(tmp_path, monkeypatch):
    a, outside, missing = goal(1), goal(2), goal(3)
    outside['relations'] = [edge(missing)]
    current = deepcopy(a);current['statement'] = 'Changed direct seed'
    before, after = pair(tmp_path, [a, outside], [current, outside])
    monkeypatch.setattr(module, 'lint_core', lambda *a, **k: pytest.fail('Blocked scope cannot run Core lint'))
    def forbidden(context):
        pytest.fail('Broken outside references must block semantic callbacks')
    result = run(before, after, gates=[ModelGate('extension:probe', 'v1', forbidden, forbidden)])
    findings = stages(result)['identities_references']['diagnostics']
    assert result['seed_artifact_ids'] == [a['id']]
    assert result['checked_artifact_ids'] == result['dependency_artifact_ids'] == []
    assert any(d['artifact_id'] == outside['id'] and d['reason'] == 'missing_relation_target' for d in findings)
    assert result['structural_scope'] == 'all_supplied_documents'
    assert result['core_lint'] is None and result['passed'] is False
    assert not result['checks_complete']


@pytest.mark.parametrize('failure,reason', [
    ('missing', 'validation_gate_dependencies_unbound_or_incomplete'),
    ('unbound', 'validation_gate_dependencies_unbound_or_incomplete'),
    ('incomplete', 'validation_gate_dependencies_unbound_or_incomplete'),
    ('unknown', 'validation_gate_dependency_missing'),
    ('exception', 'validation_gate_discovery_failed')])
def test_failed_dependency_discovery_never_becomes_a_successful_narrow_check(tmp_path, monkeypatch, failure, reason):
    a, b = goal(1), goal(2)
    current = deepcopy(b);current['statement'] = 'Changed target'
    before, after = pair(tmp_path, [a, b], [a, current])
    original = inventory(tmp_path)
    def dependencies(context):
        if failure == 'missing':
            return None
        if failure == 'exception':
            raise OSError('dependency provider unavailable')
        values = {i: [] for i in context.subjects}
        if failure == 'incomplete':
            values.pop(a['id'])
        if failure == 'unknown':
            values[a['id']] = [goal(9)['id']]
        return (GateDependencies('unbound', values) if failure == 'unbound'
                else context.dependency_result(values))
    def forbidden(context):
        pytest.fail('Failed discovery must not execute a partial gate')
    monkeypatch.setattr(module, 'lint_core', lambda *a, **k: pytest.fail('Scope is unproven'))
    with no_write_attempts():
        result = run(before, after, gates=[ModelGate('extension:probe', 'v1', dependencies, forbidden)])
    scope = stages(result)['scope']
    assert scope['status'] == 'failed' and scope['diagnostics'][0]['reason'] == reason
    assert result['validation']['checked_ids'] == result['seed_artifact_ids'] == [b['id']]
    assert result['checked_artifact_ids'] == result['dependency_artifact_ids'] == []
    assert result['core_lint'] is None and result['passed'] is False and not result['checks_complete']
    assert inventory(tmp_path) == original


@pytest.mark.parametrize('failure,reason', [
    ('exception', 'validation_gate_check_failed'),
    ('unbound', 'validation_gate_result_unbound_or_incomplete'),
    ('incomplete', 'validation_gate_result_unbound_or_incomplete'),
    ('outside', 'validation_gate_diagnostic_outside_subjects')])
def test_bad_gate_observation_keeps_actual_expanded_scope_and_native_failure(tmp_path, failure, reason):
    a, b, outside = goal(1), goal(2), goal(3)
    current = deepcopy(b);current['statement'] = 'Changed target'
    before, after = pair(tmp_path, [a, b, outside], [a, current, outside])
    def dependencies(context):
        return context.dependency_result({i: [b['id']] if i == a['id'] else [] for i in context.subjects})
    def check(context):
        if failure == 'exception':
            raise RuntimeError('gate failed')
        if failure == 'unbound':
            return GateResult('unbound', context.subjects)
        if failure == 'incomplete':
            return GateResult(context.input_sha256, context.subjects[:1])
        return context.result([{'reason': 'foreign_finding', 'artifact_id': outside['id']}])
    result = run(before, after, gates=[ModelGate('extension:probe', 'v1', dependencies, check)])
    assert result['checked_artifact_ids'] == result['core_lint']['checked_ids'] == sorted((a['id'], b['id']))
    assert result['dependency_artifact_ids'] == [a['id']]
    native = stages(result)['extension:probe']
    assert native['status'] == 'failed' and native['diagnostics'][0]['reason'] == reason
    assert result['passed'] is False
    assert result['validation_assessment']['source_report'] == result['validation']
    assert not result['full_project_validation']


def test_cyclic_declared_dependencies_expand_once_without_unrelated_artifacts(tmp_path):
    a, b, outside = goal(1), goal(2), goal(3)
    current = deepcopy(b);current['statement'] = 'Changed seed'
    before, after = pair(tmp_path, [a, b, outside], [a, current, outside])
    calls = []
    def dependencies(context):
        return context.dependency_result({a['id']: [b['id']], b['id']: [a['id']], outside['id']: []})
    def check(context):
        calls.append(context.subjects)
        return context.result()
    result = run(before, after, gates=[ModelGate('extension:cycle', 'v1', dependencies, check)])
    assert calls == [tuple(sorted((a['id'], b['id'])))]
    assert result['checked_artifact_ids'] == list(calls[0])
    assert result['passed'] is True and result['checks_complete']


@pytest.mark.parametrize('base_kind', ['missing', 'local'])
def test_base_guard_precedes_comparison_profile_validation_and_all_checks(tmp_path, monkeypatch, base_kind):
    _, after = pair(tmp_path, [goal(1)], [goal(1, statement='Changed')])
    def forbidden(*args, **kwargs):
        pytest.fail('Base guard must precede further comparison or checks')
    for name in ('compare_semantic', '_profiles', 'validate_model', 'lint_core'):
        monkeypatch.setattr(module, name, forbidden)
    with pytest.raises(ModelError) as caught:
        check_changed_sources(None if base_kind == 'missing' else after, after,
                              profile_paths={}, core_key=None)
    assert caught.value.reason == ('changed_comparison_sources_required' if base_kind == 'missing'
                                   else 'changed_git_base_required')


def test_unresolved_real_git_ref_cannot_fall_back_to_current_files(tmp_path, monkeypatch):
    root, options = source(tmp_path / 'git', 'git', source_files(goal(1),
        extra={'profiles/core.json': encoded(profile_data(profile_id='core'))}))
    _, after = pair(tmp_path / 'pair', [goal(1)], [goal(1, statement='Changed')])
    monkeypatch.setattr(module, 'validate_model', lambda *a, **k: pytest.fail('No resolved base'))
    original = inventory(tmp_path)
    with pytest.raises(ModelError) as caught:
        before = ComparisonSourceSnapshot(root, kind='git', reference='missing-specroad-ref')
        run(before, after)
    assert caught.value.reason == 'git_object_read_failed'
    assert inventory(tmp_path) == original


@pytest.mark.parametrize('mode,reason', [
    ('duplicate', 'changed_duplicate_profile_path'), ('unused', 'changed_profile_paths_mismatch')])
def test_ambiguous_or_unused_profile_binding_fails_before_checks(tmp_path, monkeypatch, mode, reason):
    extra = {'profiles/extra.json': encoded(profile_data(profile_id='extra'))}
    before, after = pair(tmp_path, [goal(1)], [goal(1, statement='Changed')], old_extra=extra, new_extra=extra)
    paths = {**PROFILE_PATHS, 'extra@0.2.0': 'profiles/core.json' if mode == 'duplicate' else 'profiles/extra.json'}
    monkeypatch.setattr(module, 'validate_model', lambda *a, **k: pytest.fail('Invalid profile binding'))
    with pytest.raises(ModelError) as caught:
        check_changed_sources(before, after, profile_paths=paths, core_key='core@0.2.0')
    assert caught.value.reason == reason


@pytest.mark.parametrize('removed', [False, True])
def test_unexecuted_empty_scope_reports_no_structural_or_semantic_check(tmp_path, removed):
    before, after = pair(tmp_path, [goal(1)], [] if removed else [goal(1)])
    result = run(before, after)
    assert result['status'] == ('no_current_artifacts' if removed else 'no_changes')
    assert result['structural_scope'] == result['validation_scope'] == 'not_run'
    assert result['validation'] is result['validation_assessment'] is result['core_lint'] is None
    assert result['checked_artifact_ids'] == result['dependency_artifact_ids'] == []
    assert not result['checks_complete'] and result['passed'] is None


def test_owned_snapshot_checks_do_not_claim_freshness_after_current_files_change(tmp_path):
    before, after = pair(tmp_path, [goal(1)], [goal(1, statement='Changed')])
    captured = after.inputs.records[0]
    (tmp_path / 'after' / captured.path).write_bytes(b'changed after capture')
    original = inventory(tmp_path)
    with no_write_attempts():
        result = run(before, after)
    assert result['after_source_sha256'] == after.sha256
    assert result['checks_complete'] and result['passed'] is True
    assert not result['project_files_verified'] and not result['atomic_snapshot']
    assert inventory(tmp_path) == original
