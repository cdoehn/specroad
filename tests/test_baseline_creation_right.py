"""Late byte failures preserve real journals without claiming a partial Baseline."""
from hashlib import sha256
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from specroad.changes import (ChangePlan, TargetModel, PublicationAuthority,
    read_transaction_completion, prepare_change_plan)
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.storage.project import ProjectSource
from support.read_only import inventory
from support.records import ref
from test_baseline_creation import project, preview, plan_for, apply


def no_completion(root):
    with pytest.raises(ModelError): read_transaction_completion(ProjectSource(root), 'txn-baseline')


def baseline_path(root):
    return root / artifact_path('baseline', ref('BASE'), 'SR')


def pending(root):
    return json.loads((root / '.specroad/write-state/pending.json').read_bytes())


@pytest.mark.parametrize('damage', ['truncated', 'missing', 'same_length_changed'])
def test_actual_staged_object_bytes_are_rechecked_before_any_publication(tmp_path, damage):
    from specroad.changes import guarded_write
    root = tmp_path / 'project'; model = project(root); plan = plan_for(model); observed = []
    def damaged(event):
        if event != 'staged:0': return
        path = root / '.specroad/write-state/staging/0.bin'
        raw = path.read_bytes(); observed.append(path)
        if damage == 'missing': path.unlink()
        elif damage == 'truncated': path.write_bytes(raw[:-1])
        else: path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
    with patch.object(guarded_write, '_checkpoint', damaged), pytest.raises(ModelError):
        apply(plan, model)
    assert len(observed) == 1 and pending(root)['state'] == 'writing'
    assert not baseline_path(root).exists() and not (root / 'archive').exists()
    no_completion(root)


def test_source_change_after_journal_creation_cannot_enter_the_snapshot(tmp_path):
    from specroad.changes import guarded_write
    root = tmp_path / 'project'; model = project(root); plan = plan_for(model)
    source = root / model.documents[0].path
    def changed(event):
        if event == 'marker_synced': source.write_bytes(source.read_bytes() + b' ')
    with patch.object(guarded_write, '_checkpoint', changed), pytest.raises(ModelError):
        apply(plan, model)
    assert source.read_bytes() == model.documents[0].content + b' '
    assert pending(root)['state'] == 'writing' and not baseline_path(root).exists()
    no_completion(root)


@pytest.mark.parametrize('fault', ['link', 'directory_sync', 'unlink'])
def test_failed_object_move_preserves_actual_names_without_advancing_the_record(tmp_path, fault):
    from specroad.changes import guarded_write
    from specroad.changes import _guarded_effects as effects
    root = tmp_path / 'project'; model = project(root); plan = plan_for(model)
    original = effects.replace_bound_image; touched = []
    def move(*args, **kwargs):
        if len(str(args[3])) == 64:
            touched.append(args[3])
            if fault == 'link': raise OSError('before atomic no-replace publication')
        return original(*args, **kwargs)
    def stop(event):
        if event == ('effect_replaced:0' if fault == 'directory_sync' else 'effect_synced:0'):
            raise OSError('lost synchronization or publication acknowledgement')
    with patch.object(effects, 'replace_bound_image', move), patch.object(guarded_write, '_checkpoint', stop):
        with pytest.raises(ModelError) as error: apply(plan, model)
    assert touched and error.value.write_state == 'unknown' and not baseline_path(root).exists()
    assert pending(root)['state'] == 'writing'
    first = sorted(plan.data['operations'][0]['record']['manifest'], key=lambda r: r['object_path'])[0]
    staged = root / '.specroad/write-state/staging/0.bin'; target = root / first['object_path']
    if fault == 'link':
        assert staged.is_file() and not target.exists()
        assert sha256(staged.read_bytes()).hexdigest() == first['sha256']
    else:
        assert not staged.exists() and target.stat().st_nlink == 1
        assert sha256(target.read_bytes()).hexdigest() == first['sha256']
    no_completion(root)


@pytest.mark.parametrize('damage', ['missing', 'changed'])
def test_lost_published_object_blocks_the_sealed_record(tmp_path, damage):
    import specroad.changes._guarded_effects as committing
    root = tmp_path / 'project'; model = project(root); plan = plan_for(model)
    original = committing.replace_bound_image; altered = []
    def changed(source, source_name, target, target_name, **kwargs):
        result = original(source, source_name, target, target_name, **kwargs)
        if kwargs.get('create_only') and not altered:
            path = Path(os.readlink('/proc/self/fd/' + str(target))) / target_name
            if damage == 'missing': path.unlink()
            else: path.write_bytes(b'changed after publication')
            altered.append(path)
        return result
    with patch.object(committing, 'replace_bound_image', side_effect=changed):
        with pytest.raises(ModelError): apply(plan, model)
    assert altered and not baseline_path(root).exists() and pending(root)['state'] == 'writing'
    no_completion(root)


