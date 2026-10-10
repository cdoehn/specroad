"""Complete output after real native commits, with no second publication.

The registry, authority and recorded build are explicit test-host fixtures.
Native locks, receipts, checkpoints, output writes and process loss are real.
"""

from dataclasses import FrozenInstanceError
import errno
from hashlib import sha256
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from specroad import _build
from specroad.changes.receipt_values import ReceiptError, completion_marker_path
from specroad.model.canonical import canonical_json_bytes
from specroad.work import publication, receipt_files, result_files
from specroad.work.checkpoints import CheckpointStorageError
from specroad.work.receipt_files import NormativeWorkResultDelivery, publish_normative_receipt_files
from specroad.work.resume import WorkResumeError
from support.automatic_recovery import current_model
from support.publication import TRANSACTION
from support.read_only import inventory, no_write_attempts
from support.work_publication_process import child
from support.writer_boundaries import child as recovery_child
from test_work_publication import setup, ready, publish, arguments
from test_work_publication_right import restore
from test_work_resume import recorded


def forbidden(*args, **kwargs):
    raise AssertionError('Output delivery must not execute a normative writer or handler')


def no_publication(monkeypatch):
    for name in ('publish_normative_work', 'publish_prepared_journal', 'project_lock',
                 'begin_building_journal', 'stage_building_journal'):
        monkeypatch.setattr(publication, name, forbidden)
    monkeypatch.setattr('specroad.work.resume.execute_request', forbidden)


def committed(tmp_path, *, multi=True):
    model, plan, _, reg, _, location, store = setup(tmp_path, multi=multi)
    checkpoint = ready(store, reg, model, plan)
    outcome = publish(store, reg, model, plan).as_dict()
    return model, plan, reg, location, store, checkpoint, outcome


def deliver(store, reg, model, plan):
    return publish_normative_receipt_files(store, **arguments(reg, model, plan))


@pytest.mark.parametrize('multi', [False, True])
def test_complete_original_receipt_is_delivered_without_another_apply(recorded, tmp_path, monkeypatch, multi):
    model, plan, reg, location, store, checkpoint, outcome = committed(tmp_path, multi=multi)
    project = Path(model.binding.source_root); before = inventory(project)
    no_publication(monkeypatch)
    delivery = deliver(store, reg, model, plan); value = delivery.as_dict()
    ref, manifest_ref = value['result_ref'], value['delivery_manifest']
    raw = Path(ref['path']).read_bytes(); payload = json.loads(raw)
    assert raw == canonical_json_bytes(outcome['request_resolution'])
    assert ref == {'path': str(Path(ref['path'])), 'media_type': 'application/json',
        'size': len(raw), 'sha256': sha256(raw).hexdigest(),
        'result_schema': 'normative-request-resolution-v1'}
    assert payload['created_ids'] == outcome['result_object']['created_ids']
    assert payload['original_request']['actor'] == plan.data['actor']
    assert payload['original_request']['operations_sha256'] == sha256(canonical_json_bytes(plan.data['operations'])).hexdigest()
    assert payload['result_object']['published_paths'] == outcome['result_object']['published_paths']
    assert payload['result_object']['transaction_id'] == 'txn-work-native'
    assert payload['receipt_verified'] and not payload['current_target_verified']
    manifest_raw = Path(manifest_ref['path']).read_bytes(); manifest = json.loads(manifest_raw)
    assert manifest_ref['size'] == len(manifest_raw)
    assert manifest_ref['sha256'] == sha256(manifest_raw).hexdigest()
    assert manifest_ref['result_schema'] == manifest['format_version'] == 'work-receipt-files-v1'
    assert manifest['request_id'] == plan.data['request_id']
    assert manifest['work_id'] == checkpoint.as_dict()['work_id']
    assert manifest['command_id'] == 'change.apply'
    assert manifest['checkpoint_sha256'] == checkpoint.as_dict()['checkpoint_sha256']
    assert manifest['checkpoint_generation'] == 2
    assert manifest['request_resolution_sha256'] == sha256(raw).hexdigest()
    assert manifest['files'] == [{**ref, 'path': 'results/' + Path(ref['path']).name,
                                 'role': 'native_request_resolution'}]
    assert {p.name for p in (location.path / 'results').iterdir()} == {
        Path(ref['path']).name, Path(manifest_ref['path']).name}
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in (location.path / 'results').iterdir())
    assert not value['work_checkpoint_changed'] and not value['work_completion_recorded']
    assert value['normative_writes'] == 0 and not value['write_authorized']
    assert inventory(project) == before and store.read().raw == checkpoint.raw
    assert len(list((project / '.specroad/requests').glob('*.json'))) == 1
    assert len(list((project / '.specroad/transactions/receipts').glob('*/transaction.json'))) == 1
    all_before = inventory(tmp_path)
    with no_write_attempts():
        assert deliver(store, reg, model, plan).as_dict() == value == delivery.as_dict()
    assert inventory(tmp_path) == all_before
    value['result_ref']['sha256'] = '0' * 64
    assert delivery.as_dict()['result_ref']['sha256'] == sha256(raw).hexdigest()
    with pytest.raises(FrozenInstanceError):
        delivery._raw = b'{}'
    with pytest.raises(TypeError):
        bool(delivery)
    with pytest.raises(TypeError):
        NormativeWorkResultDelivery()


