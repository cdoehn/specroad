"""Full machine payloads and real guarded external result publication."""

from dataclasses import FrozenInstanceError
import errno
from hashlib import sha256
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from specroad import _build
from specroad.cli.commands import builtin_registry
from specroad.cli.requests import CommandRequest
from specroad.cli.result_schemas import ENVELOPE_ID, validate_result_document
from specroad.cli.results import ResultReference
from specroad.model.canonical import canonical_json_bytes
from specroad.security import SafetyViolation
from specroad.work import result_files
from specroad.work.checkpoints import CheckpointStore, CheckpointStorageError
from specroad.work.finalization import finalize_read_only_work
from specroad.work.result_files import WorkResultDelivery, publish_read_only_result_files
from specroad.work.resume import WorkResumeError, resume_read_only_work
from specroad.work.root import WorkDirectory
from support.read_only import inventory, no_write_attempts
from test_work_resume import REQUESTS, recorded, setup


def completed(tmp_path, request=None):
    initial, roots, location, store = setup(tmp_path, request)
    resume_read_only_work(store)
    final = finalize_read_only_work(store)
    return roots, location, store, final


def forbidden(*args, **kwargs):
    raise AssertionError('Result delivery executed a handler')


@pytest.mark.parametrize('command_request', REQUESTS, ids=lambda value: value.command_id)
def test_full_original_payload_is_published_with_its_bound_manifest(recorded, tmp_path, monkeypatch, command_request):
    roots, location, store, final = completed(tmp_path, command_request)
    original = final.as_dict()['command_outcome']; protected = inventory(roots[0].root)
    work_pointer = (location.path / 'work.json').read_bytes()
    monkeypatch.setattr('specroad.work.resume.execute_request', forbidden)
    delivery = publish_read_only_result_files(store); value = delivery.as_dict()
    external = value['command_outcome']; ref = external['result_ref']
    validate_result_document(ENVELOPE_ID, external)
    assert external['result'] is None and external['summary']['delivery'] == 'external'
    assert {k: external[k] for k in ('command','status','project','diagnostics')} == {
        k: original[k] for k in ('command','status','project','diagnostics')}
    assert external['summary'] == {**original['summary'], 'delivery': 'external'}
    schema = builtin_registry().bind_request(command_request).command.protocol.result_schema
    raw = Path(ref['path']).read_bytes()
    assert raw == canonical_json_bytes(original['result'])
    assert ref['size'] == len(raw) and ref['sha256'] == sha256(raw).hexdigest()
    assert ref['result_schema'] == schema and ref['media_type'] == 'application/json'
    validate_result_document(schema, json.loads(raw))
    ResultReference(**ref).verify()
    manifest_ref = value['delivery_manifest']; manifest_raw = Path(manifest_ref['path']).read_bytes()
    assert manifest_ref['size'] == len(manifest_raw)
    assert manifest_ref['sha256'] == sha256(manifest_raw).hexdigest()
    manifest = json.loads(manifest_raw)
    assert manifest['work_id'] == value['work_id'] == final.manifest.as_dict()['work_id']
    assert manifest['checkpoint_sha256'] == final.manifest.as_dict()['checkpoint_sha256']
    assert manifest['checkpoint_generation'] == value['checkpoint_generation'] == 2
    assert manifest['outcome_sha256'] == sha256(canonical_json_bytes(original)).hexdigest()
    assert manifest['files'] == [{**ref, 'path': str(Path(ref['path']).relative_to(location.path)), 'role': 'result'}]
    assert manifest['command_id'] == command_request.command_id
    assert manifest['exit_code'] == value['command_exit_code'] == final.command_exit_code
    assert {p.name for p in (location.path / 'results').iterdir()} == {
        Path(ref['path']).name, Path(manifest_ref['path']).name}
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in (location.path / 'results').iterdir())
    assert not value['handler_executed'] and not value['project_writes_performed']
    assert not value['work_checkpoint_changed'] and store.read().raw == final.manifest.raw
    assert (location.path / 'work.json').read_bytes() == work_pointer
    assert inventory(roots[0].root) == protected
    before = inventory(location.path)
    with no_write_attempts():
        assert publish_read_only_result_files(store).as_dict() == value
        assert delivery.as_dict() == value
    assert inventory(location.path) == before
    external['result_ref']['sha256'] = '0' * 64
    assert delivery.as_dict()['command_outcome']['result_ref']['sha256'] == sha256(raw).hexdigest()
    with pytest.raises(FrozenInstanceError):
        delivery._raw = b'{}'
    with pytest.raises(TypeError):
        bool(delivery)
    with pytest.raises(TypeError):
        WorkResultDelivery()


def test_fresh_controller_reuses_only_fully_verified_persisted_output(recorded, tmp_path):
    roots, location, store, final = completed(tmp_path)
    expected = publish_read_only_result_files(store).as_dict()
    fresh = CheckpointStore(WorkDirectory(store._initial, protected_roots=roots,
        directory=location.path), store._initial)
    before = inventory(tmp_path)
    with no_write_attempts():
        actual = publish_read_only_result_files(fresh).as_dict()
    assert actual == expected and inventory(tmp_path) == before
    assert fresh.read().raw == final.manifest.raw


