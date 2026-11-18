"""Local transport evidence backed by the existing native completion proof."""
from hashlib import sha256
import os
import stat

from ..changes._lock_files import LockFiles
from ..changes._staging_files import _write_new
from ..model.canonical import canonical_json_bytes
from ..storage.json_syntax import parse_json_object
from ._files import PassiveFile, directory, require
from ._handoff import MAX_BYTES
from ._return_draft import replay
from ._export_boundary import binding
from ._native_api import _api_call


def staged(receiver, *, receipt=False):
    root = receiver.stage
    directory(root, owned=True)
    expected = {name: raw for name, raw in receiver.data.contents.items() if name != receiver.data.entrypoint}
    actual = {}
    for path in root.rglob('*'):
        info = path.lstat()
        require(info.st_uid == os.getuid() and not info.st_mode & 0o002, 'return_stage_owner_or_mode')
        if stat.S_ISDIR(info.st_mode):
            directory(path)
            continue
        name = path.relative_to(receiver.repository.root).as_posix()
        if receipt and path == root/'received.json':
            continue
        captured = PassiveFile(path, limit=MAX_BYTES)
        require(stat.S_IMODE(info.st_mode) == 0o644, 'return_staged_mode_changed')
        actual[name] = captured.raw
    require(actual == expected, 'return_staged_inventory_changed')


def _native_replay(receiver):
    proof = replay(receiver.project.root, receiver.local_draft)
    require(proof is not None and proof['replayed'] and proof['write_state'] == 'committed',
            'return_native_receipt_missing', 6)
    return proof


def record(receiver):
    # Persist the native historical proof, not the transient live-write observation.
    proof = _native_replay(receiver)
    value = {'format_version':'specroad-return-receipt-v1', 'package_sha256':receiver.source.sha256,
        'return_manifest_sha256':sha256(canonical_json_bytes(receiver.data.manifest)).hexdigest(),
        'draft_sha256':receiver.local_draft.original.sha256,
        'completion':proof['completion']}
    with LockFiles(receiver.stage) as files:
        files.acquire(); staged(receiver)
        _write_new(files.root_fd, 'received.json', canonical_json_bytes(value))
        files.check_root()
    return value


def read_replay(receiver):
    if not os.path.lexists(receiver.stage):
        return None
    path=receiver.stage/'received.json'
    require(os.path.lexists(path), 'return_stage_without_complete_receipt', 6)
    staged(receiver, receipt=True)
    captured=PassiveFile(path)
    value=parse_json_object(captured.raw)
    proof=_native_replay(receiver)
    expected={'format_version':'specroad-return-receipt-v1','package_sha256':receiver.source.sha256,
        'return_manifest_sha256':sha256(canonical_json_bytes(receiver.data.manifest)).hexdigest(),
        'draft_sha256':receiver.local_draft.original.sha256,'completion':proof['completion']}
    require(captured.raw==canonical_json_bytes(expected) and value==expected, 'return_receipt_mismatch', 6)
    require(receiver.prior_result is not None, 'return_prior_native_result_required', 6)
    prior = receiver.prior_result
    snapshot = receiver.opening.runtime.read_snapshot(prior.path, expected_sha256=prior.sha256)
    require(snapshot.operation == 'apply' and not snapshot.dry_run and snapshot.primary_result.success,
            'return_prior_result_not_successful', 6)
    receipt_name = path.relative_to(receiver.repository.root).as_posix()
    prefix = receiver.data.manifest['project_path']
    draft_name = ('' if prefix == '.' else prefix + '/') + receiver.local_draft.original.path
    originals = snapshot.effective.files
    require(receipt_name in originals and originals[receipt_name].content == captured.raw
            and draft_name in originals and originals[draft_name].content == receiver.local_draft.source_bytes,
            'return_prior_result_receipt_mismatch', 6)
    current = _api_call(receiver.api, receiver.api.context, receiver.repository.root, capture_mode='safe')
    require(binding(current) == binding(snapshot.context), 'return_replay_state_changed', 6)
    from ..authoring._inspection_snapshot import InspectionSnapshot
    live = InspectionSnapshot(receiver.project.root, None, include_archive_objects=True)
    observed = dict(live.raw)
    require(observed.pop(receiver.local_draft.original.path, None) == receiver.local_draft.source_bytes
            and observed == receiver.basis.raw, 'return_replay_project_changed', 6)
    live.verify_current(); prior.verify_current()
    captured.verify_current(); receiver.verify_current()
    return proof
