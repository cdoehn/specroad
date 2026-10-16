"""Stored selection precedence and real publication boundaries without M13."""
from copy import deepcopy

import pytest

from specroad.archive import (ReleaseBaselineReadiness, ReleaseBaselineSelectionConflict,
    assess_release_baseline_readiness)
from specroad.changes import ChangePlan, PublicationAuthority, prepare_change_plan
from specroad.changes._target_materialization import materialize_target
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.validation import ModelDocument, ModelGate
from support.read_only import inventory, no_write_attempts
from test_baseline_creation import apply, plan_for
from test_release_baseline_boundary import release_project, prepare


POINTER = '/readiness_policy/verification_evaluation'


@pytest.mark.parametrize('evaluation', [False, True, 0, 1, '', 'passed', [], ['ready']])
def test_stored_selection_requires_an_object_before_any_release_preparation(tmp_path, evaluation):
    model, release = release_project(tmp_path / 'project',
        policy={'verification_evaluation': evaluation})
    before = inventory(tmp_path)
    for call in (assess_release_baseline_readiness,
                 lambda model, **kw: prepare(model, baseline_kind='release', **kw)):
        with no_write_attempts(), pytest.raises(ModelError) as error:
            call(model, release_id=release['id'])
        assert error.value.reason == 'release_evaluation_object_required'
        assert error.value.pointer == POINTER
        assert error.value.path == artifact_path('release', release['id'], 'SR')
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('evaluation', [False, 0, '', [], ['passed']])
def test_explicit_selection_requires_an_object_and_cannot_be_ignored(tmp_path, evaluation):
    model, release = release_project(tmp_path / 'project', policy={'verification_evaluation': {}})
    with no_write_attempts(), pytest.raises(ModelError) as error:
        prepare(model, baseline_kind='release', release_id=release['id'], evaluation=evaluation)
    assert error.value.reason == 'release_evaluation_object_required'
    assert error.value.pointer == '/evaluation' and error.value.path is None


@pytest.mark.parametrize('policy', [{}, {'verification_evaluation': None}])
def test_external_selection_cannot_substitute_for_missing_stored_selection(tmp_path, policy):
    model, release = release_project(tmp_path / 'project', policy=policy)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        prepare(model, baseline_kind='release', release_id=release['id'], evaluation={'ready': True})
    assert error.value.reason == 'stored_release_evaluation_required'
    assert error.value.pointer == POINTER and inventory(tmp_path) == before


@pytest.mark.parametrize('evaluation', [{}, {'required_runs': ['another']},
    {'required_runs': ['stored'], 'ready': True}])
def test_different_external_selection_is_a_conflict_without_alternative_approval(tmp_path, evaluation):
    model, release = release_project(tmp_path / 'project',
        policy={'verification_evaluation': {'required_runs': ['stored']}})
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ReleaseBaselineSelectionConflict) as error:
        prepare(model, baseline_kind='release', release_id=release['id'], evaluation=evaluation)
    assert error.value.exit_code == 6 and error.value.reason == 'release_baseline_evaluation_conflict'
    assert error.value.pointer == POINTER
    assert error.value.path == artifact_path('release', release['id'], 'SR')
    assert inventory(tmp_path) == before


def test_equal_canonical_selection_has_the_same_observation_but_never_grants_readiness(tmp_path):
    stored = {'subject': {'revision': 1, 'state': 'owned'}, 'required_runs': ['a', 'b']}
    external = {'required_runs': ['a', 'b'], 'subject': {'state': 'owned', 'revision': 1}}
    model, release = release_project(tmp_path / 'project', policy={'verification_evaluation': stored})
    with no_write_attempts():
        original = assess_release_baseline_readiness(model, release_id=release['id'])
        repeated = assess_release_baseline_readiness(model, release_id=release['id'], evaluation=external)
    assert original.data == repeated.data and original.sha256 == repeated.sha256
    assert original.data['stored_evaluation'] == stored
    assert original.data['stored_evaluation_sha256'] == canonical_json_sha256(stored)
    external['required_runs'].clear()
    detached = repeated.data; detached['stored_evaluation']['required_runs'].clear()
    assert repeated.data == original.data and repeated.sha256 == original.sha256
    with no_write_attempts(), pytest.raises(ModelError) as error:
        prepare(model, baseline_kind='release', release_id=release['id'], evaluation=deepcopy(stored))
    assert error.value.reason == 'release_baseline_readiness_required'


