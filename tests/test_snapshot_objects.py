"""Real external object storage, exact bytes and protected project boundaries."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
import os

import pytest

from specroad.archive import ObjectReference, SnapshotObject, SnapshotObjectStore, read_snapshot_object
from specroad.changes._lock_files import LockFiles
from specroad.changes.lock_values import ProjectLockError
from specroad.model.errors import ModelError
from specroad.security import ProjectBoundary, SafetyViolation
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, make_project, no_write_attempts


def setup_store(tmp_path):
    project = tmp_path / 'project'; project.mkdir(); make_project(project)
    root = tmp_path / 'objects'; root.mkdir(mode=0o700)
    protected = (ProjectBoundary(project),)
    return SnapshotObjectStore(root, protected_roots=protected), protected


def test_canonical_json_object_uses_the_exact_existing_jcs_bytes_and_digest():
    raw = b' { "z": 1.0, "a": [true, null, "\\u00e4"], "text": "e\\u0301" }\n'
    expected = '{"a":[true,null,"ä"],"text":"e\u0301","z":1}'.encode()
    item = SnapshotObject.from_json(raw); reference = item.reference
    assert item.content == expected and reference.sha256 == sha256(expected).hexdigest()
    assert reference.size == len(expected)
    assert reference.path == 'archive/objects/' + reference.sha256[:2] + '/' + reference.sha256
    assert raw != item.content


@pytest.mark.parametrize('raw', [b'', b'\0\xff\r\n', bytes(range(256)) * 600, b'{ "a": 1 }\r\n'],
                         ids=['empty', 'binary', 'large', 'json_bytes'])
def test_attachment_objects_preserve_every_original_byte(tmp_path, raw):
    store, _ = setup_store(tmp_path); item = SnapshotObject.from_attachment(raw)
    reference = store.put(item)
    assert item.content == raw and store.get(reference) == raw
    assert (store.root / reference.path).read_bytes() == raw
    assert reference.sha256 == sha256(raw).hexdigest() and reference.size == len(raw)


def test_semantically_equal_json_reuses_one_unchanged_physical_object(tmp_path):
    store, _ = setup_store(tmp_path)
    first = store.put(SnapshotObject.from_json(b'{"b":2, "a":1}\n')); path = store.root / first.path
    initial = path.stat(); captured = inventory(store.root)
    second = store.put(SnapshotObject.from_json(b' { "a": 1.0, "b": 2 }'))
    assert first == second and path.read_bytes() == b'{"a":1,"b":2}'
    assert (path.stat().st_ino, path.stat().st_mtime_ns) == (initial.st_ino, initial.st_mtime_ns)
    assert inventory(store.root) == captured


def test_attachment_and_json_roles_can_share_identical_bytes_without_role_inference(tmp_path):
    store, _ = setup_store(tmp_path); raw = b'{"a":1}'
    assert store.put(SnapshotObject.from_json(raw)) == store.put(SnapshotObject.from_attachment(raw))
    assert len(list((store.root / 'archive/objects').glob('*/*'))) == 1


def test_distinct_bytes_have_independent_references_and_both_remain_readable(tmp_path):
    store, _ = setup_store(tmp_path)
    left = store.put(SnapshotObject.from_attachment(b'first'))
    right = store.put(SnapshotObject.from_attachment(b'other'))
    assert left.sha256 != right.sha256 and left.path != right.path
    assert store.get(left) == b'first' and store.get(right) == b'other'


def test_object_and_reference_are_owned_immutable_values():
    item = SnapshotObject(b'content'); reference = item.reference; shown = reference.data; shown['sha256'] = '0' * 64
    with pytest.raises(FrozenInstanceError): item.content = b'changed'
    with pytest.raises(FrozenInstanceError): reference.size = 0
    assert reference.data['sha256'] == sha256(b'content').hexdigest() and item.content == b'content'


@pytest.mark.parametrize('raw', ['bytes', bytearray(b'a'), None, 3])
def test_nonbyte_payloads_are_rejected_without_storage(raw):
    with pytest.raises(ModelError) as caught: SnapshotObject.from_attachment(raw)
    assert caught.value.reason == 'snapshot_object_bytes_required'


@pytest.mark.parametrize('raw,reason', [(b'{"a":1,"a":2}', 'duplicate_key'), (b'[]', 'object_required'),
    (b'{', 'invalid_json'), (b'\xff', 'invalid_utf8')])
def test_invalid_json_is_rejected_before_an_object_can_be_stored(raw, reason):
    with pytest.raises(ModelError) as caught: SnapshotObject.from_json(raw)
    assert caught.value.reason == reason


@pytest.mark.parametrize('digest', ['', 'A' * 64, '../' + 'a' * 61, 'a' * 63, None])
def test_reference_hash_cannot_select_an_arbitrary_path(digest):
    with pytest.raises(ModelError) as caught: ObjectReference(digest, 0)
    assert caught.value.reason == 'snapshot_object_hash_required'


@pytest.mark.parametrize('size', [-1, True, '1', None])
def test_reference_requires_an_exact_nonnegative_integer_size(size):
    with pytest.raises(ModelError) as caught: ObjectReference('a' * 64, size)
    assert caught.value.reason == 'snapshot_object_size_required'


def test_declaration_and_missing_read_create_no_storage(tmp_path):
    store, protected = setup_store(tmp_path); before = inventory(tmp_path)
    with no_write_attempts():
        reopened = SnapshotObjectStore(store.root, protected_roots=protected)
        with pytest.raises(FileNotFoundError): reopened.get(SnapshotObject(b'missing').reference)
    assert inventory(tmp_path) == before and not (store.root / 'archive').exists()


def test_successful_reads_and_reference_checks_remain_read_only(tmp_path):
    store, _ = setup_store(tmp_path); reference = store.put(SnapshotObject(b'content')); before = inventory(tmp_path)
    with no_write_attempts():
        assert store.get(reference) == b'content'
        assert read_snapshot_object(ProjectBoundary(store.root), reference) == b'content'
    assert inventory(tmp_path) == before


def test_actual_project_archive_objects_can_be_verified_without_writes(tmp_path):
    store, protected = setup_store(tmp_path); item = SnapshotObject.from_json(b'{ "revision": 1 }')
    reference = item.reference; path = protected[0].root / reference.path
    path.parent.mkdir(parents=True); path.write_bytes(item.content); before = inventory(protected[0].root)
    with no_write_attempts(): assert read_snapshot_object(protected[0], reference) == b'{"revision":1}'
    assert inventory(protected[0].root) == before


@pytest.mark.parametrize('place', ['same', 'child', 'parent', 'other_project'])
def test_store_cannot_be_used_as_a_project_write_bypass(tmp_path, place):
    store, protected = setup_store(tmp_path); project = protected[0].root
    if place == 'same': root = project
    elif place == 'child': root = project / 'temporary'; root.mkdir(mode=0o700)
    elif place == 'parent': root = tmp_path
    else:
        root = tmp_path / 'other'; root.mkdir(mode=0o700); (root / 'specroad.json').write_bytes(b'{}')
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(SafetyViolation): SnapshotObjectStore(root, protected_roots=protected)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('protected', [(), [], (None,)])
def test_external_store_requires_explicit_real_protected_boundaries(tmp_path, protected):
    with pytest.raises(ModelError) as caught: SnapshotObjectStore(tmp_path, protected_roots=protected)
    assert caught.value.reason == 'snapshot_protected_roots_required'


def test_unsafe_shared_storage_permissions_are_rejected(tmp_path):
    store, protected = setup_store(tmp_path); store.root.chmod(0o755)
    with pytest.raises(SafetyViolation): SnapshotObjectStore(store.root, protected_roots=protected)
    assert not (store.root / 'archive').exists()


def test_store_root_symlink_is_not_resolved_into_an_unchecked_target(tmp_path):
    store, protected = setup_store(tmp_path); link = tmp_path / 'link'; link.symlink_to(store.root, target_is_directory=True)
    with pytest.raises(SafetyViolation): SnapshotObjectStore(link, protected_roots=protected)


def test_normal_put_changes_only_the_owned_external_store(tmp_path):
    store, protected = setup_store(tmp_path); project = inventory(protected[0].root)
    (store.root / 'unrelated').write_bytes(b'keep'); item = SnapshotObject(b'content'); reference = store.put(item)
    assert inventory(protected[0].root) == project and (store.root / 'unrelated').read_bytes() == b'keep'
    assert store.get(reference) == item.content
    assert not list(store.root.rglob('.snapshot-*'))
    assert not (store.root / '.specroad').exists() and not (store.root / '.git').exists()


def test_atomic_target_publication_occurs_only_after_all_object_bytes_exist(tmp_path, monkeypatch):
    store, _ = setup_store(tmp_path); item = SnapshotObject(bytes(range(256)) * 600)
    real = os.link; calls = []
    def observed(source, target, **kwargs):
        directory = store.root / item.reference.path.rsplit('/', 1)[0]
        assert source.startswith('.snapshot-') and (directory / source).read_bytes() == item.content
        assert not (directory / target).exists()
        calls.append(target); return real(source, target, **kwargs)
    monkeypatch.setattr(os, 'link', observed)
    assert store.put(item) == item.reference and calls == [item.reference.sha256]
    assert store.get(item.reference) == item.content


def test_failed_publication_retains_prepared_bytes_and_never_claims_an_object(tmp_path, monkeypatch):
    store, _ = setup_store(tmp_path); item = SnapshotObject(b'content')
    def fail(*args, **kwargs): raise OSError('injected publication failure')
    monkeypatch.setattr(os, 'link', fail)
    with pytest.raises(OSError): store.put(item)
    assert not (store.root / item.reference.path).exists()
    assert [p.read_bytes() for p in store.root.rglob('.snapshot-*')] == [item.content]


@pytest.mark.parametrize('raw,reason', [(b'bad', 'snapshot_object_size_mismatch'), (b'damaged', 'snapshot_object_hash_mismatch')])
def test_existing_corrupted_target_is_never_overwritten(tmp_path, raw, reason):
    store, _ = setup_store(tmp_path); item = SnapshotObject(b'content'); target = store.root / item.reference.path
    target.parent.mkdir(parents=True); target.write_bytes(raw); before = inventory(store.root)
    with pytest.raises(ModelError) as caught: store.put(item)
    assert caught.value.reason == reason and inventory(store.root) == before


def test_an_active_native_store_lock_prevents_a_second_put_without_creating_files(tmp_path):
    store, _ = setup_store(tmp_path); before = inventory(store.root)
    with LockFiles(store.root) as held:
        held.acquire()
        with pytest.raises(ProjectLockError) as caught: store.put(SnapshotObject(b'content'))
        assert caught.value.reason == 'project_lock_busy'
    assert inventory(store.root) == before


def test_stored_objects_survive_reopening_from_an_isolated_fresh_process(tmp_path):
    store, protected = setup_store(tmp_path); reference = store.put(SnapshotObject.from_json(b'{ "v": 1.0 }'))
    body = ('from specroad.archive import ObjectReference, SnapshotObjectStore\nfrom specroad.security import ProjectBoundary\n'
        + 'store=SnapshotObjectStore(' + repr(str(store.root)) + ', protected_roots=(ProjectBoundary('
        + repr(str(protected[0].root)) + '),))\nassert store.get(ObjectReference('
        + repr(reference.sha256) + ',' + str(reference.size) + '))==b\'{"v":1}\'\n')
    result = run_core(body, tmp_path, capture=True)
    assert result.returncode == 0, result.stderr


def test_portable_distribution_can_store_and_read_the_same_snapshot_bytes(tmp_path):
    store, protected = setup_store(tmp_path); _, package = build_distribution(tmp_path / 'distribution')
    body = ('import sys;sys.path.insert(0,' + repr(str(package)) + ')\n'
        'from specroad.archive import SnapshotObject, SnapshotObjectStore\nfrom specroad.security import ProjectBoundary\n'
        + 's=SnapshotObjectStore(' + repr(str(store.root)) + ', protected_roots=(ProjectBoundary('
        + repr(str(protected[0].root)) + '),))\no=SnapshotObject.from_json(b\'{ "a":1 }\')\n'
        'assert s.get(s.put(o))==b\'{"a":1}\'\n')
    result = run_python(['-I', '-S', '-B', '-c', body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr


def test_unrelated_git_ancestor_is_not_a_specroad_project_or_protected_boundary(tmp_path):
    store, protected = setup_store(tmp_path)
    parent = tmp_path / 'git-container'; parent.mkdir(); (parent / '.git').mkdir()
    root = parent / 'external'; root.mkdir(mode=0o700)
    external = SnapshotObjectStore(root, protected_roots=protected)
    before = inventory(protected[0].root); item = SnapshotObject(b'independent of Git provenance')
    assert external.get(external.put(item)) == item.content
    assert inventory(protected[0].root) == before and list((parent / '.git').iterdir()) == []
