"""17.i.W: exact metadata over real native projects, without publication."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.merge import (build_merge_conflicts, prepare_merge_metadata,
                           verify_merge_metadata, resolve_merge_conflict)
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.errors import ModelError
from specroad.changes.merge_metadata import combined_merge_audit
from specroad.bundles._payload_model import owned_payload_model
from support.merge_lifecycle import artifact, bound_records, changed
from support.merge_relations import bound_relations, edge, history_for
from support.merge_resolution import PLAN_ID, ACTOR, WHEN
from support.read_only import inventory
from support.languages import small_restore_registry
from test_merge_inventory import bind_files
from test_merge_sources import read_only_sources
from test_project_bundle import project


@pytest.fixture(scope='module')
def original(tmp_path_factory):
    return project(tmp_path_factory.mktemp('metadata-seed') / 'project',
                   language_registry=small_restore_registry()).raw


def prepare(sources, history, plan=None):
    plan = build_merge_conflicts(sources, plan_id=PLAN_ID, history=history) if plan is None else plan
    return prepare_merge_metadata(plan.canonical_bytes, sources, history=history, expected_plan_sha256=plan.sha256)


def row(result, identifier):
    return next(r for r in result.data['resources'] if r['identity']['id'] == identifier)


def combined(tmp_path, original):
    path, value = artifact(original)
    sources, history = bound_records(tmp_path, original, path, [
        changed(value, revision=1, updated_at='2030-01-01T00:00:00.123456789Z'),
        changed(value, title='ours', revision=3, updated_at='2029-01-01T00:00:00Z'),
        changed(value, extensions={'vendor.metadata': {'theirs': True}}, revision=7, updated_at='2028-01-01T00:00:00Z')])
    return sources, history, path, value


def test_combined_three_and_seven_becomes_eight_with_exact_time_and_native_root(tmp_path, original):
    sources, history, path, value = combined(tmp_path, original)
    before = inventory(tmp_path)
    plan = build_merge_conflicts(sources, plan_id=PLAN_ID, history=history)
    assert plan.conflicts == []
    with read_only_sources():
        result = prepare(sources, history, plan)
        checked = verify_merge_metadata(result.canonical_bytes, plan.canonical_bytes, sources,
            history=history, expected_plan_sha256=plan.sha256)
    actual = json.loads(result.files[path])
    assert actual['title'] == 'ours' and actual['extensions'] == {'vendor.metadata': {'theirs': True}}
    assert actual['revision'] == 8 and actual['updated_at'] == '2030-01-01T00:00:00.123457789Z'
    assert actual['updated_by'] == {'actor_type': 'tool', 'actor_id': 'specroad-merge'}
    assert actual['created_at'] == value['created_at'] and actual['created_by'] == value['created_by']
    assert row(result, value['id'])['classification'] == 'combined'
    model = owned_payload_model(result.files, source_label='independent-test-oracle')
    root = model.manifest(model.artifacts, sources.ours.binding['scope_descriptor']).sha256
    assert result.data['expected_target_model_root_sha256'] == root
    assert checked.canonical_bytes == result.canonical_bytes and checked.files == result.files
    assert set(result.files) == set(original) and inventory(tmp_path) == before
    assert result.data['pending_gates'] == ['target_validation', 'publication']
    assert not result.ready and not result.write_authorized and not result.approval_granted


@pytest.mark.parametrize('mode', ['equal', 'ours_changed', 'theirs_changed', 'ours_addition', 'theirs_addition'])
def test_unchanged_and_adopted_keep_original_bytes_and_history(tmp_path, original, mode):
    path, value = artifact(original)
    variant = changed(value, revision=7, title='existing history')
    raw = (json.dumps(variant, ensure_ascii=False, indent=3) + '\n').encode()
    versions = {'equal': [raw, raw, raw], 'ours_changed': [value, raw, value],
                'theirs_changed': [value, value, raw], 'ours_addition': [None, raw, None],
                'theirs_addition': [None, None, raw]}[mode]
    sources, history = bound_records(tmp_path, original, path, versions)
    result = prepare(sources, history)
    assert result.files[path] == raw and json.loads(result.files[path])['revision'] == 7
    classification = 'adopt_existing' if mode in ('theirs_changed', 'theirs_addition') else 'unchanged_ours'
    assert row(result, value['id']) == {'identity': {'kind': 'artifact', 'id': value['id'], 'version': None},
        'path': path, 'classification': classification, 'byte_sha256': sha256(raw).hexdigest(), 'size': len(raw)}


def test_no_changes_preserves_whole_normative_inventory_including_binary_originals(tmp_path, original):
    sources = bind_files(tmp_path, [original] * 3)
    result = prepare(sources, history_for(sources))
    assert result.files == original
    assert result.data['expected_target_model_root_sha256'] == sources.ours.binding['model_root_sha256']
    assert all(r['classification'] == 'unchanged_ours' for r in result.data['resources'])


def test_unresolved_conflict_withholds_all_files_and_model_root(tmp_path, original):
    path, value = artifact(original)
    sources, history = bound_records(tmp_path, original, path, [changed(value, title=n) for n in ('base', 'ours', 'theirs')])
    result = prepare(sources, history)
    assert not result.data['metadata_complete'] and result.data['expected_target_model_root_sha256'] is None
    assert result.data['target_files'] == [] and result.data['conflicts'][0]['reason'] == 'unresolved_conflict'
    with pytest.raises(ModelError, match='merge_metadata_incomplete'):
        result.files


@pytest.mark.parametrize('take', ['base', 'ours', 'theirs', None])
def test_resolved_branch_forces_combined_revision_and_bound_human_actor(tmp_path, original, take):
    path, value = artifact(original)
    sources, history = bound_records(tmp_path, original, path, [changed(value, title=n, revision=r)
        for n, r in (('base', 1), ('ours', 3), ('theirs', 7))])
    plan = build_merge_conflicts(sources, plan_id=PLAN_ID, history=history)
    args = {'value': 'chosen'} if take is None else {'take': take}
    resolved = resolve_merge_conflict(plan.canonical_bytes, sources, history=history,
        expected_plan_sha256=plan.sha256, conflict_id=plan.conflicts[0]['conflict_id'], actor=ACTOR, resolved_at=WHEN, **args)
    result = prepare(sources, history, resolved)
    target = json.loads(result.files[path])
    assert target['title'] == ('chosen' if take is None else take)
    assert target['updated_by'] == ACTOR and target['revision'] == 8
    assert result.data['input_plan'] == resolved.data and row(result, value['id'])['classification'] == 'combined'


def test_last_bound_resolution_actor_in_owner_or_relation_order_controls_audit(tmp_path, original):
    relation = edge(created_at='2026-01-01T00:00:00Z',
        created_by={'actor_type': 'tool', 'actor_id': 'relation-author'})
    sources, history, owner = bound_relations(tmp_path, original,
        [[dict(relation, rationale=role)] for role in ('base', 'ours', 'theirs')])
    plan = build_merge_conflicts(sources, plan_id=PLAN_ID, history=history)
    conflict = next(r for r in plan.conflicts if r['pointer'].endswith('/rationale'))
    selected = resolve_merge_conflict(plan.canonical_bytes, sources, history=history, expected_plan_sha256=plan.sha256,
        conflict_id=conflict['conflict_id'], actor=ACTOR, resolved_at=WHEN, take='theirs')
    result = prepare(sources, history, selected)
    path = row(result, owner)['path']; value = json.loads(result.files[path])
    assert value['relations'] == [dict(relation, rationale='theirs')]
    assert value['revision'] == 2 and value['updated_by'] == ACTOR


def test_disjoint_relations_are_joined_in_the_owner_without_restamping_relation_audit(tmp_path, original):
    a, b = edge(number=1), edge(number=2)
    sources, history, owner = bound_relations(tmp_path, original, [[], [b], [a]])
    result = prepare(sources, history)
    value = json.loads(result.files[row(result, owner)['path']])
    assert value['relations'] == [a, b]
    assert value['revision'] == 2 and row(result, owner)['classification'] == 'combined'


def test_immutable_evidence_conflict_cannot_be_reclassified_as_combined(tmp_path, original):
    path, value = artifact(original, 'evidence')
    sources, history = bound_records(tmp_path, original, path, [value, value, changed(value, revision=7)])
    result = prepare(sources, history)
    assert not result.data['metadata_complete']
    with pytest.raises(ModelError): result.files


def test_passive_result_owns_values_and_does_not_imply_authority(tmp_path, original):
    sources = bind_files(tmp_path, [original] * 3)
    result = prepare(sources, history_for(sources)); raw = result.canonical_bytes
    exposed = result.data; exposed['ready'] = True
    files = result.files; files.clear()
    assert result.canonical_bytes == raw and result.files == original
    with pytest.raises(TypeError): bool(result)
    with pytest.raises(FrozenInstanceError): result._encoded = b'{}'


@pytest.mark.parametrize('field', ['created_at', 'created_by'])
def test_different_creation_metadata_blocks_even_simple_adoption(tmp_path, original, field):
    path, value = artifact(original)
    different = '2020-01-01T00:00:00Z' if field == 'created_at' else {'actor_type': 'human', 'actor_id': 'other-origin'}
    sources, history = bound_records(tmp_path, original, path, [value, value, changed(value, **{field: different})])
    result = prepare(sources, history)
    assert any(r['reason'] == 'merge_creation_origin_conflict' for r in result.data['conflicts'])
    assert row(result, value['id'])['classification'] == 'conflict'


def test_lower_current_or_base_revision_is_not_adopted(tmp_path, original):
    path, value = artifact(original)
    sources, history = bound_records(tmp_path, original, path, [changed(value, revision=9), changed(value, revision=9), changed(value, revision=7)])
    result = prepare(sources, history)
    assert any(r['reason'] == 'merge_lower_known_revision' for r in result.data['conflicts'])
