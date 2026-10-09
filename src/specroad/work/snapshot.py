"""Incremental capture of a trusted caller's explicitly declared input set.

Captured bytes are immutable hash-addressed data. The live builder is neither
a durable checkpoint nor an atomic observation of a whole normative project.
"""

from contextlib import ExitStack, contextmanager
from hashlib import sha256
import json
import os
from types import MappingProxyType

from ..changes._lock_files import LockFiles
from ..changes.lock_values import ProjectLockError
from ..model.canonical import canonical_json_bytes
from ..security import ProjectBoundary, SafetyViolation
from ..security.paths import _parts, _signature
from ..security.resource_access import opened_resource
from ..storage.operational_preflight import observe_operational_preflight


class SnapshotCaptureError(ValueError):
    """Logical resource identity without exposing an absolute source location."""

    def __init__(self, reason, *, root_id=None, path=None, object_sha256=None):
        super().__init__(reason)
        self.reason = reason
        self.root_id = root_id
        self.path = path
        self.object_sha256 = object_sha256

    def as_dict(self):
        return {'reason': self.reason, 'root_id': self.root_id, 'path': self.path,
                'object_sha256': self.object_sha256}


def _positive(value):
    if type(value) is not int or value <= 0:
        raise ValueError('A positive integer work window is required')
    return value


def _plan(roots, entries):
    if type(roots) is not dict or not roots:
        raise ValueError('Explicit named source boundaries are required')
    for key, boundary in roots.items():
        if (type(key) is not str or not key or key != key.strip()
                or any(ord(c) < 32 or ord(c) == 127 for c in key)
                or type(boundary) is not ProjectBoundary):
            raise ValueError('Invalid source root declaration')
        key.encode('utf-8')
    if type(entries) is not list and type(entries) is not tuple:
        raise ValueError('An explicit input sequence is required')
    result = []
    for entry in entries:
        if (type(entry) is not dict or any(type(k) is not str for k in entry)
                or set(entry) != {'root_id', 'path'}
                or type(entry['root_id']) is not str or entry['root_id'] not in roots
                or type(entry['path']) is not str):
            raise ValueError('Invalid source input declaration')
        _parts(entry['path'])
        result.append((entry['root_id'], entry['path']))
    if len(set(result)) != len(result):
        raise ValueError('Duplicate declared source input')
    return tuple(sorted(result))


def _check_sources(handles):
    for root_id, boundary, files in handles:
        try:
            files.require_held()
            boundary._check_root()
            status = observe_operational_preflight(boundary)
        except (ProjectLockError, SafetyViolation, OSError) as error:
            raise SnapshotCaptureError('source_guard_changed', root_id=root_id) from error
        if status['consistency_state'] != 'consistent' or not status['inspection_complete']:
            paths = sorted(status['unresolved_paths'] + status['unknown_paths'])
            reason = 'source_recovery_required' if status['recovery_required'] else 'source_operational_state_unknown'
            raise SnapshotCaptureError(reason, root_id=root_id, path=paths[0] if paths else None)


@contextmanager
def _locked_sources(roots):
    # Reuse the writer's real root-inode mutex without creating an owner record.
    # A live task retains it across advance calls and releases it at seal/close.
    with ExitStack() as stack:
        held, handles = {}, []
        for root_id, boundary in sorted(roots.items()):
            try:
                boundary._check_root()
                identity = boundary._root_identity
                if identity not in held:
                    files = stack.enter_context(LockFiles(boundary.root))
                    if files.boundary._root_identity != identity:
                        raise SafetyViolation('Input root changed before capture')
                    files.acquire()
                    held[identity] = files
                handles.append((root_id, boundary, held[identity]))
            except (ProjectLockError, SafetyViolation, OSError) as error:
                reason = ('source_writer_busy' if isinstance(error, ProjectLockError)
                          and error.reason == 'project_lock_busy' else 'source_guard_unavailable')
                raise SnapshotCaptureError(reason, root_id=root_id) from error
        _check_sources(handles)
        yield handles
        _check_sources(handles)


