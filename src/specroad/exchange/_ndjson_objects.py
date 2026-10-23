"""Closed native NDJSON envelopes; no line framing or project mapping/IO."""
from ..changes.values import ChangePlan
from ..model.canonical import canonical_json_bytes
from ..model.domain_schemas import DOMAIN_TYPES, validate_domain_fields
from ..model.record_schemas import RECORD_TYPES, validate_record_fields
from ..model.errors import ModelError


def validate_envelope(value):
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
