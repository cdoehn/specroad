"""Explicit external diagnostic sorting in an exclusively owned private directory.

This first backend owns immutable JSONL runs and a live delivery cursor. It does
not implement a work-v1 checkpoint, implicit project writes or process resume.
Native I/O/allocation errors propagate; partial owned files are never removed.
"""

from contextlib import contextmanager
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import stat

from ..security.errors import SafetyViolation
from ..security.paths import ProjectBoundary, _HAS_SAFE_OPEN, _identity, _parts, _regular, _signature
from ..storage.byte_binding import fingerprint_reader
from ..storage._spool_segments import RunSegment as _Run, RunCursor as DiagnosticCursor, _positive
from ..runtime.control_points import complete_steps
from .ordering import diagnostic_key
from .values import Diagnostic


def _json_line(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")


class DiagnosticSpool:
    """An owned spool capability; construct through create_diagnostic_spool.

    Closing releases handles only. Callers retain the directory and all runs.
    The returned manifest is a detached description, never write authority.
    """

    _record_field = "diagnostic"
    _format = "diagnostic-spool-v1"
    _ordering = "diagnostic-key-v1"
    _cursor_format = "diagnostic-cursor-v1"
    _sort_key = staticmethod(diagnostic_key)
    _decode = staticmethod(Diagnostic.from_dict)

    def __init__(self, root, protected_roots):
        self._fds = []
        self._entries = []
        self._cursors = set()
        self._counter = 0
        self._operation = None
        self._manifest = None
        self._manifest_ref = None
        self._final = None
        if type(protected_roots) is not tuple or not protected_roots or any(
                type(boundary) is not ProjectBoundary for boundary in protected_roots):
            raise ValueError("Explicit protected project/input/output boundaries are required")
        raw = os.fspath(root)
        if type(raw) is not str or not raw.startswith("/") or raw.startswith("//"):
            raise SafetyViolation("An absolute spool path is required")
        parts = _parts(raw[1:])
        self.root = Path(raw)
        self._protected = protected_roots
        for boundary in self._protected:
            boundary._check_root()
            if self.root.is_relative_to(boundary.root) or boundary.root.is_relative_to(self.root):
                raise SafetyViolation("Spool and protected roots overlap")
        if not _HAS_SAFE_OPEN or os.mkdir not in os.supports_dir_fd:
            raise SafetyViolation("Secure external spooling is unavailable")
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        try:
            parent = self._adopt_descriptor(os.open("/", flags))
            for name in parts[:-1]:
                parent = self._open_directory(parent, name, flags)
            self._check()
            os.mkdir(parts[-1], 0o700, dir_fd=parent)
            self._directory = self._open_directory(parent, parts[-1], flags)
            os.fsync(parent)
            self._check()
        except BaseException:
            self.close()
            raise

    def _adopt_descriptor(self, descriptor):
        try:
            self._fds.append(descriptor)
        except BaseException:
            os.close(descriptor)
            raise
        return descriptor

    def _open_directory(self, parent, name, flags):
        before = os.stat(name, dir_fd=parent, follow_symlinks=False)
        _regular(before, directory=True)
        opened = self._adopt_descriptor(os.open(name, flags, dir_fd=parent))
        if _identity(os.fstat(opened)) != _identity(before):
            raise SafetyViolation("Spool ancestor changed while opening")
        self._entries.append((parent, name, opened, _identity(before)))
        return opened

    def _check(self):
        if not self._fds:
            raise ValueError("Spool is closed")
        for boundary in self._protected:
            boundary._check_root()
        for parent, name, descriptor, identity in self._entries:
            current = os.stat(name, dir_fd=parent, follow_symlinks=False)
            _regular(current, directory=True)
            if _identity(current) != identity or _identity(os.fstat(descriptor)) != identity:
                raise SafetyViolation("Spool directory changed during use")
        if hasattr(self, "_directory"):
            info = os.fstat(self._directory)
            if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise SafetyViolation("Spool directory is not private")

    def _file_info(self, name):
        info = os.stat(name, dir_fd=self._directory, follow_symlinks=False)
        _regular(info)
        if info.st_nlink != 1 or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise SafetyViolation("Spool file is not an exclusively owned private file")
        return info

    @contextmanager
    def _verified_stream(self, reference):
        self._check()
        before = self._file_info(reference.name)
        if before.st_size != reference.size:
            raise SafetyViolation("Spool file size changed")
        descriptor = os.open(reference.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=self._directory)
        try:
            if _signature(os.fstat(descriptor)) != _signature(before):
                raise SafetyViolation("Spool file changed while opening")
            with io.FileIO(descriptor, "rb", closefd=False) as raw:
                with io.BufferedReader(raw, buffer_size=65536) as stream:
                    fingerprint = fingerprint_reader(stream.read, reference.size)
                    if fingerprint.sha256 != reference.sha256:
                        raise SafetyViolation("Spool file digest changed")
                    self._check_file(reference, descriptor, before)
                    stream.seek(0)
                    yield stream, before
                    self._check_file(reference, descriptor, before)
        finally:
            os.close(descriptor)

    def _check_file(self, reference, descriptor, before):
        self._check()
        if (_signature(os.fstat(descriptor)) != _signature(before)
                or _signature(self._file_info(reference.name)) != _signature(before)):
            raise SafetyViolation("Spool file changed while reading")

    def _write(self, lines, *, name=None):
        return complete_steps(self._write_steps(lines, name=name))

    def _write_steps(self, lines, *, name=None, operation=None):
        self._check()
        if name is None:
            name = "run-%016x.jsonl" % self._counter
            self._counter += 1
        if operation is None:
            operation = {"phase": "manifest" if name == "spool.json" else "batch_run"}
        self._operation = operation
        operation["output"] = {"name": name, "bytes_written": 0, "records_written": 0, "sealed": False}
        digest, size, records, longest = sha256(), 0, 0, 0
        descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=self._directory)
        try:
            for line in lines:
                self._check()
                with memoryview(line) as view:
                    offset = 0
                    while offset < len(view):
                        count = os.write(descriptor, view[offset:offset + 65536])
                        if type(count) is not int or not 0 < count <= min(65536, len(view) - offset):
                            raise SafetyViolation("Spool write made invalid progress")
                        offset += count
                digest.update(line)
                size += len(line)
                records += 1
                longest = max(longest, len(line))
                operation["output"].update(bytes_written=size, records_written=records)
                yield None  # One whole record written; descriptor remains owned.
            os.fsync(descriptor)
            written = os.fstat(descriptor)
            if (_signature(written) != _signature(self._file_info(name))
                    or written.st_size != size):
                raise SafetyViolation("Spool file changed while writing")
        finally:
            os.close(descriptor)
        os.fsync(self._directory)
        reference = _Run(name, size, digest.hexdigest(), records, longest)
        with self._verified_stream(reference):
            pass
        operation["output"].update(sealed=True, reference=reference.as_dict())
        yield None  # Durable run verified; not a work-v1 checkpoint.
        return reference

    def _records(self, reference):
        with self._verified_stream(reference) as (stream, before):
            for _ in range(reference.records):
                self._check_file(reference, stream.fileno(), before)
                line = stream.readline(reference.max_line_bytes + 1)
                if not line.endswith(b"\n") or len(line) > reference.max_line_bytes:
                    raise SafetyViolation("Spool record boundary changed")
                value = json.loads(line)
                # Only fully hash-verified, internally produced records are parsed.
                item = self._decode(value[self._record_field])
                self._check_file(reference, stream.fileno(), before)
                yield (self._sort_key(item), value["sequence"]), line
            if stream.read(1):
                raise SafetyViolation("Spool record count changed")

    def _merge(self, first, second):
        return complete_steps(self._merge_steps(first, second))

    def _merge_steps(self, first, second):
        left, right = self._records(first), self._records(second)
        operation = {"phase": "merge", "inputs": [
            {"reference": run.as_dict(), "record_index": 0, "byte_offset": 0}
            for run in (first, second)]}
        def lines():
            a, b = next(left, None), next(right, None)
            while a is not None or b is not None:
                if b is None or (a is not None and a[0] <= b[0]):
                    operation["inputs"][0]["record_index"] += 1
                    operation["inputs"][0]["byte_offset"] += len(a[1])
                    yield a[1]
                    a = next(left, None)
                else:
                    operation["inputs"][1]["record_index"] += 1
                    operation["inputs"][1]["byte_offset"] += len(b[1])
                    yield b[1]
                    b = next(right, None)
        try:
            return (yield from self._write_steps(lines(), operation=operation))
        finally:
            left.close()
            right.close()

    @property
    def manifest(self):
        if self._manifest is None:
            raise ValueError("Spool construction is incomplete")
        return json.loads(self._manifest)

    def cursor(self):
        if self._final is None:
            raise ValueError("Spool construction is incomplete")
        cursor = DiagnosticCursor(self)
        try:
            self._cursors.add(cursor)
        except BaseException:
            cursor.close()
            raise
        return cursor

    def close(self):
        for cursor in tuple(self._cursors):
            cursor.close()
        for descriptor in reversed(self._fds):
            os.close(descriptor)
        self._fds.clear()

    def __enter__(self):
        self._check()
        return self

    def __exit__(self, *unused):
        self.close()


