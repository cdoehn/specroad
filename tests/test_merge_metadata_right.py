"""17.i.R: native historical proof, exact boundaries and independent recomputation."""
from base64 import b64decode
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from specroad.merge import (prepare_merge_metadata, verify_merge_metadata, build_merge_conflicts,
                           resolve_merge_conflict, load_merge_sources, SourceSnapshot)
from specroad.changes.merge_metadata import combined_merge_audit
from specroad.model.audit import artifact_audit
from specroad.model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from specroad.model.errors import ModelError
from specroad.security import SafetyViolation
from specroad.model.paths import artifact_path
from specroad.bundles._payload_model import owned_payload_model
from specroad.archive.objects import SnapshotObject
from specroad.archive.verification import verify_baseline_objects
from support.merge_lifecycle import artifact, bound_records, changed
from support.merge_relations import history_for, bound_relations, edge
from support.merge_resolution import PLAN_ID, ACTOR, WHEN
from support.read_only import inventory
from support.languages import small_restore_registry
from test_merge_inventory import bind_files
from test_merge_metadata import prepare, combined, row
from test_merge_sources import read_only_sources, sources as native_sources, KINDS
from test_project_bundle import project


@pytest.fixture(scope='module')
def original(tmp_path_factory):
    return project(tmp_path_factory.mktemp('metadata-right-seed') / 'project',
                   language_registry=small_restore_registry()).raw


@pytest.fixture
def source_plan(tmp_path, original):
    sources, history, path, value = combined(tmp_path, original)
    plan = build_merge_conflicts(sources, plan_id=PLAN_ID, history=history)
    return sources, history, plan, path, value


@pytest.fixture
def bound(source_plan):
    sources, history, plan, path, value = source_plan
    result = prepare(sources, history, plan)
    return sources, history, plan, result, path, value


@pytest.mark.parametrize('field,value', [
    ('metadata_policy_version', 'change-metadata-v1'), ('metadata_format_version', 'unknown'),
    ('ready', True), ('write_authorized', True), ('approval_granted', True),
    ('metadata_complete', False), ('expected_target_model_root_sha256', 'f' * 64),
    ('input_plan_sha256', 'e' * 64), ('pending_gates', []), ('unexpected', None)])
def test_writer_rejects_forged_fields_even_with_valid_json(bound, field, value):
    sources, history, plan, result, _, _ = bound
    candidate = result.data; candidate[field] = value
    with pytest.raises(ModelError, match='merge_metadata_binding_mismatch'):
        verify_merge_metadata(jcs(candidate), plan.canonical_bytes, sources,
            history=history, expected_plan_sha256=plan.sha256)


@pytest.mark.parametrize('target', ['resources', 'target_files'])
def test_rehashing_a_forged_byte_projection_cannot_create_writer_evidence(bound, target):
    sources, history, plan, result, _, _ = bound
    candidate = result.data
    candidate[target][0]['byte_sha256' if target == 'resources' else 'sha256'] = '0' * 64
    candidate[target + '_sha256'] = digest(candidate[target])
    with pytest.raises(ModelError, match='merge_metadata_binding_mismatch'):
        verify_merge_metadata(jcs(candidate), plan.canonical_bytes, sources,
            history=history, expected_plan_sha256=plan.sha256)


@pytest.mark.parametrize('expected', [None, True, [], 'bad', '0' * 64])
def test_selected_original_input_hash_is_mandatory(source_plan, expected):
    sources, history, plan, _, _ = source_plan
    with pytest.raises(ModelError, match='merge_metadata_input_hash_mismatch'):
        prepare_merge_metadata(plan.canonical_bytes, sources, history=history, expected_plan_sha256=expected)