def test_error_after_record_publication_is_not_a_completed_baseline(tmp_path):
    import specroad.changes._guarded_effects as committing
    root = tmp_path / 'project'; model = project(root); plan = plan_for(model)
    original = committing.replace_bound_image
    def failed(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[3].startswith('SR-BASE-'): raise OSError('lost publication acknowledgement')
        return result
    with patch.object(committing, 'replace_bound_image', side_effect=failed):
        with pytest.raises(ModelError) as error: apply(plan, model)
    assert error.value.write_state == 'unknown' and baseline_path(root).exists()
    assert json.loads(baseline_path(root).read_bytes())['baseline_state'] == 'sealed'
    assert pending(root)['state'] == 'writing'
    no_completion(root)


@pytest.mark.parametrize('boundary', ['receipt', 'cleanup'])
def test_late_finalization_error_never_returns_a_false_success_or_retries(tmp_path, boundary):
    from specroad.changes import guarded_write
    root = tmp_path / 'project'; model = project(root); plan = plan_for(model); failed = []
    def stop(event):
        if event == ('receipt:transaction.json'
                     if boundary == 'receipt' else 'receipts_synced'):
            failed.append(event); raise OSError('injected finalization failure')
    with patch.object(guarded_write, '_checkpoint', stop), pytest.raises(ModelError):
        apply(plan, model)
    assert len(failed) == 1 and baseline_path(root).exists()
    for row in plan.data['operations'][0]['record']['manifest']:
        assert sha256((root / row['object_path']).read_bytes()).hexdigest() == row['sha256']
    assert pending(root)['state'] == 'writing'
    no_completion(root)


@pytest.mark.parametrize('field', ['model_root_sha256', 'configuration_hash', 'manifest_role', 'source_path', 'created_by'])
def test_self_consistent_saved_declarations_cannot_override_actual_snapshot_inputs(tmp_path, field):
    root = tmp_path / 'project'; model = project(root); original = plan_for(model); data = original.data
    record = data['operations'][0]['record']
    if field == 'manifest_role': record['manifest'][0]['role'] = 'invented'
    elif field == 'source_path': record['manifest'][0]['source_path'] = '../outside'
    elif field == 'created_by':
        record['created_by']['actor_id'] = record['updated_by']['actor_id'] = 'different creator'
    else: record[field] = 'f' * 64
    data['result_artifacts'] = [{'artifact': record, 'sha256': canonical_json_sha256(record)}]
    data.pop('change_plan_sha256'); plan = prepare_change_plan(data); before = inventory(root)
    with pytest.raises(ModelError) as error: apply(plan, model)
    assert error.value.reason == 'baseline_snapshot_binding_mismatch' and inventory(root) == before


@pytest.mark.parametrize('history', ['reserved_artifact_ids', 'previously_approved_ids'])
def test_historical_baseline_identity_is_not_reused(tmp_path, history):
    root = tmp_path / 'project'; model = project(root); plan = plan_for(model)
    model = TargetModel(model.configuration_bytes, model.binding, model.documents,
        profile=model.profile, resource_files=model.resource_files, **{history: [ref('BASE')]})
    before = inventory(root)
    with pytest.raises(ModelError): apply(plan, model)
    assert inventory(root) == before


@pytest.mark.parametrize('boundary', ['symlink', 'hardlinked_source', 'readonly_archive'])
def test_native_path_and_permission_guards_remain_mandatory(tmp_path, boundary):
    root = tmp_path / 'project'; model = project(root); plan = plan_for(model)
    if boundary == 'symlink':
        foreign = tmp_path / 'foreign'; foreign.mkdir(); (root / 'archive').symlink_to(foreign, target_is_directory=True)
    elif boundary == 'hardlinked_source':
        os.link(root / model.documents[0].path, tmp_path / 'linked.json')
    else:
        (root / 'archive').mkdir(); (root / 'archive').chmod(0o555)
    before = inventory(tmp_path)
    try:
        with pytest.raises(ModelError): apply(plan, model)
        assert inventory(tmp_path) == before
    finally:
        if boundary == 'readonly_archive': (root / 'archive').chmod(0o755)


def test_changed_request_payload_cannot_replay_or_create_a_second_baseline(tmp_path):
    root = tmp_path / 'project'; model = project(root); plan = plan_for(model); apply(plan, model)
    value = preview(model, name='Different snapshot')
    other = ChangePlan(canonical_json_bytes(value['plan'])); before = inventory(root)
    with pytest.raises(ModelError): apply(other, model, transaction_id='second-transaction')
    assert inventory(root) == before


def test_final_source_recheck_precedes_immutable_object_publication(tmp_path):
    from specroad.changes._publication_io import replace_bound_image
    source = tmp_path / 'stage'; target = tmp_path / 'objects'; source.mkdir(); target.mkdir()
    path = source / 'image'; original = b'original'; path.write_bytes(original); info = path.stat()
    a = os.open(source, os.O_RDONLY | os.O_DIRECTORY); b = os.open(target, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(ModelError):
            replace_bound_image(a, 'image', b, 'object', size=len(original), digest=sha256(original).hexdigest(),
                identity=(info.st_dev, info.st_ino), create_only=True,
                source_changed=lambda: AssertionError('unexpected identity change'),
                before_replace=lambda: path.write_bytes(b'modified'))
    finally:
        os.close(a); os.close(b)
    assert path.read_bytes() == b'modified' and not (target / 'object').exists()


def test_new_object_link_is_durable_before_its_staged_name_can_be_removed(tmp_path):
    from specroad.changes._publication_io import replace_bound_image
    source = tmp_path / 'stage'; target = tmp_path / 'objects'; source.mkdir(); target.mkdir()
    path = source / 'image'; raw = b'complete object'; path.write_bytes(raw); info = path.stat()
    a = os.open(source, os.O_RDONLY | os.O_DIRECTORY); b = os.open(target, os.O_RDONLY | os.O_DIRECTORY)
    original = os.fsync; observations = []
    def sync(fd):
        if fd == b:
            observations.append((path.exists(), (target / 'object').read_bytes()))
            raise OSError('injected first directory sync failure')
        return original(fd)
    try:
        with patch.object(os, 'fsync', side_effect=sync), pytest.raises(OSError):
            replace_bound_image(a, 'image', b, 'object', size=len(raw), digest=sha256(raw).hexdigest(),
                identity=(info.st_dev, info.st_ino), create_only=True,
                source_changed=lambda: AssertionError('unexpected identity change'))
    finally:
        os.close(a); os.close(b)
    assert observations == [(True, raw)]
    assert path.read_bytes() == (target / 'object').read_bytes() == raw
