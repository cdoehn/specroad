"""15.k.R: immutable identity conflicts and exact historical dependency bytes."""
from base64 import b64encode
from hashlib import sha256
import json

import pytest

from specroad.bundles import prepare_project_bundle
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.paths import artifact_path
from specroad.recovery import RestoreError, RestorePlan, verify_restore_plan
from specroad.storage.record_artifact import RecordArtifact
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.records import ref
from support.restore import plan_for
from test_restore_history import evidence_case
from test_restore_plan import decode_files, resign
from test_restore_plan_right import save_snapshot


ATTACHMENT = 'attachments/measurement.bin'


def alternate_record(history, *, different=True):
    value = json.loads(next(raw for path, raw in history.items() if path.startswith('spec/')))
    value['id'] = ref('EVD', '2')
    value['run_context']['run_id'] = 'test-ci:measurement-2'
    if different:
        content = b'a different immutable measurement'
        value['attachments'][0].update(size=len(content), sha256=sha256(content).hexdigest())
    raw = canonical_json_bytes(value)
    RecordArtifact(raw)  # A valid stored record, not an invented approval gate.
    return artifact_path('evidence', value['id'], 'SR'), raw


def rejected(options, reason, path, *, raw=None):
    before = inventory(options['project_root'].parent)
    with no_write_attempts(), pytest.raises(RestoreError) as failure:
        plan_for(options) if raw is None else RestorePlan(raw)
    assert failure.value.reason == reason
    assert failure.value.path == path
    assert inventory(options['project_root'].parent) == before
    return failure.value.exit_code


@pytest.mark.parametrize('kind', ['baseline', 'project_bundle'])
@pytest.mark.parametrize('available', ['first', 'second', 'missing'])
def test_incompatible_protected_attachment_bindings_are_conflicts_even_without_bytes(tmp_path, kind, available):
    options, _, _, history = evidence_case(tmp_path, kind)
    path, raw = alternate_record(history)
    put(options['project_root'], path, raw)
    if available == 'missing':
        (options['project_root'] / ATTACHMENT).unlink()
    elif available == 'second':
        put(options['project_root'], ATTACHMENT, b'a different immutable measurement')
    assert rejected(options, 'restore_protected_dependency_conflict', ATTACHMENT) == 6


@pytest.mark.parametrize('kind', ['baseline', 'project_bundle'])
@pytest.mark.parametrize('damage', ['missing', 'changed'])
def test_archived_identity_conflict_is_not_hidden_by_damaged_dependency(tmp_path, kind, damage):
    options, _, _, history = evidence_case(tmp_path, kind, canonical=True)
    save_snapshot(options['project_root'], identity=ref('BASE', '2'))
    path = next(p for p in history if p.startswith('spec/'))
    value = json.loads(history[path]); value['title'] = 'Conflicting immutable content'
    put(options['project_root'], path, canonical_json_bytes(value))
    if damage == 'missing':
        (options['project_root'] / ATTACHMENT).unlink()
    else:
        put(options['project_root'], ATTACHMENT, b'damaged before image')
    assert rejected(options, 'restore_protected_history_conflict', path) == 6


@pytest.mark.parametrize('kind', ['baseline', 'project_bundle'])
@pytest.mark.parametrize('reverse_ids', [False, True])
def test_archived_attachment_is_selected_by_exact_binding_not_snapshot_order(tmp_path, kind, reverse_ids):
    options, files, source, history = evidence_case(tmp_path, kind, canonical=True)
    root = options['project_root']
    evidence_path = next(p for p in history if p.startswith('spec/'))
    (root / evidence_path).unlink()
    # A different historical mutable subject used the same attachment path.
    # Its original bytes stay in its archive, not in the restored subject.
    subject_path = next(p for p in files if p.startswith('spec/requirements/'))
    subject = json.loads(files[subject_path])
    old_attachment = b'older unrelated snapshot attachment'
    subject['attachments'] = [{'path': ATTACHMENT, 'size': len(old_attachment),
        'sha256': sha256(old_attachment).hexdigest(), 'media_type': 'application/octet-stream'}]
    put(root, subject_path, canonical_json_bytes(subject))
    put(root, ATTACHMENT, old_attachment)
    first, second = ('2', '1') if reverse_ids else ('1', '2')
    originals = save_snapshot(root, identity=ref('BASE', first))
    put(root, subject_path, files[subject_path])
    for path, raw in history.items():
        put(root, path, raw)
    originals.update(save_snapshot(root, identity=ref('BASE', second)))
    (root / evidence_path).unlink()
    (root / ATTACHMENT).unlink()
    before = inventory(tmp_path)
    with no_write_attempts():
        plan = plan_for(options)
        assert RestorePlan(plan.source_bytes).source_bytes == plan.source_bytes
        assert verify_restore_plan(plan.source_bytes).source_bytes == plan.source_bytes
    assert inventory(tmp_path) == before
    target = decode_files(plan)
    assert all(target[p] == raw for p, raw in {**originals, **history}.items())
    assert target[subject_path] == files[subject_path]
    assert (options['source_root'] / options['source_path']).read_bytes() == source
    assert {r['evidence_result'] for r in plan.history_assessments} == {'failed'}
    independent = tmp_path / 'independent'
    for path, raw in target.items():
        put(independent, path, raw)
    assert prepare_project_bundle(independent).manifest['bundle_model_root_sha256'] == plan.data['expected_target_root']