def test_original_plan_byte_spelling_is_bound_separately_from_canonical_candidate(bound):
    sources, history, plan, _, _, _ = bound
    raw = json.dumps(plan.data, indent=2).encode()
    assert sha256(raw).hexdigest() != plan.sha256
    with pytest.raises(ModelError, match='merge_metadata_input_hash_mismatch'):
        prepare_merge_metadata(raw, sources, history=history, expected_plan_sha256=plan.sha256)
    result = prepare_merge_metadata(raw, sources, history=history, expected_plan_sha256=sha256(raw).hexdigest())
    assert result.data['input_plan_sha256'] == sha256(raw).hexdigest()
    reread = verify_merge_metadata(result.canonical_bytes, raw, sources,
        history=history, expected_plan_sha256=sha256(raw).hexdigest())
    assert reread.canonical_bytes == result.canonical_bytes


@pytest.mark.parametrize('kind', KINDS)
def test_native_local_git_baseline_and_bundle_sources_have_same_root_and_no_writes(tmp_path, kind):
    requests, files, record, git = native_sources(tmp_path)
    sources = load_merge_sources(requests[kind], requests[kind], requests[kind])
    history = history_for(sources)
    plan = build_merge_conflicts(sources, plan_id=PLAN_ID, history=history)
    before = inventory(tmp_path)
    with read_only_sources():
        result = prepare(sources, history, plan)
        reread = verify_merge_metadata(result.canonical_bytes, plan.canonical_bytes, sources,
            history=history, expected_plan_sha256=plan.sha256)
    assert result.files == files and reread.files == files
    assert result.data['expected_target_model_root_sha256'] == sources.ours.binding['model_root_sha256']
    assert inventory(tmp_path) == before


def archived_history(root, *, revision=9, other_origin=False, kind='goal'):
    """Prepare an actual native baseline, with its own recomputable root/objects."""
    from test_baseline_creation import project as baseline_project
    from specroad.changes.baselines import prepare_baseline_operation
    from support.records import ref
    model = baseline_project(root / 'history', bundled=True)
    files = dict(model.source_files)
    if kind == 'goal':
        path, value = artifact(files)
    else:
        from support.records import record_value
        from support.domain import domain_value
        requirement = domain_value('requirement')
        files[artifact_path('requirement', requirement['id'], 'SR')] = jcs(requirement)
        value = record_value(kind)
        path = artifact_path(kind, value['id'], 'SR')
    historical = changed(value, revision=revision)
    if other_origin:
        historical['created_by'] = {'actor_type': 'human', 'actor_id': 'separate-origin'}
    files[path] = jcs(historical)
    native = owned_payload_model(files, source_label='synthetic-historical-original')
    operation = prepare_baseline_operation(native, baseline_id=ref('BASE'),
        name='Synthetic bound history', actor=ACTOR, planned_at=WHEN)
    files[artifact_path('baseline', operation['record']['id'], 'SR')] = jcs(operation['record'])
    for item in operation['objects']:
        files[item['path']] = b64decode(item['bytes_base64'])
    # Qualification is real and independent of the merge implementation.
    verify_baseline_objects(jcs(operation['record']),
        [SnapshotObject(b64decode(item['bytes_base64'])) for item in operation['objects']])
    return files, path, value


@pytest.mark.parametrize('theirs,accepted', [(7, False), (9, True), (10, True)])
@pytest.mark.parametrize('kind', ['goal', 'evidence'])
def test_higher_revision_in_native_ours_baseline_is_not_silently_downgraded(tmp_path, theirs, accepted, kind):
    files, path, value = archived_history(tmp_path, kind=kind)
    root = tmp_path / 'sources'; root.mkdir()
    versions = [changed(value, revision=3), changed(value, revision=3), changed(value, revision=theirs)]
    if kind == 'evidence':
        versions[:2] = [None, None]
    sources, history = bound_records(root, files, path, versions)
    result = prepare(sources, history)
    accepted = accepted and (kind != 'evidence' or theirs == 9)
    assert result.data['metadata_complete'] is accepted
    if accepted:
        assert result.files[path] == sources.theirs.files[path]
        assert json.loads(result.files[path])['revision'] == theirs
    else:
        reason = 'merge_immutable_history_conflict' if kind == 'evidence' else 'merge_lower_known_revision'
        assert any(row['reason'] == reason for row in result.data['conflicts'])
        with pytest.raises(ModelError): result.files