@pytest.mark.parametrize('cut', ['committed', 'cleanup'])
def test_lost_process_output_is_delivered_from_original_commit_before_and_after_cleanup(recorded, tmp_path, monkeypatch, cut):
    packet, stopped = child(tmp_path, cut)
    assert stopped['pid'] == packet['pid'] != os.getpid()
    reg, plan, store = restore(tmp_path, packet)
    project = tmp_path / 'project'; model = current_model(project)
    before = inventory(project); checkpoint = store.read()
    no_publication(monkeypatch)
    delivery = deliver(store, reg, model, plan); value = delivery.as_dict()
    raw = Path(value['result_ref']['path']).read_bytes(); saved = json.loads(raw)
    assert saved['result_object']['transaction_id'] == TRANSACTION
    assert saved['original_request']['operations_sha256'] == sha256(canonical_json_bytes(plan.data['operations'])).hexdigest()
    assert inventory(project) == before and store.read().raw == checkpoint.raw
    assert checkpoint.as_dict()['state'] == 'running'
    assert not value['work_completion_recorded']
    # Explicit native Recovery may remove its orphan owner/cleanup journal.
    # Delivery itself never dispatches that action or changes its historical result.
    recovered, = recovery_child(project, 'recover')
    assert recovered['outcome'] == 'target' and recovered['files'] == packet['after']
    after = inventory(tmp_path)
    with no_write_attempts():
        assert delivery.as_dict() == value
        assert deliver(store, reg, current_model(project), plan).as_dict() == value
    assert inventory(tmp_path) == after and Path(value['result_ref']['path']).read_bytes() == raw


@pytest.mark.parametrize('stage', ['payload', 'manifest'])
@pytest.mark.parametrize('late', [False, True])
def test_output_failure_retains_commit_and_actual_files_and_retry_only_finishes_delivery(recorded, tmp_path, monkeypatch, stage, late):
    model, plan, reg, location, store, checkpoint, outcome = committed(tmp_path)
    project = Path(model.binding.source_root); before = inventory(project)
    no_publication(monkeypatch)
    native_write, native_replace, write = result_files._write_new, os.replace, os.write
    attempts = []
    with monkeypatch.context() as patcher:
        if late:
            def replaced(src, dst, **kwargs):
                result = native_replace(src, dst, **kwargs)
                if dst.startswith('result-' if stage == 'payload' else 'manifest-'):
                    attempts.append(dst)
                    raise OSError(errno.EIO, 'Owned failure after actual output replacement')
                return result
            patcher.setattr(os, 'replace', replaced)
        else:
            def incomplete(parent, name, raw):
                is_payload = json.loads(raw)['format_version'] == 'normative-request-resolution-v1'
                if is_payload != (stage == 'payload'):
                    return native_write(parent, name, raw)
                def failed(fd, chunk):
                    if attempts:
                        raise OSError(errno.ENOSPC, 'Owned partial output')
                    attempts.append(name)
                    return write(fd, chunk[:7])
                with patch.object(os, 'write', failed):
                    return native_write(parent, name, raw)
            patcher.setattr(result_files, '_write_new', incomplete)
        with pytest.raises(OSError) as caught:
            deliver(store, reg, model, plan)
    assert attempts and caught.value.errno == (errno.EIO if late else errno.ENOSPC)
    retained = {p.name: p.read_bytes() for p in (location.path / 'results').iterdir()}
    assert len(retained) == (1 if stage == 'payload' else 2)
    assert not any(n.startswith('manifest-') for n in retained) or (late and stage == 'manifest')
    if not late:
        assert len(retained[attempts[0]]) == 7
    assert store.read().raw == checkpoint.raw and inventory(project) == before
    value = deliver(store, reg, model, plan).as_dict()
    assert all((location.path / 'results' / name).read_bytes() == raw for name, raw in retained.items())
    assert Path(value['result_ref']['path']).read_bytes() == canonical_json_bytes(outcome['request_resolution'])
    assert store.read().raw == checkpoint.raw and inventory(project) == before


