"""Passive native NDJSON v1 codec over caller-owned bytes or transfer blocks.

Iterators expose only partial observations until exhausted. They neither open
files nor publish output; whole-stream helpers return only after every record
has passed. Incremental readers require explicit EOF. Checkpoints are inert
codec data; the caller owns durable storage, input snapshots and output staging.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..changes.values import ChangePlan
from ..model.canonical import canonical_json_bytes
from ..model.domain_schemas import DOMAIN_TYPES, validate_domain_fields
from ..model.record_schemas import RECORD_TYPES, validate_record_fields
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object


class NDJSONError(ModelError):
    """A local format/field failure, with no copied payload values."""
    exit_code = 3

    def diagnostic(self):
        return {**super().diagnostic(), "exit_code": self.exit_code}


class NDJSONResumeConflict(NDJSONError):
    """Changed source/checkpoint binding, retaining the conflict exit class."""
    exit_code = 6


def _validate_envelope(value):
    if set(value) != {"format_version", "object_kind", "object"}:
        raise ModelError("ndjson_envelope_fields")
    if value["format_version"] != "1.0.0":
        raise ModelError("ndjson_unsupported_version", pointer="/format_version")
    if value["object_kind"] not in ("artifact", "change_plan"):
        raise ModelError("ndjson_object_kind", pointer="/object_kind")
    payload = value["object"]
    if type(payload) is not dict:
        raise ModelError("ndjson_payload_object_required", pointer="/object")
    try:
        if value["object_kind"] == "change_plan":
            # Verify the existing inner hash; never prepare or repair a plan.
            ChangePlan(canonical_json_bytes(payload))
        elif payload.get("artifact_type") in DOMAIN_TYPES:
            validate_domain_fields(payload)
        elif payload.get("artifact_type") in RECORD_TYPES:
            validate_record_fields(payload)
        else:
            raise ModelError("unsupported_artifact_type", pointer="/artifact_type")
    except ModelError as error:
        raise ModelError(error.reason, pointer="/object" + error.pointer,
                         highest_supported=error.highest_supported) from None


def _decode_record(record, line):
    try:
        if b"\r" in record:
            raise ModelError("ndjson_raw_cr")
        value = parse_json_object(record)
        _validate_envelope(value)
    except ModelError as error:
        raise NDJSONError(error.reason, pointer=error.pointer, line=line,
                          column=error.column, position=error.position,
                          highest_supported=error.highest_supported) from None
    return value


def iter_decode_ndjson(raw):
    """Yield detached envelopes in order from complete bytes, not transfer blocks.

    A yielded prefix is not a whole-stream success or a write authorization.
    Physical lines are counted even when empty; no invalid line is skipped.
    """
    if type(raw) is not bytes:
        raise NDJSONError("bytes_required")
    start, line = 0, 1
    while start < len(raw):
        end = raw.find(b"\n", start)
        if end < 0:
            end = len(raw)  # The supplied complete byte source is at actual EOF.
        record = raw[start:end]
        if record:
            yield _decode_record(record, line)
        start, line = end + 1, line + 1


class NDJSONDecoder:
    """Incremental, passive reader; feed results are always partial observations.

    Only the unfinished line survives between feed calls. A feed returns the
    records in that caller-sized block, so callers can bound their working set
    without a total-byte/object cutoff. No decoded history is accumulated.
    Keep original source bytes separately for provenance or durable resume.
    A failed reader cannot be reused to skip a bad line or claim completion.
    """

    def __init__(self):
        self._pending = bytearray()
        self._digest = sha256()
        self._offset = 0
        self._line = 1
        self._count = 0
        self._state = "running"
        self._bound_source = None

    def _running(self):
        if self._state != "running":
            raise NDJSONError("ndjson_reader_not_running", line=self._line)

    def feed(self, block):
        """Consume bytes, including empty blocks, without inferring EOF.

        Nothing from this call is returned if any complete line in it fails.
        Previously returned objects remain partial, never a complete import.
        """
        self._running()
        try:
            if type(block) is not bytes:
                raise NDJSONError("bytes_required", line=self._line)
            if (self._bound_source is not None
                    and block != self._bound_source[self._offset:self._offset + len(block)]):
                raise NDJSONResumeConflict("ndjson_source_changed", line=self._line)
            self._digest.update(block)
            self._offset += len(block)
            records, start = [], 0
            while start < len(block):
                end = block.find(b"\n", start)
                if end < 0:
                    self._pending.extend(block[start:])
                    break
                self._pending.extend(block[start:end])
                if self._pending:
                    records.append(_decode_record(bytes(self._pending), self._line))
                    self._count += 1
                self._pending.clear()
                self._line += 1
                start = end + 1
            return tuple(records)
        except BaseException:
            # Resource/security/host failures retain their original classes.
            # A partially advanced reader is nevertheless never reusable.
            self._state = "failed"
            raise

    def finish(self):
        """Declare actual EOF; a partial last object is an error, not a pause."""
        self._running()
        try:
            if self._bound_source is not None and self._offset != len(self._bound_source):
                raise NDJSONResumeConflict("ndjson_source_incomplete", line=self._line)
            records = ()
            if self._pending:
                records = (_decode_record(bytes(self._pending), self._line),)
                self._count += 1
                self._pending.clear()
            self._state = "complete"
            return records
        except BaseException:
            self._state = "failed"
            raise

    def observation(self):
        complete = self._state == "complete"
        return {"format_version": "1.0.0", "complete": complete,
                "failed": self._state == "failed", "bytes_received": self._offset,
                "object_count": self._count, "next_line": self._line,
                "consumed_sha256": self._digest.hexdigest(),
                "source_sha256": self._digest.hexdigest() if complete else None,
                "validation_scope": "ndjson_native_fields_only",
                "write_authorized": False, "execution_ready": False}

    def checkpoint(self, source):
        """Bind a running cursor to an explicit, complete immutable snapshot.

        Returns data only, not a Work manifest or durable-write receipt. Save
        this data, its independently trusted SHA-256 and the original source
        together with confirmed outputs using the host's storage mechanisms.
        A checkpoint never substitutes for finish or authorizes publication.
        """
        self._running()
        if type(source) is not bytes:
            raise NDJSONError("bytes_required", line=self._line)
        if (self._offset > len(source)
                or sha256(memoryview(source)[:self._offset]).digest() != self._digest.digest()
                or (self._bound_source is not None and source != self._bound_source)):
            raise NDJSONResumeConflict("ndjson_source_changed", line=self._line)
        raw = canonical_json_bytes({
            "format_version": "ndjson-cursor-v1", "source_sha256": sha256(source).hexdigest(),
            "source_size": len(source), "byte_offset": self._offset,
            "next_line": self._line, "object_count": self._count,
            "pending_hex": self._pending.hex()})
        self._bound_source = source
        return raw


def resume_ndjson(source, checkpoint, *, checkpoint_sha256):
    """Resume inert saved bytes against a separately retained checkpoint hash.

    Source identity and cursor geometry are checked before any new output.
    The consumed prefix is revalidated in bounded blocks, discarding its
    objects; an untrusted cursor cannot hide an invalid earlier line. Pending
    bytes are not parsed as a final line. No saved object is emitted again.
    This is a pure codec operation, not a portable Work/CLI integration.
    """
    if type(source) is not bytes or type(checkpoint) is not bytes:
        raise NDJSONError("bytes_required")
    if (type(checkpoint_sha256) is not str
            or sha256(checkpoint).hexdigest() != checkpoint_sha256):
        raise NDJSONResumeConflict("ndjson_checkpoint_changed")
    try:
        value = parse_json_object(checkpoint)
        fields = {"format_version", "source_sha256", "source_size", "byte_offset",
                  "next_line", "object_count", "pending_hex"}
        if (set(value) != fields or value["format_version"] != "ndjson-cursor-v1"
                or any(type(value[key]) is not int or value[key] < 0
                       for key in ("source_size", "byte_offset", "next_line", "object_count"))
                or value["next_line"] < 1 or value["byte_offset"] > value["source_size"]
                or type(value["pending_hex"]) is not str
                or type(value["source_sha256"]) is not str
                or len(value["source_sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in value["source_sha256"])):
            raise ModelError("ndjson_invalid_checkpoint")
    except ModelError:
        raise NDJSONError("ndjson_invalid_checkpoint") from None
    if len(source) != value["source_size"] or sha256(source).hexdigest() != value["source_sha256"]:
        raise NDJSONResumeConflict("ndjson_source_changed", line=value["next_line"])
    reader = NDJSONDecoder()
    for start in range(0, value["byte_offset"], 65536):
        reader.feed(source[start:min(start + 65536, value["byte_offset"])])
    if (reader._line != value["next_line"] or reader._count != value["object_count"]
            or reader._pending.hex() != value["pending_hex"]):
        raise NDJSONError("ndjson_invalid_checkpoint", line=reader._line)
    reader._bound_source = source
    return reader


def iter_decode_ndjson_chunks(blocks):
    """Decode an iterable whose exhaustion explicitly means actual EOF.

    For a temporarily paused producer use NDJSONDecoder.feed/finish instead.
    Iteration prefixes are partial. Input/host exceptions are not EOF and are
    not converted to format errors or successful completion.
    """
    reader = NDJSONDecoder()
    for block in blocks:
        yield from reader.feed(block)
    yield from reader.finish()


def iter_encode_ndjson(objects):
    """Yield canonical envelope + LF records; the prefix is not complete output.

    The caller supplies explicit envelopes, including both discriminators, and
    owns the iterable. No kind inference, sorting, deduplication or publication.
    """
    if isinstance(objects, (str, bytes, bytearray, dict)):
        raise NDJSONError("ndjson_object_sequence_required")
    try:
        iterator = iter(objects)
    except TypeError:
        raise NDJSONError("ndjson_object_sequence_required") from None
    for line, value in enumerate(iterator, 1):
        try:
            encoded = canonical_json_bytes(value)
            owned = parse_json_object(encoded)
            _validate_envelope(owned)
        except ModelError as error:
            raise NDJSONError(error.reason, pointer=error.pointer, line=line,
                              highest_supported=error.highest_supported) from None
        yield encoded + b"\n"


def encode_ndjson(objects):
    """Return complete canonical bytes only after all envelopes validate."""
    return b"".join(iter_encode_ndjson(objects))


@dataclass(frozen=True, init=False)
class NDJSONObservation:
    """Complete passive transport observation, never an import/Apply ticket."""
    source_bytes: bytes
    _records: tuple

    def __init__(self, raw):
        records = tuple(canonical_json_bytes(value) for value in iter_decode_ndjson(raw))
        object.__setattr__(self, "source_bytes", raw)
        object.__setattr__(self, "_records", records)

    @property
    def objects(self):
        return [parse_json_object(record) for record in self._records]

    @property
    def source_sha256(self):
        return sha256(self.source_bytes).hexdigest()

    @property
    def write_authorized(self):
        return False

    @property
    def execution_ready(self):
        return False

    def observation(self):
        return {"format_version": "1.0.0", "source_sha256": self.source_sha256,
                "object_count": len(self._records), "complete": True,
                "validation_scope": "ndjson_native_fields_only",
                "write_authorized": False, "execution_ready": False}


def decode_ndjson(raw):
    """Validate the entire byte source before returning a complete observation."""
    return NDJSONObservation(raw)
