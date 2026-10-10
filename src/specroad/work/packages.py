"""Self-contained, externally hash-bound transport of read-only Work chains.

All declared input and checkpoint bytes are retained. Restore recreates private
storage with a new root-inode binding; data is never executable authority. Native
write work is refused until a separate native transaction/receipt export binding
exists. These host APIs process complete ZIP32 bytes, not CLI/multipart streams.
"""

from hashlib import sha256
import os

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ._archive import ArchiveError, encode_archive, decode_archive, _require
from ._data_contract import WorkManifestError, _object, _parse, _hash, _count
from .checkpoints import (CheckpointStore, _StoredObjects, _read_reference,
                          _reference, _reference_check, _verify_bindings)
from .control import _initial, _read
from .manifest import _entries, _tree, read_work_manifest, read_work_successor
from .result_files import _ensure_work
from .resume import _runtime_build
from .root import WorkDirectory
from ._root_lock import _BINDING, _CURRENT, _DIRECTORIES, _LOCK, _private


_MANIFEST = 'work-package.json'
_FIELDS = ('format_version', 'package_kind', 'work_id', 'checkpoint_generation',
           'checkpoint_sha256', 'initial_manifest', 'initial_checkpoint_sha256', 'tool_build')


def _supported(manifest):
    if manifest.as_dict()['command_class'] != 'read_only':
        raise ArchiveError('normative_work_package_requires_native_binding', exit_code=6)


def _capture(store, held, pointer):
    """Capture only bytes reachable from the already verified published chain."""
    payloads = {'work.json': pointer[0]}
    reference = store._pointer_value(pointer[0])['checkpoint']
    bindings, seen = {}, set()
    while reference is not None:
        _require(reference['sha256'] not in seen, 'work_package_checkpoint_cycle')
        seen.add(reference['sha256'])
        raw = _read_reference(held, 'checkpoints', reference, bindings=bindings)
        payloads['checkpoints/' + reference['sha256'] + '.json'] = raw
        record = _parse(raw)
        index = _StoredObjects(held, bindings)
        rows = _entries('checkpoint-objects', record['objects'], index)
        for digest, content in index.cache.items():
            payloads['objects/' + digest] = content
        for item in [record['manifest'], *rows]:
            content = _read_reference(held, 'objects', item, bindings=bindings)
            payloads['objects/' + item['sha256']] = content
        reference = record['parent']
    _verify_bindings(held, bindings)
    return payloads


def _decode(metadata, payloads, registry, build):
    """Check the entire portable chain before any destination is allocated."""
    _object(metadata, _FIELDS)
    _require(metadata['format_version'] == 'work-package-v1'
             and metadata['package_kind'] == 'work', 'unsupported_work_package')
    if metadata['tool_build'] != build:
        raise ArchiveError('incompatible_work_package_build', exit_code=6)
    used = set()

    def get(path):
        _require(path in payloads, 'work_package_bytes_missing')
        used.add(path)
        return payloads[path]

    def referenced(folder, reference):
        _reference_check(reference)
        path = folder + '/' + reference['sha256'] + ('.json' if folder == 'checkpoints' else '')
        raw = get(path)
        _require(_reference(raw) == reference, 'work_package_reference_mismatch')
        if folder == 'checkpoints':
            _require(len(raw) <= 65536, 'work_package_checkpoint_too_large')
        return raw

    class Objects:
        def get(self, digest, default=None):
            _hash(digest)
            raw = get('objects/' + digest)
            _require(sha256(raw).hexdigest() == digest and len(raw) <= 65536,
                     'work_package_index_invalid')
            _require(canonical_json_bytes(_parse(raw)) == raw, 'work_package_index_invalid')
            return raw

    raw = get('work.json'); pointer = _parse(raw)
    _object(pointer, ('format_version', 'work_id', 'checkpoint_generation',
                      'checkpoint_sha256', 'checkpoint'))
    _require(pointer['format_version'] == 'work-current-v1'
             and canonical_json_bytes(pointer) == raw, 'work_package_pointer_invalid')
    for key in ('work_id', 'checkpoint_generation', 'checkpoint_sha256'):
        _require(canonical_json_bytes(pointer[key]) == canonical_json_bytes(metadata[key]),
                 'work_package_binding_mismatch')
    _count(pointer['checkpoint_generation']); _hash(pointer['checkpoint_sha256'])
    reference, generation = pointer['checkpoint'], pointer['checkpoint_generation']
    seen, chain = set(), []
    while True:
        _reference_check(reference)
        _require(reference['sha256'] not in seen, 'work_package_checkpoint_cycle')
        seen.add(reference['sha256'])
        raw = referenced('checkpoints', reference); record = _parse(raw)
        _object(record, ('format_version', 'work_id', 'checkpoint_generation',
                         'checkpoint_sha256', 'manifest', 'objects', 'parent'))
        _count(record['checkpoint_generation']); _hash(record['checkpoint_sha256'])
        _require(record['format_version'] == 'stored-work-checkpoint-v1'
                 and canonical_json_bytes(record) == raw
                 and record['work_id'] == pointer['work_id']
                 and record['checkpoint_generation'] == generation,
                 'work_package_checkpoint_invalid')
        rows = _entries('checkpoint-objects', record['objects'], Objects())
        _require(canonical_json_bytes(record['objects'])
                 == canonical_json_bytes(_tree('checkpoint-objects', rows, {})),
                 'noncanonical_work_package_inventory')
        objects = {}
        for item in rows:
            content = referenced('objects', item)
            _require(item['sha256'] not in objects, 'duplicate_work_package_object')
            objects[item['sha256']] = content
        _require([item['sha256'] for item in rows] == sorted(objects), 'work_package_object_order')
        manifest_raw = referenced('objects', record['manifest'])
        manifest = read_work_manifest(manifest_raw, objects, registry=registry, expected_tool_build=build)
        value = manifest.as_dict(); _supported(manifest)
        _require(manifest.raw == manifest_raw and value['work_id'] == pointer['work_id']
                 and value['checkpoint_generation'] == generation
                 and value['checkpoint_sha256'] == record['checkpoint_sha256'],
                 'work_package_manifest_mismatch')
        chain.append(manifest)
        if record['parent'] is None:
            _require(generation == 0, 'work_package_initial_missing')
            break
        _require(generation > 0, 'work_package_generation_invalid')
        generation -= 1
        reference = record['parent']
    chain.reverse()
    initial, previous = chain[0], chain[0]
    _reference_check(metadata['initial_manifest']); _hash(metadata['initial_checkpoint_sha256'])
    _require(_reference(initial.raw) == metadata['initial_manifest']
             and initial.as_dict()['checkpoint_sha256'] == metadata['initial_checkpoint_sha256'],
             'work_package_initial_mismatch')
    for manifest in chain[1:]:
        previous = read_work_successor(manifest.raw, manifest.objects, previous=previous,
                                       registry=registry, expected_tool_build=build)
    _require(previous.as_dict()['checkpoint_sha256'] == metadata['checkpoint_sha256'],
             'work_package_current_mismatch')
    _require(used == set(payloads), 'unreferenced_work_package_payload')
    return tuple(chain)