def test_archived_same_identifier_with_other_creation_origin_blocks_adoption(tmp_path):
    files, path, value = archived_history(tmp_path, other_origin=True)
    root = tmp_path / 'sources'; root.mkdir()
    sources, history = bound_records(root, files, path,
        [changed(value, revision=3), changed(value, revision=3), changed(value, revision=12)])
    result = prepare(sources, history)
    assert any(row['reason'] == 'merge_creation_origin_conflict' for row in result.data['conflicts'])
    assert not result.data['metadata_complete']


@pytest.mark.parametrize('times,expected', [
    (['2026-01-01T00:00:00.1Z', '2026-01-01T00:00:00.100000001Z', '2026-01-01T00:00:00Z'], '2026-01-01T00:00:00.100001001Z'),
    (['2026-12-31T23:59:59.999999Z'] * 3, '2027-01-01T00:00:00Z'),
    (['2024-02-28T23:59:59.999999Z'] * 3, '2024-02-29T00:00:00Z'),
    (['2024-02-29T23:59:59.999999Z'] * 3, '2024-03-01T00:00:00Z'),
    (['2026-01-01t00:00:00.000000001Z'] * 3, '2026-01-01T00:00:00.000001001Z'),
    (['2026-12-31T23:59:60.999999Z'] * 3, '2027-01-01T00:00:00Z')])
def test_time_maximum_uses_exact_digits_and_calendar_without_host_clock(original, times, expected):
    _, value = artifact(original)
    versions = [changed(value, updated_at=t, revision=r) for t, r in zip(times, (1, 3, 7))]
    assert combined_merge_audit(*versions)['updated_at'] == expected


@pytest.mark.parametrize('field,value', [('revision', True), ('revision', 0), ('revision', -1),
    ('revision', 1.5), ('updated_at', '2026-02-30T00:00:00Z'), ('updated_at', None),
    ('updated_by', {'actor_type': 'human'}), ('created_at', 'not-a-time')])
def test_central_policy_rejects_invalid_audit_values(original, field, value):
    _, item = artifact(original)
    with pytest.raises(ModelError):
        combined_merge_audit(item, changed(item, **{field: value}), item)


@pytest.mark.parametrize('change,reason', [
    ({'revision': 9007199254740992}, 'number_roundtrip_loss'),
    ({'updated_at': '9999-12-31T23:59:59.999999Z'}, 'timestamp_overflow')])
def test_revision_or_timestamp_successor_overflow_is_explicit(original, change, reason):
    _, item = artifact(original)
    with pytest.raises(ModelError, match=reason):
        combined_merge_audit(item, changed(item, **change), item)


def test_missing_base_is_not_revision_one_creation(original):
    _, item = artifact(original)
    result = combined_merge_audit(None, changed(item, revision=3), changed(item, revision=7))
    assert result['revision'] == 8 and result['created_at'] == item['created_at']


def test_full_boundary_turns_timestamp_overflow_into_conflict_without_partial_bytes(tmp_path, original):
    path, value = artifact(original)
    sources, history = bound_records(tmp_path, original, path, [value,
        changed(value, title='ours', updated_at='9999-12-31T23:59:59.999999Z'),
        changed(value, extensions={'vendor.metadata': {'x': 1}})])
    result = prepare(sources, history)
    assert any(row['reason'] == 'timestamp_overflow' for row in result.data['conflicts'])
    assert result.data['target_files'] == [] and result.data['expected_target_model_root_sha256'] is None


def test_invalid_explicit_business_value_is_not_a_valid_target_root(tmp_path, original):
    path, value = artifact(original)
    sources, history = bound_records(tmp_path, original, path, [changed(value, title=s) for s in ('b', 'o', 't')])
    plan = build_merge_conflicts(sources, plan_id=PLAN_ID, history=history)
    resolved = resolve_merge_conflict(plan.canonical_bytes, sources, history=history,
        expected_plan_sha256=plan.sha256, conflict_id=plan.conflicts[0]['conflict_id'],
        actor=ACTOR, resolved_at=WHEN, value=None)
    result = prepare(sources, history, resolved)
    assert not result.data['metadata_complete']
    assert result.data['conflicts'][0]['reason'] == 'merge_metadata_target_projection'
    assert result.data['expected_target_model_root_sha256'] is None