def test_changed_stored_bytes_produce_a_new_binding_without_upgrading_an_old_observation(tmp_path):
    model, release = release_project(tmp_path / 'project',
        policy={'verification_evaluation': {'required_runs': ['old']}})
    first = assess_release_baseline_readiness(model, release_id=release['id']); data = first.data
    release['revision'] += 1
    release['readiness_policy']['verification_evaluation']['required_runs'] = ['new']
    document = ModelDocument(artifact_path('release', release['id'], 'SR'), canonical_json_bytes(release))
    target = materialize_target(model, (document,))
    with no_write_attempts(): second = assess_release_baseline_readiness(target, release_id=release['id'])
    assert first.data == data and first.sha256 != second.sha256
    assert second.data['release_revision'] == data['release_revision'] + 1
    assert second.data['stored_evaluation'] == {'required_runs': ['new']}
    for report in (first, second):
        with no_write_attempts(), pytest.raises(ModelError) as error: report.require_ready()
        assert error.value.reason == 'release_baseline_readiness_required'


@pytest.mark.parametrize('strict', [False, True])
def test_host_success_gate_is_never_invoked_as_a_replacement_for_real_readiness(tmp_path, strict):
    model, release = release_project(tmp_path / 'project',
        policy={'verification_evaluation': {}, 'ready': True, 'passed': True})
    calls = []
    def dependencies(context):
        calls.append('dependencies')
        return context.dependency_result({name: list(context.all_ids) for name in context.subjects})
    def validate(context):
        calls.append('validate'); return context.result()
    fake = ModelGate('configuration', 'success-stub', dependencies, validate)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        prepare(model, baseline_kind='release', release_id=release['id'], strict=strict, gates=(fake,))
    assert error.value.reason == 'release_baseline_readiness_required'
    assert calls == [] and inventory(tmp_path) == before


def test_forged_success_report_is_never_a_publication_permit(tmp_path):
    model, release = release_project(tmp_path / 'project')
    value = assess_release_baseline_readiness(model, release_id=release['id']).data
    value.update(ready=True, release_authorized=True, write_authorized=True,
        readiness_evaluated=True, readiness_provider_available=True, blockers=[])
    forged = object.__new__(ReleaseBaselineReadiness)
    object.__setattr__(forged, '_encoded', canonical_json_bytes(value))
    with no_write_attempts(), pytest.raises(ModelError) as error: forged.require_ready()
    assert error.value.reason == 'release_baseline_readiness_required'
    with no_write_attempts(), pytest.raises(ModelError) as error:
        prepare(model, baseline_kind='release', release_id=release['id'], evaluation=forged.data)
    assert error.value.reason == 'stored_release_evaluation_required'


def test_working_creation_cannot_silently_discard_an_external_release_selection(tmp_path):
    model, _ = release_project(tmp_path / 'project')
    with no_write_attempts(), pytest.raises(ModelError) as error: prepare(model, evaluation={})
    assert error.value.reason == 'working_baseline_release_selection_not_applicable'


@pytest.mark.parametrize('route', ['prepare', 'load', 'execute'])
def test_saved_release_relabeling_fails_before_host_authority_or_native_publication(tmp_path, route):
    model, _ = release_project(tmp_path / 'project'); data = plan_for(model).data
    data['operations'][0]['record']['baseline_kind'] = 'release'
    data.pop('change_plan_sha256')
    if route != 'prepare': data['change_plan_sha256'] = canonical_json_sha256(data)
    calls = []; before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        if route == 'prepare': prepare_change_plan(data)
        elif route == 'load': ChangePlan(canonical_json_bytes(data))
        else:
            forged = object.__new__(ChangePlan)
            object.__setattr__(forged, 'source_bytes', canonical_json_bytes(data))
            object.__setattr__(forged, '_encoded', canonical_json_bytes(data))
            apply(forged, model, authority=PublicationAuthority('host', '1',
                lambda request: calls.append(request) or True))
    assert error.value.reason == 'release_baseline_readiness_required'
    assert error.value.pointer == '/operations/0/record/baseline_kind'
    assert calls == [] and inventory(tmp_path) == before
