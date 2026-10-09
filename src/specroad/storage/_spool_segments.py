"""Shared immutable run references and guarded forward-only result delivery.

The owner supplies its existing verified storage capability and typed record
codec. These helpers confer no path, write or detached-checkpoint authority.
"""
from dataclasses import dataclass
import json

from ..security.errors import SafetyViolation


def _positive(value):
    if type(value) is not int or value < 1:
        raise ValueError("A positive integer is required")


@dataclass(frozen=True)
class RunSegment:
    name: str
    size: int
    sha256: str
    records: int
    max_line_bytes: int

    def as_dict(self):
        return dict(name=self.name, size=self.size, sha256=self.sha256,
                    records=self.records, max_line_bytes=self.max_line_bytes)


class RunCursor:
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
        return dict(format=self._spool._cursor_format, phase="delivery",
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
                result.append(spool._decode(json.loads(line)[spool._record_field]))
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