class DiagnosticSort:
    """Live bounded work units for input, sorted runs, merging and publication.

    Cursor snapshots describe actual owned work; they cannot be imported as
    checkpoints. A pause retains open descriptors and the original iterator.
    """

    def __init__(self, root, diagnostics, *, protected_roots, batch_bytes=65536,
                 _spool_type=DiagnosticSpool):
        _positive(batch_bytes)
        self._spool = _spool_type(root, protected_roots)
        try:
            self._batch_bytes = batch_bytes
            self._source = diagnostics
            self._accepted = self._buffered = self._units = 0
            self._pending_input = None
            self._levels = []
            self._source_finished = self._complete = self._failed = self._closed = False
            self._steps = self._construct_steps()
        except BaseException:
            self._spool.close()
            raise

    @property
    def state(self):
        value = dict(format="spool-sort-cursor-v1", spool_format=self._spool._format,
                     phase="complete" if self._complete else "failed" if self._failed else
                     "cancelled" if self._closed else
                     (self._spool._operation or {}).get("phase", "input"),
                     units_completed=self._units, accepted_records=self._accepted,
                     buffered_records=self._buffered, pending_input_sequence=self._pending_input,
                     source_finished=self._source_finished, complete=self._complete,
                     durable_checkpoint=False,
                     pending_runs=[run.as_dict() for run in self._levels if run is not None],
                     operation=self._spool._operation)
        return json.loads(json.dumps(value))

    @property
    def result(self):
        if not self._complete:
            raise ValueError("Sort is incomplete")
        self._spool._check()
        return self._spool

    @property
    def batch_bytes(self):
        return self._batch_bytes

    def reduce_batch_bytes(self, maximum):
        """Reduce future batching without dropping buffered or pending input.

        An in-flight flush/merge keeps its cursor. A previously buffered batch
        is flushed by the existing driver; this does not claim to free it now.
        """
        _positive(maximum)
        if self._closed:
            raise ValueError("Sort is closed")
        if not self._complete:
            self._batch_bytes = min(self._batch_bytes, maximum)
        return self._batch_bytes

    def advance(self, units=1):
        _positive(units)
        if self._closed:
            raise ValueError("Sort is closed")
        try:
            self._spool._check()
            for _ in range(units):
                if self._complete:
                    break
                try:
                    next(self._steps)
                except StopIteration:
                    self._complete = True
                self._units += 1
            return self.state
        except BaseException:
            self._failed = True
            self._complete = False
            self.close()
            raise

    def close(self):
        if not self._closed:
            self._closed = True
            try:
                self._steps.close()
            finally:
                self._spool.close()

    def __enter__(self):
        if self._closed:
            raise ValueError("Sort is closed")
        return self

    def __exit__(self, *unused):
        self.close()

    def _construct_steps(self):
        spool = self._spool
        levels, batch = self._levels, []
        batch_size = total = batches = peak_bytes = peak_records = 0
        input_digest = sha256()

        def flush():
            nonlocal batch_size, batches
            batch.sort(key=lambda item: item[0])
            run = yield from spool._write_steps(item[1] for item in batch)
            batch.clear()
            self._buffered = batch_size = 0
            batches += 1
            level = 0
            while level < len(levels) and levels[level] is not None:
                previous = levels[level]
                levels[level] = None
                run = yield from spool._merge_steps(previous, run)
                level += 1
            if level == len(levels):
                levels.append(run)
            else:
                levels[level] = run

        for item in self._source:
            key = spool._sort_key(item)
            line = _json_line({"sequence": total, spool._record_field: item.as_dict()})
            self._pending_input = total
            if batch and batch_size + len(line) > self._batch_bytes:
                yield from flush()
            batch.append(((key, total), line))
            batch_size += len(line)
            input_digest.update(line)
            total += 1
            self._accepted, self._buffered, self._pending_input = total, len(batch), None
            spool._operation = {"phase": "input"}
            peak_bytes, peak_records = max(peak_bytes, batch_size), max(peak_records, len(batch))
            yield None
            if batch_size >= self._batch_bytes:
                yield from flush()
        self._source_finished = True
        if batch:
            yield from flush()
        final = None
        while levels:
            run = levels.pop()
            if run is not None:
                final = run if final is None else (yield from spool._merge_steps(final, run))
        if final is None:
            final = yield from spool._write_steps(())
        if final.records != total:
            raise SafetyViolation("Spool lost records during sorting")
        manifest = dict(format=spool._format, ordering=spool._ordering,
                        state="sorted", record_count=total, input_sha256=input_digest.hexdigest(),
                        result=final.as_dict(), durable_checkpoint=False,
                        batch=dict(target_bytes=self._batch_bytes, count=batches,
                                   peak_encoded_bytes=peak_bytes, peak_records=peak_records))
        spool._manifest = _json_line(manifest)
        spool._manifest_ref = yield from spool._write_steps((spool._manifest,), name="spool.json")
        spool._final = final


def create_diagnostic_spool(root, diagnostics, *, protected_roots, batch_bytes=65536):
    """Finish the same resumable sort synchronously and transfer spool ownership.

    The batch goal bounds encoded records, not total Python RSS. One diagnostic
    may exceed that soft goal and is processed alone. Pairwise binary-carry
    merges retain only two current records and O(log(number of runs)) references.
    Source binding, all protected roots and spool lifetime belong to the caller.
    """
    task = DiagnosticSort(root, diagnostics, protected_roots=protected_roots, batch_bytes=batch_bytes)
    while not task.advance(256)["complete"]:
        pass
    return task.result