class InputSnapshotTask:
    """Retain live progress across advance calls and keep all captured bytes.

    Enumeration covers exactly the caller's declared set, not a discovered
    normative model closure. Each read uses the existing guarded resource
    adapter. Whole-store memory and cross-process restart remain separate work.
    """

    def __init__(self, roots, entries, *, block_bytes=65536):
        self._block_bytes = min(_positive(block_bytes), 65536)
        self._plan = _plan(roots, entries)
        self._roots = dict(roots)
        self._entries = []
        self._objects = {}
        self._units = 0
        self._bytes = 0
        self._phase = 'enumerating'
        self._current = None
        self._manifest = None
        self._manifest_hash = None
        self._failed = False
        self._closed = False
        self._error = None
        self._pid = os.getpid()
        self._signatures = {}
        self._validated = 0
        self._revalidated = 0
        self._validation_bytes = 0
        self._steps = self._capture()

    def _capture(self):
        for root_id, path in self._plan:
            self._entries.append({'root_id': root_id, 'path': path, 'size': None,
                'captured_bytes': 0, 'sha256': None, 'complete': False, 'chunks': []})
            yield None  # One deterministic declaration; no content claim.
        with _locked_sources(self._roots) as handles:
            yield from self._capture_files()
            self._phase = 'validating'
            _check_sources(handles)
            yield from self._validate_files()
            # A change after an earlier validation unit still prevents sealing.
            # Noncooperating OS writes cannot be made atomic by this observation.
            for entry in self._entries:
                self._current = entry
                with opened_resource(self._roots[entry['root_id']], entry['path']) as (_, initial):
                    if _signature(initial) != self._signatures[(entry['root_id'], entry['path'])]:
                        raise SnapshotCaptureError('source_changed_during_closure',
                            root_id=entry['root_id'], path=entry['path'])
            self._current = None
            self._phase = 'sealing'
            value = {'format_version': 'captured-inputs-v1', 'inputs': [
                {key: entry[key] for key in ('root_id', 'path', 'size', 'sha256')}
                for entry in self._entries]}
            manifest = canonical_json_bytes(value)
            manifest_hash = sha256(manifest).hexdigest()
        self._manifest = manifest
        self._manifest_hash = manifest_hash
        self._phase = 'sealed'
        yield None

    def _capture_files(self):
        self._phase = 'capturing'
        for entry in self._entries:
            self._current = entry
            digest = sha256()
            root_id, path = entry['root_id'], entry['path']
            with opened_resource(self._roots[root_id], path) as (fd, initial):
                entry['size'] = initial.st_size
                self._signatures[(root_id, path)] = _signature(initial)
                yield None  # Opened, guarded input; no bytes have been invented.
                while entry['captured_bytes'] < initial.st_size:
                    raw = os.read(fd, min(self._block_bytes, initial.st_size - entry['captured_bytes']))
                    if not raw:
                        raise SnapshotCaptureError('source_truncated', root_id=root_id, path=path)
                    object_hash = sha256(raw).hexdigest()
                    prior = self._objects.get(object_hash)
                    if prior is not None and prior != raw:
                        raise SnapshotCaptureError('captured_hash_conflict', root_id=root_id, path=path)
                    self._objects[object_hash] = raw
                    entry['chunks'].append({'offset': entry['captured_bytes'],
                        'size': len(raw), 'sha256': object_hash})
                    digest.update(raw)
                    entry['captured_bytes'] += len(raw)
                    self._bytes += len(raw)
                    yield None
                # A growing source cannot become a silently truncated snapshot.
                if os.read(fd, 1):
                    raise SnapshotCaptureError('source_grew', root_id=root_id, path=path)
            # The guarded context verified size, identity, timestamps and paths.
            entry['sha256'] = digest.hexdigest()
            entry['complete'] = True
            yield None  # This one captured input is usable before the full set.

    def _validate_files(self):
        for entry in self._entries:
            self._current = entry
            root_id, path = entry['root_id'], entry['path']
            refreshed = False
            with opened_resource(self._roots[root_id], path) as (fd, initial):
                if _signature(initial) != self._signatures[(root_id, path)]:
                    # Size/mtime are never accepted as a replacement content hash.
                    # Reread only an affected source, once, in bounded blocks.
                    digest, offset = sha256(), 0
                    while offset < initial.st_size:
                        raw = os.read(fd, min(self._block_bytes, initial.st_size - offset))
                        if not raw:
                            raise SnapshotCaptureError('source_truncated', root_id=root_id, path=path)
                        digest.update(raw)
                        offset += len(raw)
                        self._validation_bytes += len(raw)
                        yield None
                    if os.read(fd, 1) or offset != entry['size'] or digest.hexdigest() != entry['sha256']:
                        raise SnapshotCaptureError('source_content_changed', root_id=root_id, path=path)
                    refreshed = True
            self._signatures[(root_id, path)] = _signature(initial)
            self._validated += 1
            self._revalidated += refreshed
            yield None

    def advance(self, max_units):
        """Run at most this many confirmed units; a failed unit is not counted."""
        _positive(max_units)
        if self._pid != os.getpid():
            raise SnapshotCaptureError('capture_not_owned')
        if self._closed or self._failed:
            raise SnapshotCaptureError('capture_not_active')
        if self._manifest is not None:
            return self.state
        try:
            for _ in range(max_units):
                next(self._steps)
                self._units += 1
                if self._manifest is not None:
                    break
        except StopIteration:
            pass
        except BaseException as error:
            self._failed = True
            self._phase = 'failed'
            entry = self._current or {}
            if isinstance(error, SnapshotCaptureError):
                reported = error
            else:
                reason = ('source_missing' if isinstance(error, FileNotFoundError) else
                          'unsafe_or_changed_source' if isinstance(error, SafetyViolation) else
                          'source_io_failure' if isinstance(error, OSError) else 'capture_failed')
                reported = SnapshotCaptureError(reason, root_id=entry.get('root_id'), path=entry.get('path'))
            self._error = reported.as_dict()
            self._steps.close()
            if isinstance(error, (OSError, SafetyViolation)):
                raise reported from error
            raise
        return self.state

    @property
    def state(self):
        # Only data and logical names; never descriptors, absolute paths or hash objects.
        value = {'format_version': 'input-capture-progress-v1', 'phase': self._phase,
            'expected_inputs': len(self._plan), 'enumerated_inputs': len(self._entries),
            'completed_inputs': sum(entry['complete'] for entry in self._entries),
            'confirmed_units': self._units, 'captured_bytes': self._bytes,
            'validated_inputs': self._validated, 'revalidated_inputs': self._revalidated,
            'validation_bytes': self._validation_bytes,
            'inputs': self._entries, 'error': self._error, 'closed': self._closed,
            'complete': self._manifest is not None,
            'input_manifest_sha256': self._manifest_hash, 'model_root_sha256': None,
            'atomic_project_snapshot': False, 'durable_checkpoint': False,
            'continuation_scope': 'current_invocation'}
        return json.loads(canonical_json_bytes(value))

    @property
    def objects(self):
        return MappingProxyType(dict(self._objects))

    @property
    def manifest_bytes(self):
        if self._manifest is None:
            raise SnapshotCaptureError('input_set_incomplete')
        return self._manifest

    def read_block(self, object_sha256):
        if type(object_sha256) is not str:
            raise ValueError('A captured object hash is required')
        try:
            return self._objects[object_sha256]
        except KeyError as error:
            raise SnapshotCaptureError('captured_bytes_missing', object_sha256=object_sha256) from error

    def read_input(self, root_id, path):
        if type(root_id) is not str or type(path) is not str:
            raise ValueError('A logical input identity is required')
        entry = next((entry for entry in self._entries
                      if entry['root_id'] == root_id and entry['path'] == path), None)
        if entry is None or not entry['complete']:
            raise SnapshotCaptureError('input_bytes_incomplete', root_id=root_id, path=path)
        return b''.join(self.read_block(row['sha256']) for row in entry['chunks'])

    def work_inputs(self):
        """Explicit materialization for the current in-memory work-v1 codec."""
        self.manifest_bytes
        return [{'root_id': entry['root_id'], 'path': entry['path'],
                 'raw': self.read_input(entry['root_id'], entry['path'])}
                for entry in self._entries]

    def close(self):
        self._steps.close()
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __reduce__(self):
        raise TypeError('Live input capture tasks cannot be serialized')

    def __copy__(self):
        raise TypeError('Live input capture tasks cannot be copied')

    def __deepcopy__(self, memo):
        raise TypeError('Live input capture tasks cannot be copied')
