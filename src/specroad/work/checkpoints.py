"""Durable inert work generations under a caller-trusted initial work binding.

This publishes data, not execution permission, Code 8 or a command result.
Readers preserve orphan owner records; writers never recover or steal them.
"""

from hashlib import sha256
import os
import secrets

from ..changes._publication_io import replace_bound_image
from ..changes._staging_files import _write_new
from ..model.canonical import canonical_json_bytes
from ..security import paths as guards
from ._data_contract import _object, _parse, _hash, _count
from ._root_lock import _private
from .manifest import WorkManifest, read_work_manifest, read_work_successor, _tree, _entries
from .root import WorkDirectory


class CheckpointStorageError(ValueError):
    """A concrete logical storage failure without invented continuation bytes."""

    def __init__(self, reason, *, path=None):
        super().__init__(reason)
        self.reason, self.path = reason, path

    def as_dict(self):
        return {'reason': self.reason, 'path': self.path}


def _check(condition, reason='checkpoint_binding_changed', *, path=None):
    if not condition:
        raise CheckpointStorageError(reason, path=path)


def _reference(raw):
    return {'sha256': sha256(raw).hexdigest(), 'size': len(raw)}


def _reference_check(reference):
    _object(reference, ('sha256', 'size'))
    _hash(reference['sha256']); _count(reference['size'])


def _directory(held, folder):
    return held._children[('checkpoints', 'objects', 'results').index(folder)]


def _read_file(held, folder, name, *, sync=False, expected_size=None,
               maximum=None, bindings=None):
    held.check()
    parent = _directory(held, folder)
    logical = folder + '/' + name
    try:
        before = os.stat(name, dir_fd=parent, follow_symlinks=False)
        _private(before)
        _check(expected_size is None or before.st_size == expected_size,
               'checkpoint_bytes_changed', path=logical)
        _check(maximum is None or before.st_size <= maximum,
               'checkpoint_metadata_too_large', path=logical)
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            _check(guards._signature(os.fstat(fd)) == guards._signature(before), path=logical)
            data = bytearray()
            while len(data) <= before.st_size:
                raw = os.read(fd, min(65536, before.st_size + 1 - len(data)))
                if not raw:
                    break
                data.extend(raw)
            if sync:
                os.fsync(fd)
                os.fsync(parent)
            now = os.stat(name, dir_fd=parent, follow_symlinks=False)
            _private(now)
            _check(len(data) == before.st_size
                   and guards._signature(now) == guards._signature(before)
                   and guards._signature(os.fstat(fd)) == guards._signature(before), path=logical)
            held.check()
            if bindings is not None:
                key, signature = (folder, name), guards._signature(before)
                _check(key not in bindings or bindings[key] == signature,
                       'checkpoint_bytes_changed', path=logical)
                bindings[key] = signature
            return bytes(data)
        finally:
            os.close(fd)
    except FileNotFoundError as error:
        raise CheckpointStorageError('checkpoint_bytes_missing', path=logical) from error


def _read_reference(held, folder, reference, *, bindings=None):
    _reference_check(reference)
    name = reference['sha256'] + ('.json' if folder == 'checkpoints' else '')
    raw = _read_file(held, folder, name, expected_size=reference['size'],
                     maximum=65536 if folder == 'checkpoints' else None, bindings=bindings)
    _check(_reference(raw) == reference, 'checkpoint_bytes_changed', path=folder + '/' + name)
    return raw


def _verify_bindings(held, bindings):
    """Close the checked read set without silently trusting earlier path reads."""
    for (folder, name), signature in bindings.items():
        held.check()
        parent, logical = _directory(held, folder), folder + '/' + name
        try:
            before = os.stat(name, dir_fd=parent, follow_symlinks=False)
            _private(before)
            _check(guards._signature(before) == signature, 'checkpoint_bytes_changed', path=logical)
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            try:
                _check(guards._signature(os.fstat(fd)) == signature,
                       'checkpoint_bytes_changed', path=logical)
                now = os.stat(name, dir_fd=parent, follow_symlinks=False)
                _private(now)
                _check(guards._signature(now) == signature, 'checkpoint_bytes_changed', path=logical)
            finally:
                os.close(fd)
        except FileNotFoundError as error:
            raise CheckpointStorageError('checkpoint_bytes_missing', path=logical) from error
    held.check()


