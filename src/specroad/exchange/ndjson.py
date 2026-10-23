"""Passive native NDJSON v1 codec over a complete, caller-owned byte source.

Iterators expose only partial observations until exhausted. They neither open
files nor publish output; whole-stream helpers return only after every record
has passed. Transfer chunks and persistent continuation belong to the caller's
later streaming/work integration, not to a guessed end of input here.
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
            try:
                if b"\r" in record:
                    raise ModelError("ndjson_raw_cr")
                value = parse_json_object(record)
                _validate_envelope(value)
            except ModelError as error:
                raise NDJSONError(error.reason, pointer=error.pointer, line=line,
                                  column=error.column, position=error.position,
                                  highest_supported=error.highest_supported) from None
            yield value
        start, line = end + 1, line + 1


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
