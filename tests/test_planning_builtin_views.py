"""Shared native provider parity and authority boundaries; never rendered text."""
from copy import deepcopy
from dataclasses import replace
import builtins
import io
import os

import pytest

from specroad.changes import TargetModel
from specroad.documents import resolve_builtin_view, render_builtin_view, BuiltinViewError
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.planning import project_roadmap, assess_release_readiness
from specroad.validation import ModelDocument
from specroad.verification.coverage import assess_verification_coverage
from support.read_only import no_write_attempts
from support.targets import model
from test_roadmap_projection import roadmap_values
from test_release_readiness import release_case, context, services, RELEASE
from test_release_readiness_right import refresh_reviews
from test_verification_coverage import coverage_case, prepare
from test_verification_coverage_right import release_case as coverage_release_case, release_input


@pytest.mark.parametrize('empty', [False, True])
def test_roadmap_builtin_retains_native_facts_without_inventing_a_release_decision(empty):
    supplied = model([] if empty else roadmap_values()); before = supplied.source_files
    direct = project_roadmap(supplied)
    with no_write_attempts(): result = resolve_builtin_view(supplied, 'roadmap')
    data = result.data
    assert data['roadmap'] == direct.data and data['roadmap_sha256'] == direct.sha256
    assert data['rows'] == direct.data['items'] and data['row_count'] == len(data['rows'])
    assert data['computed_reports']['roadmap']['result'] == direct.data
    assert data['computed_reports']['roadmap']['status'] == 'computed'
    assert data['readiness'] is None and data['readiness_sha256'] is None
    assert data['release_readiness_evaluated'] is False
    assert not any(data[k] for k in ('write_authorized', 'approval_granted', 'full_validation_passed',
                                    'project_files_verified', 'rendering_performed'))
    assert result.source_files == before == supplied.source_files
    with pytest.raises(TypeError): bool(result)
    data['roadmap']['items'].clear()
    assert result.data['roadmap'] == direct.data


@pytest.mark.parametrize('case', ['ready', 'missing-service', 'blocked', 'provisional'])
def test_roadmap_builtin_preserves_all_native_release_gate_values_and_selection(case):
    values, evaluation = release_case()
    if case == 'blocked': values[1]['implementation_status'] = 'blocked'
    if case == 'provisional':
        del values[0]['readiness_policy']['verification_evaluation']
        # This fixture deliberately declares fresh synthetic reviews for its
        # new Release bytes. Old reviews correctly make the native gate fail.
        values = refresh_reviews(values)
    ctx = context(values, evaluation=evaluation if case == 'provisional' else None)
    gates = services(ctx)
    if case == 'missing-service': gates = [g for g in gates if g.gate_id != 'lifecycle']
    before = ctx._model.source_files
    direct = assess_release_readiness(ctx, gates=gates)
    with no_write_attempts():
        result = resolve_builtin_view(ctx._model, 'roadmap', readiness=ctx, readiness_gates=gates)
    data = result.data
    assert data['readiness'] == direct.data and data['readiness_sha256'] == direct.sha256
    assert data['readiness']['release_id'] == RELEASE
    assert len(data['readiness']['gates']) == 8
    assert data['readiness']['ready'] is (case in ('ready', 'provisional'))
    assert data['readiness']['provisional'] is (case == 'provisional')
    assert data['release_readiness_evaluated'] and not data['approval_granted']
    assert not data['readiness']['release_baseline_authorized'] and not data['write_authorized']
    assert result.source_files == before == ctx._model.source_files
    data['readiness']['gates'].clear()
    assert result.data['readiness'] == direct.data


@pytest.mark.parametrize('change', ['record', 'bytes', 'physical-binding'])
def test_readiness_cannot_be_attached_to_a_different_view_model(change):
    values, _ = release_case(); ctx = context(values); original = ctx._model
    docs = list(original.documents); binding = original.binding
    if change == 'physical-binding': binding = replace(binding, source_root='/different/project')
    elif change == 'record':
        import json
        value = json.loads(docs[0].content); value['title'] += ' changed'
        docs[0] = ModelDocument(docs[0].path, canonical_json_bytes(value))
    else: docs[0] = ModelDocument(docs[0].path, docs[0].content + b'\n')
    other = TargetModel(original.configuration_bytes, binding, docs,
        profile=original.profile, resource_files=original.resource_files)
    with no_write_attempts(), pytest.raises(BuiltinViewError) as caught:
        resolve_builtin_view(other, 'roadmap', readiness=ctx)
    assert caught.value.reason == 'builtin_readiness_binding_mismatch' and caught.value.exit_code == 6


