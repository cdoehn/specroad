"""Bound archived-byte validation, historical inputs and concurrent changes."""
from hashlib import sha256
import json
from unittest.mock import patch

import pytest

from specroad.archive import (SnapshotObject, baseline_integrity_gate,
    verify_baseline_objects, verify_baseline_snapshot, build_baseline_manifest)
from specroad.archive import verification as implementation
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.security import ProjectBoundary
from specroad.validation import ModelDocument, validate_model
from support.model import put, configuration_value
from support.read_only import inventory, no_write_attempts
from support.records import record_value, ref
from support.scopes import descriptor
from test_baseline_manifest import baseline_inputs
from test_baseline_verification import stored_snapshot, verify, row_for, replace_object


def document(record):
    return ModelDocument(artifact_path('baseline', record['id'], 'SR'), canonical_json_bytes(record))


def validate(records, objects, **options):
    profile = baseline_inputs(scope=descriptor('project'))['effective_profile']
    return validate_model([document(r) for r in records], profile=profile,
                          gates=(baseline_integrity_gate(objects),), **options)


def stage(report, name='baseline_integrity'):
    return next(s for s in report.data['stages'] if s['stage'] == name)


def test_loaded_object_verification_matches_native_without_filesystem_reads(tmp_path):
    root = tmp_path / 'archive'; record, snapshot = stored_snapshot(root)
    native = verify(root, record)
    with no_write_attempts(), patch.object(implementation, 'read_snapshot_object', side_effect=AssertionError('no disk')):
        actual = verify_baseline_objects(canonical_json_bytes(record), snapshot.objects)
    assert actual == native


def test_common_pipeline_registers_real_baseline_checks_without_approving_lifecycle(tmp_path):
    root = tmp_path / 'archive'; record, snapshot = stored_snapshot(root)
    before = inventory(root)
    with no_write_attempts():
        report = validate([record], snapshot.objects)
    assert stage(report)['status'] == 'passed'
    assert stage(report)['checked_ids'] == [record['id']]
    assert stage(report, 'lifecycle')['status'] == 'unavailable'
    assert not report.complete and not report.passed
    assert not report.data['write_authorized'] and inventory(root) == before


def test_common_pipeline_reports_every_failed_baseline_with_bound_locations(tmp_path):
    root = tmp_path / 'archive'; first, snapshot = stored_snapshot(root)
    second = json.loads(canonical_json_bytes(first)); second['id'] = ref('BASE', '1')
    first['model_root_sha256'] = '0' * 64; second['configuration_hash'] = 'a' * 64
    report = validate([first, second], snapshot.objects); checked = stage(report)
    assert checked['status'] == 'failed'
    assert set(checked['checked_ids']) == {first['id'], second['id']}
    assert {(d['artifact_id'], d['reason']) for d in checked['diagnostics']} == {
        (first['id'], 'baseline_model_root_mismatch'), (second['id'], 'baseline_configuration_hash_mismatch')}
    assert {d['path'] for d in checked['diagnostics']} == {document(first).path, document(second).path}


def test_historical_objects_need_no_current_artifact_counterparts_in_selected_validation(tmp_path):
    root = tmp_path / 'archive'; first, snapshot = stored_snapshot(root)
    second = json.loads(canonical_json_bytes(first)); second['id'] = ref('BASE', '1')
    report = validate([first, second], snapshot.objects, selected_ids=[second['id']])
    assert report.data['checked_ids'] == [second['id']]
    assert stage(report)['checked_ids'] == [second['id']] and stage(report)['status'] == 'passed'


def test_missing_archive_bytes_fail_instead_of_becoming_a_successful_gate(tmp_path):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    report = validate([record], ())
    assert stage(report)['status'] == 'failed'
    assert stage(report)['diagnostics'][0]['reason'] == 'snapshot_referenced_object_missing'
    assert stage(report)['diagnostics'][0]['object_path'].startswith('archive/objects/')


def test_changed_object_resources_change_the_gate_binding_and_cannot_reuse_success(tmp_path):
    root = tmp_path / 'archive'; record, snapshot = stored_snapshot(root)
    before = validate([record], snapshot.objects)
    changed = [SnapshotObject(b'changed')] + list(snapshot.objects[1:])
    after = validate([record], changed)
    assert before.data['input_sha256'] != after.data['input_sha256']
    assert stage(before)['status'] == 'passed' and stage(after)['status'] == 'failed'


def test_gate_owns_supplied_bytes_but_rechecks_each_new_record(tmp_path):
    root = tmp_path / 'archive'; record, snapshot = stored_snapshot(root)
    inputs = list(snapshot.objects); gate = baseline_integrity_gate(inputs)
    inputs.clear()
    profile = baseline_inputs(scope=descriptor('project'))['effective_profile']
    first = validate_model([document(record)], profile=profile, gates=(gate,))
    record['model_root_sha256'] = '0' * 64
    second = validate_model([document(record)], profile=profile, gates=(gate,))
    assert stage(first)['status'] == 'passed' and stage(second)['status'] == 'failed'
    assert first.data['input_sha256'] != second.data['input_sha256']


def test_shared_object_inventory_is_scoped_to_the_record_and_claims_no_project_completeness(tmp_path):
    root = tmp_path / 'archive'; record, snapshot = stored_snapshot(root)
    value = verify_baseline_objects(canonical_json_bytes(record), (*snapshot.objects, SnapshotObject(b'other baseline')))
    assert value['checked_objects'] == len(snapshot.objects)
    assert not value['project_completeness_verified']