def _ensure_file(held, folder, name, raw):
    held.check()
    parent = _directory(held, folder)
    try:
        os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        _write_new(parent, name, raw)
    # Existing identical bytes also cross the durability boundary before reuse.
    _check(_read_file(held, folder, name, sync=True) == raw,
           'checkpoint_bytes_changed', path=folder + '/' + name)
    held.check()


class _StoredObjects:
    """Lazy trusted adapter for the existing bounded-fanout manifest reader."""

    def __init__(self, held, bindings):
        self.held = held
        self.bindings = bindings
        self.cache = {}

    def get(self, digest, default=None):
        _hash(digest)
        if digest not in self.cache:
            # A 64-entry inventory segment has only fixed hash references/counts.
            # This metadata limit is unrelated to the size of stored input bytes.
            raw = _read_file(self.held, 'objects', digest, maximum=65536, bindings=self.bindings)
            _check(sha256(raw).hexdigest() == digest, 'checkpoint_bytes_changed',
                   path='objects/' + digest)
            _check(canonical_json_bytes(_parse(raw)) == raw, 'noncanonical_checkpoint_segment',
                   path='objects/' + digest)
            self.cache[digest] = raw
        return self.cache[digest]


class CheckpointStore:
    """Publish/read inert generations; initial must be independently trusted.

    Both operations acquire the native work mutex. Reading does not write files
    or take over an orphan owner. Publication accepts only the initial generation
    or the immediate validated successor of the actual current generation.
    """

    def __init__(self, location, initial):
        _check(type(location) is WorkDirectory and type(initial) is WorkManifest,
               'trusted_initial_checkpoint_required')
        value = initial.as_dict()
        _check(value['checkpoint_generation'] == 0
               and location._work_id == value['work_id']
               and location._initial_hash == value['checkpoint_sha256'],
               'trusted_initial_checkpoint_required')
        self._location, self._initial = location, initial
        self._build, self._registry = value['tool_build'], initial._registry

    def _pointer(self, held):
        try:
            return held._read('work.json')
        except FileNotFoundError:
            return None

    def _pointer_value(self, raw):
        value = _parse(raw)
        _object(value, ('format_version', 'work_id', 'checkpoint_generation',
                        'checkpoint_sha256', 'checkpoint'))
        _check(value['format_version'] == 'work-current-v1'
               and value['work_id'] == self._location._work_id)
        _count(value['checkpoint_generation']); _hash(value['checkpoint_sha256'])
        _reference_check(value['checkpoint'])
        _check(canonical_json_bytes(value) == raw)
        return value

    def _read_chain(self, held, pointer):
        current = self._pointer_value(pointer)
        reference, generation = current['checkpoint'], current['checkpoint_generation']
        seen, chain, bindings = set(), [], {}
        while True:
            _reference_check(reference)
            _check(reference['sha256'] not in seen, 'checkpoint_cycle')
            seen.add(reference['sha256'])
            raw = _read_reference(held, 'checkpoints', reference, bindings=bindings)
            record = _parse(raw)
            _object(record, ('format_version', 'work_id', 'checkpoint_generation',
                             'checkpoint_sha256', 'manifest', 'objects', 'parent'))
            _count(record['checkpoint_generation']); _hash(record['checkpoint_sha256'])
            _check(record['format_version'] == 'stored-work-checkpoint-v1'
                   and record['work_id'] == current['work_id']
                   and record['checkpoint_generation'] == generation
                   and canonical_json_bytes(record) == raw)
            stored = _StoredObjects(held, bindings)
            rows = _entries('checkpoint-objects', record['objects'], stored)
            objects = {}
            for row in rows:
                _reference_check(row)
                _check(row['sha256'] not in objects, 'duplicate_checkpoint_object')
                objects[row['sha256']] = _read_reference(held, 'objects', row, bindings=bindings)
            _check([row['sha256'] for row in rows] == sorted(objects))
            manifest_raw = _read_reference(held, 'objects', record['manifest'], bindings=bindings)
            manifest = read_work_manifest(manifest_raw, objects, registry=self._registry,
                                          expected_tool_build=self._build)
            value = manifest.as_dict()
            _check(manifest.raw == manifest_raw and value['work_id'] == record['work_id']
                   and value['checkpoint_generation'] == generation
                   and value['checkpoint_sha256'] == record['checkpoint_sha256'])
            chain.append(manifest)
            if record['parent'] is None:
                _check(generation == 0)
                break
            _check(generation > 0)
            generation -= 1
            reference = record['parent']
        previous = chain.pop()
        _check(previous.raw == self._initial.raw
               and dict(previous.objects) == dict(self._initial.objects))
        for manifest in reversed(chain):
            previous = read_work_successor(manifest.raw, manifest.objects, previous=previous,
                registry=self._registry, expected_tool_build=self._build)
        value = previous.as_dict()
        _check(value['checkpoint_generation'] == current['checkpoint_generation']
               and value['checkpoint_sha256'] == current['checkpoint_sha256'])
        _verify_bindings(held, bindings)
        return previous

    def read(self):
        """Load exactly the published complete generation, or None if unpublished."""
        with self._location.inspect_checkpoint() as held:
            pointer = self._pointer(held)
            if pointer is None:
                return None
            result = self._read_chain(held, pointer[0])
            _check(self._pointer(held) == pointer, 'checkpoint_pointer_changed')
            return result

    def publish(self, manifest):
        """Secure every referenced byte before atomically replacing work.json.

        Any error retains all actual files. If a failure occurs after replacement,
        the caller must inspect current data instead of assuming a rollback.
        """
        _check(type(manifest) is WorkManifest, 'checked_checkpoint_required')
        manifest = read_work_manifest(manifest.raw, manifest.objects, registry=self._registry,
                                      expected_tool_build=self._build)
        _check(manifest.as_dict()['work_id'] == self._location._work_id)
        with self._location.for_checkpoint() as held:
            before = self._pointer(held)
            if before is None:
                _check(manifest.raw == self._initial.raw
                       and dict(manifest.objects) == dict(self._initial.objects))
                parent = None
            else:
                previous = self._read_chain(held, before[0])
                manifest = read_work_successor(manifest.raw, manifest.objects, previous=previous,
                    registry=self._registry, expected_tool_build=self._build)
                parent = self._pointer_value(before[0])['checkpoint']
            index = {}
            reference = _tree('checkpoint-objects', [
                {'sha256': digest, 'size': len(raw)}
                for digest, raw in sorted(manifest.objects.items())], index)
            payloads = dict(manifest.objects)
            for digest, raw in [*index.items(), (sha256(manifest.raw).hexdigest(), manifest.raw)]:
                _check(digest not in payloads or payloads[digest] == raw)
                payloads[digest] = raw
            for digest, raw in sorted(payloads.items()):
                _ensure_file(held, 'objects', digest, raw)
            value = manifest.as_dict()
            record = canonical_json_bytes({'format_version': 'stored-work-checkpoint-v1',
                'work_id': value['work_id'], 'checkpoint_generation': value['checkpoint_generation'],
                'checkpoint_sha256': value['checkpoint_sha256'], 'manifest': _reference(manifest.raw),
                'objects': reference, 'parent': parent})
            checkpoint = _reference(record)
            _ensure_file(held, 'checkpoints', checkpoint['sha256'] + '.json', record)
            pointer = canonical_json_bytes({'format_version': 'work-current-v1',
                'work_id': value['work_id'], 'checkpoint_generation': value['checkpoint_generation'],
                'checkpoint_sha256': value['checkpoint_sha256'], 'checkpoint': checkpoint})
            _check(self._read_chain(held, pointer).raw == manifest.raw)
            temporary = '.current-' + secrets.token_hex(16) + '.json'
            directory = _directory(held, 'checkpoints')
            identity = _write_new(directory, temporary, pointer)
            def before_replace():
                held.check()
                _check(self._pointer(held) == before, 'checkpoint_pointer_changed')
                _check(self._read_chain(held, pointer).raw == manifest.raw)
                _check(self._pointer(held) == before, 'checkpoint_pointer_changed')
            replace_bound_image(directory, temporary, held._root, 'work.json',
                size=len(pointer), digest=sha256(pointer).hexdigest(), identity=identity,
                source_changed=lambda: CheckpointStorageError('checkpoint_pointer_changed'),
                before_replace=before_replace)
            _check(self._pointer(held) == (pointer, identity), 'checkpoint_pointer_changed')
            _check(self._read_chain(held, pointer).raw == manifest.raw)
            _check(self._pointer(held) == (pointer, identity), 'checkpoint_pointer_changed')
            held.check()
            return manifest