@pytest.mark.parametrize('kind', ['baseline', 'project_bundle'])
@pytest.mark.parametrize('archived', [False, True])
def test_identical_dependencies_of_distinct_records_are_preserved_once(tmp_path, kind, archived):
    options, _, _, history = evidence_case(tmp_path, kind, canonical=True)
    path, raw = alternate_record(history, different=False)
    history[path] = raw
    for path, raw in history.items():
        put(options['project_root'], path, raw)
    if archived:
        originals = save_snapshot(options['project_root'], identity=ref('BASE', '2'))
        for path in history:
            (options['project_root'] / path).unlink()
        history.update(originals)
    before = inventory(tmp_path)
    with no_write_attempts():
        plan = plan_for(options)
        assert RestorePlan(plan.source_bytes).source_bytes == plan.source_bytes
    assert inventory(tmp_path) == before
    target = decode_files(plan)
    assert all(target[p] == content for p, content in history.items())
    rows = [r for r in plan.data['preserved'] if r['path'] == ATTACHMENT]
    assert len(rows) == 1 and rows[0]['reasons'] == ['protected_dependency']
    assert len({r['evidence_id'] for r in plan.history_assessments}) == 2


@pytest.mark.parametrize('kind', ['baseline', 'project_bundle'])
@pytest.mark.parametrize('damage', ['missing', 'changed'])
def test_missing_and_changed_original_attachments_have_exact_nonconflict_diagnostics(tmp_path, kind, damage):
    options, _, _, _ = evidence_case(tmp_path, kind)
    if damage == 'missing':
        (options['project_root'] / ATTACHMENT).unlink()
        reason = 'restore_protected_dependency_missing'
    else:
        put(options['project_root'], ATTACHMENT, b'corrupt')
        reason = 'restore_protected_attachment_bytes_mismatch'
    assert rejected(options, reason, ATTACHMENT) == 3


@pytest.mark.parametrize('kind', ['baseline', 'project_bundle'])
@pytest.mark.parametrize('damage', ['missing', 'changed'])
def test_missing_nested_archive_bytes_are_not_replaced_by_current_mutable_files(tmp_path, kind, damage):
    options, _, _, history = evidence_case(tmp_path, kind, canonical=True)
    first = save_snapshot(options['project_root'], identity=ref('BASE', '1'))
    save_snapshot(options['project_root'], identity=ref('BASE', '2'))
    path = next(p for p, raw in first.items() if p.startswith('archive/') and raw == history[ATTACHMENT])
    if damage == 'missing':
        (options['project_root'] / path).unlink()
        reason = 'restore_protected_dependency_missing'
    else:
        put(options['project_root'], path, b'corrupt archive object')
        reason = 'restore_baseline_object_bytes_mismatch'
    assert rejected(options, reason, path) == 3


def test_source_evidence_obligations_participate_in_history_conflict_check(tmp_path):
    options, _, _, history = evidence_case(tmp_path, canonical=True)
    for path, raw in history.items():
        put(options['source_root'], path, raw)
    put(options['source_root'], options['source_path'], prepare_project_bundle(options['source_root']).source_bytes)
    (options['project_root'] / next(p for p in history if p.startswith('spec/'))).unlink()
    path, raw = alternate_record(history)
    put(options['project_root'], path, raw)
    put(options['project_root'], ATTACHMENT, b'a different immutable measurement')
    assert rejected(options, 'restore_protected_dependency_conflict', ATTACHMENT) == 6


def test_rehashed_plan_cannot_hide_conflicting_record_as_backup_only(tmp_path):
    options, _, _, history = evidence_case(tmp_path)
    data = plan_for(options).data
    path, raw = alternate_record(history)
    row = {'path': path, 'size': len(raw), 'sha256': sha256(raw).hexdigest()}
    data['inventory']['entries'].append({**row, 'kind': 'file'})
    data['inventory']['entries'].sort(key=lambda r: r['path'].encode('utf-8'))
    data['inventory']['sha256'] = canonical_json_sha256({k: data['inventory'][k] for k in ('roots', 'entries')})
    data['backup']['entries'].append(row)
    data['backup']['entries'].sort(key=lambda r: r['path'].encode('utf-8'))
    data['backup']['sha256'] = canonical_json_sha256(data['backup']['entries'])
    data['objects'].append({'sha256': row['sha256'], 'size': len(raw), 'data_base64': b64encode(raw).decode('ascii')})
    data['objects'].sort(key=lambda r: r['sha256'])
    assert rejected(options, 'restore_protected_dependency_conflict', ATTACHMENT, raw=resign(data)) == 6