@pytest.mark.parametrize('objects', [None, {}, [b'not an object'], ['archive/objects/name']])
def test_unbound_object_declarations_are_not_treated_as_bytes(tmp_path, objects):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    with pytest.raises(ModelError):
        verify_baseline_objects(canonical_json_bytes(record), objects)


@pytest.mark.parametrize('change', ['deleted', 'corrupted'])
def test_post_reconstruction_native_recheck_catches_late_object_changes(tmp_path, change):
    root = tmp_path / 'archive'; record, snapshot = stored_snapshot(root)
    target = root / row_for(record, 'attachment')['object_path']
    read = implementation.read_snapshot_object; calls = []
    def interleave(boundary, reference):
        raw = read(boundary, reference); calls.append(reference.path)
        if len(calls) == len(snapshot.objects):
            if change == 'deleted': target.unlink()
            else:
                data = target.read_bytes(); target.write_bytes(bytes([data[0] ^ 1]) + data[1:])
        return raw
    with patch.object(implementation, 'read_snapshot_object', interleave), pytest.raises(ModelError) as error:
        verify(root, record)
    assert len(calls) >= len(snapshot.objects)
    assert error.value.reason == ('snapshot_referenced_object_missing' if change == 'deleted' else 'snapshot_object_hash_mismatch')


@pytest.mark.parametrize('role', ['artifact', 'profile', 'rule', 'mapping', 'semantic_configuration', 'effective_profile', 'model_manifest'])
def test_json_snapshot_objects_cannot_be_replaced_with_noncanonical_alias_bytes(tmp_path, role):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    row = row_for(record, role); value = json.loads((root / row['object_path']).read_bytes())
    replace_object(root, row, json.dumps(value, indent=2).encode())
    with pytest.raises(ModelError) as error:
        verify(root, record)
    assert error.value.reason == 'baseline_snapshot_json_not_canonical'


@pytest.mark.parametrize('field,value', [('id', 'wrong'), ('revision', 123), ('artifact_type', 'goal'),
                                       ('source_path', 'spec/requirements/wrong.json'), ('media_type', 'text/plain')])
def test_resource_metadata_cannot_relabel_actual_archived_artifact_bytes(tmp_path, field, value):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    row_for(record, 'artifact')[field] = value
    with pytest.raises(ModelError):
        verify(root, record)


@pytest.mark.parametrize('value', ['unknown', None, 2, {}])
def test_unknown_snapshot_roles_fail_closed(tmp_path, value):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    row_for(record, 'attachment')['role'] = value
    with pytest.raises(ModelError) as error:
        verify(root, record)
    assert error.value.reason == 'baseline_snapshot_role_unsupported'


def test_inert_output_validation_cannot_override_stored_managed_paths(tmp_path):
    values = configuration_value(); values['managed_paths'].append('baseline-verification-output')
    snapshot = build_baseline_manifest(**baseline_inputs(configuration=values, scope=descriptor('project')), baseline_id=ref('BASE'))
    record = record_value('baseline', **{k: snapshot.data[k] for k in (
        'scope_descriptor', 'manifest', 'model_root_sha256', 'configuration_hash', 'profiles', 'tool_version')})
    root = tmp_path / 'archive'; root.mkdir()
    for item in snapshot.objects: put(root, item.reference.path, item.content)
    before = inventory(root)
    with no_write_attempts(): report = verify(root, record)
    assert report['model_root_sha256'] == snapshot.model_root_sha256 and inventory(root) == before


@pytest.mark.parametrize('field,value', [('default_locale', 'de-DE'), ('generated_path', 'generated')])
def test_operational_values_cannot_be_smuggled_into_the_stored_semantic_projection(tmp_path, field, value):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    row = row_for(record, 'semantic_configuration')
    data = json.loads((root / row['object_path']).read_bytes()); data[field] = value
    replace_object(root, row, canonical_json_bytes(data)); record['configuration_hash'] = row['sha256']
    with pytest.raises(ModelError) as error:
        verify(root, record)
    assert error.value.reason == 'baseline_semantic_configuration_invalid'


def test_snapshot_can_include_an_older_baseline_and_its_actual_archived_objects(tmp_path):
    from test_baseline_creation import project, plan_for, ACTOR, TIME
    from specroad.changes.baselines import object_documents, prepare_baseline_operation
    from specroad.changes._target_materialization import materialize_target
    from base64 import b64decode

    model = project(tmp_path / 'original'); first = plan_for(model).data['operations'][0]
    target = materialize_target(model, (document(first['record']), *object_documents(first)))
    second = prepare_baseline_operation(target, baseline_id=ref('BASE', '1'), name='With history', actor=ACTOR, planned_at=TIME)
    root = tmp_path / 'archive'; root.mkdir()
    for item in second['objects']: put(root, item['path'], b64decode(item['bytes_base64']))
    before = inventory(tmp_path)
    with no_write_attempts(): value = verify(root, second['record'])
    assert value['snapshot_integrity_verified'] and value['checked_artifacts'] == 2
    assert any(row['role'] == 'archive' for row in second['record']['manifest'])
    assert inventory(tmp_path) == before