def _checked_package(raw, expected_sha256, registry, build):
    metadata, payloads = decode_archive(raw, manifest_name=_MANIFEST, expected_sha256=expected_sha256)
    try:
        chain = _decode(metadata, payloads, registry, build)
    except (WorkManifestError, ModelError) as error:
        raise ArchiveError('invalid_work_package') from error
    return chain, payloads


def export_work_package(store):
    """Return canonical inert ZIP bytes without writing an output or project.

    The caller retains these exact bytes and their external SHA-256. Root inode,
    process locks, temporary files and unreferenced scratch are not transport
    data. Every declared generation and its complete object set are included.
    """
    build = _runtime_build(); _initial(store, build); _supported(store._initial)
    with store._location.inspect_checkpoint() as held:
        pointer, current = _read(store, held, build); _supported(current)
        value = current.as_dict()
        metadata = {'format_version': 'work-package-v1', 'package_kind': 'work',
            **{key: value[key] for key in ('work_id', 'checkpoint_generation', 'checkpoint_sha256')},
            'initial_manifest': _reference(store._initial.raw),
            'initial_checkpoint_sha256': store._initial.as_dict()['checkpoint_sha256'],
            'tool_build': build}
        raw = encode_archive(_MANIFEST, metadata, _capture(store, held, pointer))
        chain, _ = _checked_package(raw, sha256(raw).hexdigest(), store._registry, build)
        _require(chain[0].raw == store._initial.raw and chain[-1].raw == current.raw,
                 'work_package_source_changed')
        _ensure_work(store, held, pointer, current, build)
        return raw


def _restore_target(held, payloads, *, complete=False):
    """Refuse foreign arrivals without deleting them or the published prefix."""
    held.check()
    required = {_BINDING, _LOCK, *_DIRECTORIES}
    names = set(os.listdir(held._root))
    _require(required <= names <= required | {_CURRENT}, 'work_package_target_changed')
    for folder, directory in zip(_DIRECTORIES, held._children):
        expected = {name[len(folder) + 1:] for name in payloads if name.startswith(folder + '/')}
        current = set(os.listdir(directory))
        _require(current <= expected and (not complete or current == expected),
                 'work_package_target_changed')
        for name in current:
            _private(os.stat(name, dir_fd=directory, follow_symlinks=False))
        _require(set(os.listdir(directory)) == current, 'work_package_target_changed')
    _require(set(os.listdir(held._root)) == names, 'work_package_target_changed')
    held.check()


def restore_work_package(raw, *, expected_sha256, registry, protected_roots, directory):
    """Verify every package byte, then restore into one missing/empty safe root.

    No command, imported package code or Recovery is executed. Every original
    generation is republished through the existing durable store. An I/O error
    preserves actual files and any published prefix; it is not rolled back or
    relabelled as a completed restore. Existing nonempty roots are never reused.
    """
    _require(directory is not None, 'work_package_target_required')
    build = _runtime_build()
    chain, payloads = _checked_package(raw, expected_sha256, registry, build)
    _require(_runtime_build() == build, 'work_package_runtime_changed')
    location = WorkDirectory(chain[0], protected_roots=protected_roots, directory=directory)
    store = CheckpointStore(location, chain[0])
    with location.for_checkpoint(require_empty=True) as held:
        _require(_runtime_build() == build, 'work_package_runtime_changed')
        _restore_target(held, payloads)
        for manifest in chain:
            _require(_runtime_build() == build, 'work_package_runtime_changed')
            store._publish_held(held, manifest, store._pointer(held))
            _restore_target(held, payloads)
        _require(store._pointer(held)[0] == payloads['work.json'], 'work_package_restore_mismatch')
        _ensure_work(store, held, store._pointer(held), chain[-1], build)
        _restore_target(held, payloads, complete=True)
    return store