def test_runtime_change_cannot_relabel_an_existing_delivery(recorded, tmp_path, monkeypatch):
    _, _, store, _ = completed(tmp_path)
    delivery = publish_read_only_result_files(store)
    monkeypatch.setattr(_build, 'BUILD_METADATA', {**_build.BUILD_METADATA, 'build_sha256': '9' * 64})
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        delivery.as_dict()
    assert caught.value.exit_code == 6 and inventory(tmp_path) == before


@pytest.mark.parametrize('generation', [0, 1])
def test_unfinished_work_cannot_be_advertised_as_a_delivered_result(recorded, tmp_path, generation):
    _, _, _, store = setup(tmp_path)
    if generation:
        resume_read_only_work(store)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        publish_read_only_result_files(store)
    assert caught.value.reason == 'completed_work_required'
    assert inventory(tmp_path) == before


def test_missing_work_is_not_allocated_by_result_delivery(recorded, tmp_path):
    _, _, _, store = setup(tmp_path, publish=False); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(FileNotFoundError):
        publish_read_only_result_files(store)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('which', ['payload', 'manifest'])
@pytest.mark.parametrize('change', ['missing', 'different_bytes'])
def test_every_access_rechecks_all_result_and_manifest_bytes(recorded, tmp_path, which, change):
    _, _, store, final = completed(tmp_path)
    delivery = publish_read_only_result_files(store); value = delivery.as_dict()
    path = Path(value['command_outcome']['result_ref']['path'] if which == 'payload'
                else value['delivery_manifest']['path'])
    if change == 'missing':
        path.unlink()
    else:
        raw = path.read_bytes(); path.write_bytes(raw[:-1] + b'!')
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises((WorkResumeError, CheckpointStorageError)):
        delivery.as_dict()
    assert inventory(tmp_path) == before and store.read().raw == final.manifest.raw


@pytest.mark.parametrize('kind', ['symlink', 'hardlink', 'fifo', 'public'])
def test_unsafe_result_storage_is_refused_without_project_writes(recorded, tmp_path, kind):
    roots, location, store, _ = completed(tmp_path)
    path = location.path / 'results/foreign'
    if kind == 'symlink':
        path.symlink_to(roots[0].root, target_is_directory=True)
    elif kind == 'fifo':
        os.mkfifo(path, 0o600)
    else:
        path.write_bytes(b'Owned fixture data'); path.chmod(0o600)
        if kind == 'hardlink':
            os.link(path, path.with_name('alias'))
        else:
            path.chmod(0o644)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(SafetyViolation):
        publish_read_only_result_files(store)
    assert inventory(tmp_path) == before


def test_bounded_short_writes_keep_the_entire_original_payload(recorded, tmp_path, monkeypatch):
    _, _, store, final = completed(tmp_path, CommandRequest('schema.list'))
    native = result_files._write_new; write = os.write; counts = []

    def short_write(parent, name, raw):
        def piece(fd, chunk):
            count = write(fd, chunk[:31]); counts.append(count)
            return count
        with patch.object(os, 'write', piece):
            return native(parent, name, raw)

    monkeypatch.setattr(result_files, '_write_new', short_write)
    delivered = publish_read_only_result_files(store).as_dict()
    ref = delivered['command_outcome']['result_ref']
    assert counts and max(counts) <= 31 and len(counts) > 2
    assert Path(ref['path']).read_bytes() == canonical_json_bytes(final.as_dict()['command_outcome']['result'])
    assert ref['size'] > 31 and store.read().raw == final.manifest.raw


@pytest.mark.parametrize('late', [False, True])
def test_output_failure_preserves_actual_files_and_checkpoint_for_explicit_retry(recorded, tmp_path, monkeypatch, late):
    roots, location, store, final = completed(tmp_path)
    protected = inventory(roots[0].root)
    native_write = result_files._write_new; native_replace = os.replace; write = os.write
    with monkeypatch.context() as patcher:
        if late:
            def replaced(src, dst, **kwargs):
                result = native_replace(src, dst, **kwargs)
                if dst.startswith('result-'):
                    raise OSError(errno.EIO, 'Owned failure after actual output replacement')
                return result
            patcher.setattr(os, 'replace', replaced)
        else:
            def incomplete(parent, name, raw):
                calls = []
                def failed(fd, chunk):
                    if calls:
                        raise OSError(errno.ENOSPC, 'Owned incomplete output file')
                    calls.append(True)
                    return write(fd, chunk[:7])
                with patch.object(os, 'write', failed):
                    return native_write(parent, name, raw)
            patcher.setattr(result_files, '_write_new', incomplete)
        with pytest.raises(OSError) as caught:
            publish_read_only_result_files(store)
    assert caught.value.errno == (errno.EIO if late else errno.ENOSPC)
    retained = {p.name: p.read_bytes() for p in (location.path / 'results').iterdir()}
    assert len(retained) == 1 and not any(n.startswith('manifest-') for n in retained)
    expected = canonical_json_bytes(final.as_dict()['command_outcome']['result'])
    assert next(iter(retained.values())) == (expected if late else expected[:7])
    assert store.read().raw == final.manifest.raw and inventory(roots[0].root) == protected
    monkeypatch.setattr('specroad.work.resume.execute_request', forbidden)
    delivery = publish_read_only_result_files(store).as_dict()
    assert all((location.path / 'results' / name).read_bytes() == raw for name, raw in retained.items())
    assert delivery['command_outcome']['summary']['complete'] is True
    assert store.read().raw == final.manifest.raw and inventory(roots[0].root) == protected