@pytest.mark.parametrize('which', ['request', 'transaction', 'committed'])
@pytest.mark.parametrize('existing_output', [False, True])
def test_missing_native_proof_cannot_be_replaced_by_output_files(recorded, tmp_path, monkeypatch, which, existing_output):
    model, plan, reg, _, store, checkpoint, outcome = committed(tmp_path)
    delivery = deliver(store, reg, model, plan) if existing_output else None
    project = Path(model.binding.source_root)
    relative = (completion_marker_path('txn-work-native') if which == 'committed'
                else outcome['transaction']['receipts'][which]['path'])
    (project / relative).unlink()
    no_publication(monkeypatch); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises((ReceiptError, WorkResumeError)):
        deliver(store, reg, model, plan)
    if delivery is not None:
        with no_write_attempts(), pytest.raises((ReceiptError, WorkResumeError)):
            delivery.as_dict()
    assert inventory(tmp_path) == before and store.read().raw == checkpoint.raw


def test_uncommitted_preparations_do_not_trigger_apply_or_allocate_output(recorded, tmp_path, monkeypatch):
    model, plan, _, reg, _, _, store = setup(tmp_path)
    checkpoint = ready(store, reg, model, plan); before = inventory(tmp_path)
    no_publication(monkeypatch)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        deliver(store, reg, model, plan)
    assert caught.value.reason == 'normative_receipt_required'
    assert inventory(tmp_path) == before and store.read().raw == checkpoint.raw


@pytest.mark.parametrize('existing_output', [False, True])
def test_different_valid_completion_observations_cannot_confirm_delivery(recorded, tmp_path, monkeypatch, existing_output):
    model, plan, reg, _, store, checkpoint, _ = committed(tmp_path / 'original')
    other_model, _, _, _, _, _, _ = committed(tmp_path / 'other')
    other = receipt_files.read_transaction_completion(publication._source(other_model), 'txn-work-native')
    delivery = deliver(store, reg, model, plan) if existing_output else None
    before = inventory(tmp_path)
    monkeypatch.setattr(receipt_files, 'read_transaction_completion', lambda *a, **k: other)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        deliver(store, reg, model, plan)
    assert caught.value.reason == 'normative_receipt_binding_changed'
    if delivery is not None:
        with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
            delivery.as_dict()
        assert caught.value.reason == 'normative_receipt_binding_changed'
    assert inventory(tmp_path) == before and store.read().raw == checkpoint.raw


@pytest.mark.parametrize('which', ['result_ref', 'delivery_manifest'])
@pytest.mark.parametrize('change', ['missing', 'changed'])
def test_each_delivery_access_rechecks_every_output_byte(recorded, tmp_path, which, change):
    model, plan, reg, _, store, checkpoint, _ = committed(tmp_path)
    delivery = deliver(store, reg, model, plan)
    path = Path(delivery.as_dict()[which]['path'])
    if change == 'missing':
        path.unlink()
    else:
        path.write_bytes(path.read_bytes()[:-1] + b'!')
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises((WorkResumeError, CheckpointStorageError)):
        delivery.as_dict()
    assert inventory(tmp_path) == before and store.read().raw == checkpoint.raw


def test_runtime_change_refuses_existing_delivery_without_writes(recorded, tmp_path, monkeypatch):
    model, plan, reg, _, store, _, _ = committed(tmp_path)
    delivery = deliver(store, reg, model, plan); before = inventory(tmp_path)
    monkeypatch.setattr(_build, 'BUILD_METADATA', {**_build.BUILD_METADATA, 'build_sha256': '9' * 64})
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        delivery.as_dict()
    assert caught.value.exit_code == 6 and inventory(tmp_path) == before


def test_receipt_disappearing_during_output_write_prevents_publication(recorded, tmp_path, monkeypatch):
    model, plan, reg, location, store, checkpoint, _ = committed(tmp_path)
    marker = Path(model.binding.source_root) / completion_marker_path('txn-work-native')
    original = marker.read_bytes(); native = result_files._write_new
    no_publication(monkeypatch)
    with monkeypatch.context() as patcher:
        def vanished(parent, name, raw):
            result = native(parent, name, raw)
            marker.unlink()
            return result
        patcher.setattr(result_files, '_write_new', vanished)
        with pytest.raises(ReceiptError):
            deliver(store, reg, model, plan)
    retained = {p.name: p.read_bytes() for p in (location.path / 'results').iterdir()}
    assert len(retained) == 1 and all(n.startswith('.result-') for n in retained)
    assert store.read().raw == checkpoint.raw
    marker.write_bytes(original)
    before = inventory(Path(model.binding.source_root))
    deliver(store, reg, model, plan).as_dict()
    assert inventory(Path(model.binding.source_root)) == before
    assert all((location.path / 'results' / name).read_bytes() == raw for name, raw in retained.items())