@pytest.mark.parametrize('fake', [True, {'ready': True}, {'gates': [], 'status': 'ready'}])
def test_readiness_labels_or_report_dictionaries_are_not_native_contexts(fake):
    with no_write_attempts(), pytest.raises(BuiltinViewError) as caught:
        resolve_builtin_view(model([]), 'roadmap', readiness=fake)
    assert caught.value.reason == 'typed_release_readiness_context_required'


@pytest.mark.parametrize('name', ['specification', 'traceability', 'verification'])
def test_readiness_options_cannot_be_silently_ignored_by_other_views(name):
    values, evaluation = coverage_case(); supplied, verification = prepare(values, evaluation)
    with pytest.raises(BuiltinViewError) as caught:
        resolve_builtin_view(supplied, name, readiness={'ready': True},
            verification=verification if name == 'verification' else None)
    assert caught.value.reason == 'builtin_readiness_input_not_applicable'


def test_services_without_a_native_readiness_context_are_refused():
    with pytest.raises(BuiltinViewError) as caught:
        resolve_builtin_view(model([]), 'roadmap', readiness_gates=[True])
    assert caught.value.reason == 'builtin_readiness_context_required'


@pytest.mark.parametrize('name', ['verification', 'traceability'])
@pytest.mark.parametrize('configured', [False, True])
def test_verification_and_traceability_keep_the_exact_release_selection(name, configured):
    _, supplied, evaluation, cfg, scope = coverage_release_case(configured=configured)
    verification = release_input(supplied, None, cfg, scope)
    direct = assess_verification_coverage(supplied, verification)
    with no_write_attempts(): result = resolve_builtin_view(supplied, name, verification=verification)
    data = result.data
    assert data['summary'] == verification.summary
    assert data['summary']['evaluation_sha256'] == evaluation.sha256
    assert data['selection_scope_descriptor'] == scope.data
    assert data['computed_reports']['verification']['result'] == direct.data
    expected = {row['requirement_id']: row['verification_result'] for row in direct.data['requirements']}
    for row in data['rows']:
        assert row['verification_result'] == expected.get(row['requirement_id'])
    assert not data['release_readiness_evaluated'] and not data['approval_granted']


@pytest.mark.parametrize('entrypoint', ['resolve', 'render'])
def test_changed_verification_model_is_refused_before_projection_or_rendering(entrypoint):
    values, evaluation = coverage_case(); supplied, verification = prepare(values, evaluation)
    values[0]['title'] += ' other'; other = model(values)
    call = resolve_builtin_view if entrypoint == 'resolve' else render_builtin_view
    with no_write_attempts(), pytest.raises(ModelError):
        call(other, 'traceability', verification=verification)


@pytest.mark.parametrize('name', ['roadmap', 'verification', 'traceability'])
@pytest.mark.parametrize('output_format', ['markdown', 'html'])
def test_render_adapter_consumes_native_inputs_without_file_access_or_writes(monkeypatch, name, output_format):
    if name == 'roadmap':
        values, _ = release_case(); ctx = context(values); supplied = ctx._model
        options = {'readiness': ctx, 'readiness_gates': services(ctx)}
    else:
        values, evaluation = coverage_case(); supplied, verification = prepare(values, evaluation)
        options = {'verification': verification}
    expected = resolve_builtin_view(supplied, name, **options); before = supplied.source_files
    from specroad.documents import builtin_views
    native = builtin_views.resolve_builtin_view; observed = []
    def capture(*args, **kwargs):
        result = native(*args, **kwargs); observed.append(result.data); return result
    monkeypatch.setattr(builtin_views, 'resolve_builtin_view', capture)
    def refuse(*args, **kwargs): raise AssertionError('Unexpected filesystem read')
    with no_write_attempts(), monkeypatch.context() as guarded:
        for module in (builtins, io, os): guarded.setattr(module, 'open', refuse)
        render_builtin_view(supplied, name, output_format=output_format, **options)
    assert observed == [expected.data]
    assert supplied.source_files == before