def test_multiple_resolution_actors_follow_bound_event_order_not_sorted_conflict_ids(tmp_path, original):
    path, value = artifact(original)
    sources, history = bound_records(tmp_path, original, path, [changed(value, title=s,
        extensions={'vendor.metadata': {'x': i}}) for i, s in enumerate(('base', 'ours', 'theirs'))])
    plan = build_merge_conflicts(sources, plan_id=PLAN_ID, history=history)
    first = plan
    actors = [{'actor_type': 'human', 'actor_id': 'first'}, {'actor_type': 'human', 'actor_id': 'last'}]
    for conflict, actor in zip(reversed(plan.conflicts), actors):
        first = resolve_merge_conflict(first.canonical_bytes, sources, history=history,
            expected_plan_sha256=first.sha256, conflict_id=conflict['conflict_id'],
            actor=actor, resolved_at=WHEN, take='ours')
    assert len(first.data['resolutions']) == 2
    result = prepare(sources, history, first)
    assert json.loads(result.files[path])['updated_by'] == actors[-1]
    assert result.data['input_plan']['resolutions'] == first.data['resolutions']


@pytest.mark.parametrize('role', ['base', 'ours', 'theirs'])
def test_actual_source_mutation_invalidates_both_preparations(bound, role):
    sources, history, plan, result, path, _ = bound
    source = getattr(sources, role)
    target = Path(source.source_root) / path
    target.write_bytes(target.read_bytes() + b'\n')
    with pytest.raises((ModelError, SafetyViolation)):
        prepare(sources, history, plan)
    with pytest.raises((ModelError, SafetyViolation)):
        verify_merge_metadata(result.canonical_bytes, plan.canonical_bytes, sources,
            history=history, expected_plan_sha256=plan.sha256)


def test_actual_change_during_target_projection_is_caught_before_return(bound, monkeypatch):
    sources, history, plan, _, path, _ = bound
    from specroad.merge import metadata
    original_constructor = metadata.owned_payload_model
    def changing(files, **kwargs):
        result = original_constructor(files, **kwargs)
        target = Path(sources.ours.source_root) / path
        target.write_bytes(target.read_bytes() + b'\n')
        return result
    monkeypatch.setattr(metadata, 'owned_payload_model', changing)
    with pytest.raises((ModelError, SafetyViolation)): prepare(sources, history, plan)


def test_unknown_origin_is_not_replaced_by_equal_bytes_or_created_fields(tmp_path, original):
    sources = bind_files(tmp_path, [original] * 3); history = history_for(sources)
    entry = next(r for r in history['observations'] if r['role'] == 'ours' and r['identity']['kind'] == 'artifact')
    entry['origin'] = None
    result = prepare(sources, history)
    assert not result.data['metadata_complete']
    assert result.data['expected_target_model_root_sha256'] is None


def test_regular_change_policy_cannot_be_replaced_with_merge_policy():
    from specroad.changes._metadata_policy import select_policy
    with pytest.raises(ModelError, match='unsupported_regular_metadata_policy'):
        select_policy('merge-metadata-v1')


def test_actor_event_timestamp_does_not_change_k3_source_time_maximum(original):
    _, value = artifact(original)
    versions = [changed(value, updated_at='2030-01-01T00:00:00Z', revision=r) for r in (1, 3, 7)]
    result = combined_merge_audit(*versions, resolution_actor=ACTOR)
    assert result['updated_at'] == '2030-01-01T00:00:00.000001Z' and result['updated_by'] == ACTOR


def test_selected_candidate_cannot_hide_a_changed_history_input(bound):
    sources, history, plan, result, _, _ = bound
    different = deepcopy(history)
    different['observations'][0]['origin'] = None
    with pytest.raises(ModelError):
        verify_merge_metadata(result.canonical_bytes, plan.canonical_bytes, sources,
            history=different, expected_plan_sha256=plan.sha256)
