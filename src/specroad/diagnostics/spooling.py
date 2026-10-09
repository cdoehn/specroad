"""Explicit external diagnostic sorting in an exclusively owned private directory.

This first backend owns immutable JSONL runs and a live delivery cursor. It does
not implement a work-v1 checkpoint, implicit project writes or process resume.
Native I/O/allocation errors propagate; partial owned files are never removed.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import stat

from ..security.errors import SafetyViolation
from ..security.paths import ProjectBoundary, _HAS_SAFE_OPEN, _identity, _parts, _regular, _signature
from ..storage.byte_binding import fingerprint_reader
from .ordering import diagnostic_key
from .values import Diagnostic


def _json_line(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")


def _positive(value):
    if type(value) is not int or value < 1:
        raise ValueError("A positive integer is required")


@dataclass(frozen=True)
class _Run:
    name: str
    size: int
    sha256: str
    records: int
    max_line_bytes: int

    def as_dict(self):
        return dict(name=self.name, size=self.size, sha256=self.sha256,
                    records=self.records, max_line_bytes=self.max_line_bytes)


class DiagnosticSpool:
    """An owned spool capability; construct through create_diagnostic_spool.

    Closing releases handles only. Callers retain the directory and all runs.
    The returned manifest is a detached description, never write authority.
    """

    def __init__(self, root, protected_roots):
        self._fds = []
        self._entries = []
        self._cursors = set()
        self._counter = 0
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
            parent = os.open("/", flags)
            self._fds.append(parent)
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

    def _open_directory(self, parent, name, flags):
        before = os.stat(name, dir_fd=parent, follow_symlinks=False)
        _regular(before, directory=True)
        opened = os.open(name, flags, dir_fd=parent)
        self._fds.append(opened)
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
        self._check()
        if name is None:
            name = "run-%016x.jsonl" % self._counter
            self._counter += 1
        descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=self._directory)
        digest, size, records, longest = sha256(), 0, 0, 0
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
        return reference

    def _records(self, reference):
        with self._verified_stream(reference) as (stream, _):
            for _ in range(reference.records):
                line = stream.readline(reference.max_line_bytes + 1)
                if not line.endswith(b"\n") or len(line) > reference.max_line_bytes:
                    raise SafetyViolation("Spool record boundary changed")
                value = json.loads(line)
                # Only fully hash-verified, internally produced records are parsed.
                diagnostic = Diagnostic.from_dict(value["diagnostic"])
                yield (diagnostic_key(diagnostic), value["sequence"]), line
            if stream.read(1):
                raise SafetyViolation("Spool record count changed")

    def _merge(self, first, second):
        left, right = self._records(first), self._records(second)
        def lines():
            a, b = next(left, None), next(right, None)
            while a is not None or b is not None:
                if b is None or (a is not None and a[0] <= b[0]):
                    yield a[1]
                    a = next(left, None)
                else:
                    yield b[1]
                    b = next(right, None)
        try:
            return self._write(lines())
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
        self._cursors.add(cursor)
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


class DiagnosticCursor:
    """Forward-only pages from one verified run; no detached state import yet."""

    def __init__(self, spool):
        self._spool = spool
        self._index = self._offset = 0
        self._complete = self._closed = False
        with spool._verified_stream(spool._manifest_ref):
            pass
        self._guard = spool._verified_stream(spool._final)
        self._stream, self._before = self._guard.__enter__()

    @property
    def state(self):
        return dict(format="diagnostic-cursor-v1", phase="delivery",
                    spool_sha256=self._spool._manifest_ref.sha256,
                    record_index=self._index, byte_offset=self._offset,
                    complete=self._complete, durable_checkpoint=False)

    def read_page(self, count):
        _positive(count)
        if self._closed:
            raise ValueError("Cursor is closed")
        if self._complete:
            return []
        spool, reference = self._spool, self._spool._final
        try:
            spool._check_file(reference, self._stream.fileno(), self._before)
            result = []
            offset = self._offset
            for _ in range(min(count, reference.records - self._index)):
                line = self._stream.readline(reference.max_line_bytes + 1)
                if not line.endswith(b"\n") or len(line) > reference.max_line_bytes:
                    raise SafetyViolation("Spool record boundary changed")
                result.append(Diagnostic.from_dict(json.loads(line)["diagnostic"]))
                offset += len(line)
            complete = self._index + len(result) == reference.records
            if complete and (offset != reference.size or self._stream.read(1)):
                raise SafetyViolation("Spool delivery did not consume the complete run")
            spool._check_file(reference, self._stream.fileno(), self._before)
            self._index += len(result)
            self._offset, self._complete = offset, complete
            return result
        except BaseException:
            self.close()
            raise

    def close(self):
        if not self._closed:
            self._closed = True
            self._spool._cursors.discard(self)
            # Closing must release descriptors even after integrity failure.
            self._guard.gen.close()

    def __enter__(self):
        if self._closed:
            raise ValueError("Cursor is closed")
        return self

    def __exit__(self, *unused):
        self.close()


def create_diagnostic_spool(root, diagnostics, *, protected_roots, batch_bytes=65536):
    """Consume diagnostics once, retaining every record in deterministic order.

    The batch goal bounds encoded records, not total Python RSS. One diagnostic
    may exceed that soft goal and is processed alone. Pairwise binary-carry
    merges retain only two current records and O(log(number of runs)) references.
    Source binding, all protected roots and spool lifetime belong to the caller.
    """
    _positive(batch_bytes)
    spool = DiagnosticSpool(root, protected_roots)
    try:
        levels, batch = [], []
        batch_size = total = batches = peak_bytes = peak_records = 0
        input_digest = sha256()

        def flush():
            nonlocal batch_size, batches
            batch.sort(key=lambda item: item[0])
            run = spool._write(item[1] for item in batch)
            batch.clear()
            batch_size = 0
            batches += 1
            level = 0
            while level < len(levels) and levels[level] is not None:
                run = spool._merge(levels[level], run)
                levels[level] = None
                level += 1
            if level == len(levels):
                levels.append(run)
            else:
                levels[level] = run

        for diagnostic in diagnostics:
            key = diagnostic_key(diagnostic)  # exact owned Diagnostic required
            line = _json_line(dict(sequence=total, diagnostic=diagnostic.as_dict()))
            if batch and batch_size + len(line) > batch_bytes:
                flush()
            batch.append(((key, total), line))
            batch_size += len(line)
            input_digest.update(line)
            total += 1
            peak_bytes, peak_records = max(peak_bytes, batch_size), max(peak_records, len(batch))
            if batch_size >= batch_bytes:
                flush()
        if batch:
            flush()
        final = None
        for run in levels:
            if run is not None:
                final = run if final is None else spool._merge(final, run)
        if final is None:
            final = spool._write(())
        if final.records != total:
            raise SafetyViolation("Spool lost records during sorting")
        manifest = dict(format="diagnostic-spool-v1", ordering="diagnostic-key-v1",
                        state="sorted", record_count=total, input_sha256=input_digest.hexdigest(),
                        result=final.as_dict(), durable_checkpoint=False,
                        batch=dict(target_bytes=batch_bytes, count=batches,
                                   peak_encoded_bytes=peak_bytes, peak_records=peak_records))
        spool._manifest = _json_line(manifest)
        spool._manifest_ref = spool._write((spool._manifest,), name="spool.json")
        spool._final = final
        return spool
    except BaseException:
        spool.close()
        raise
