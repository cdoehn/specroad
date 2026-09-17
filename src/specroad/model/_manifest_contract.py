"""Pure descriptor/boundary validation for model manifest inputs.

No filesystem, runtime lookup, scope expansion or effective-policy resolution.
The assembler and future integrations reuse these same guarded values.
"""

import json
import re

from .canonical import canonical_json_bytes as canonical_json
from .errors import ModelError


def _text(value):
    if type(value) is not str or not value.strip() or "\0" in value:
        raise ModelError("invalid_manifest_identity")
    try:
        value.encode("utf-8")
    except UnicodeError as error:
        raise ModelError("invalid_unicode") from error
    return value


def _hash(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ModelError("invalid_manifest_hash")
    return value


def _descriptor(value):
    """Initial descriptor shapes only; resolving seeds/closure is a later service."""
    fields = {"scope_version", "scope_kind", "selector", "configuration_id",
              "closure_profile", "boundary_policy"}
    if (type(value) is not dict or set(value) != fields
            or value["scope_version"] != "scope-v1"
            or value["closure_profile"] != "core-closure-v1"
            or value["boundary_policy"] not in ("closed", "partial")):
        raise ModelError("invalid_scope_descriptor")
    kind, selector = value["scope_kind"], value["selector"]
    if type(kind) is not str:
        raise ModelError("invalid_scope_descriptor")
    if value["configuration_id"] is not None:
        raise ModelError("configured_scope_not_supported")
    if type(selector) is not dict:
        raise ModelError("invalid_scope_selector")
    if kind in ("project", "specification"):
        if selector:
            raise ModelError("invalid_scope_selector")
    elif kind == "explicit":
        if set(selector) != {"artifact_ids", "resource_ids"}:
            raise ModelError("invalid_scope_selector")
        for values in selector.values():
            if type(values) is not list:
                raise ModelError("invalid_scope_selector")
            for name in values:
                _text(name)
            if values != sorted(set(values), key=lambda s: s.encode("utf-8")):
                raise ModelError("noncanonical_scope_selector")
    else:
        raise ModelError("scope_kind_not_supported")
    return json.loads(canonical_json(value))


def _boundaries(values, descriptor, artifacts, configuration):
    """Validate explicit boundary records; do not fabricate target provenance."""
    if isinstance(values, (str, bytes, dict)):
        raise ModelError("boundary_sequence_required")
    try:
        values = tuple(values)
    except TypeError as error:
        raise ModelError("boundary_sequence_required") from error
    if values and descriptor["boundary_policy"] != "partial":
        raise ModelError("boundary_in_closed_scope")
    included = {item["id"] for item in artifacts}
    result, seen = [], set()
    required = {"source_id", "relation_type", "target_id", "target_type", "reason", "origin_target_sha256"}
    from .paths import artifact_path
    from .relation_values import _relation_id
    for item in values:
        if type(item) is not dict or not required <= item.keys() or item.keys() - required - {"relation_id"}:
            raise ModelError("invalid_boundary_reference")
        for name in ("source_id", "target_id", "target_type", "reason"):
            _text(item[name])
        if item["relation_type"] not in ("conflicts_with", "duplicates"):
            raise ModelError("strong_relation_cannot_be_boundary")
        relation = item.get("relation_id")
        if "relation_id" in item:
            _relation_id(relation)
        _hash(item["origin_target_sha256"])
        artifact_path(item["target_type"], item["target_id"], configuration.id_prefix)
        if item["source_id"] not in included or item["target_id"] in included:
            raise ModelError("boundary_membership_mismatch")
        key = (item["source_id"], relation or "", item["target_id"])
        if key in seen:
            raise ModelError("duplicate_boundary_reference")
        seen.add(key)
        result.append(json.loads(canonical_json(item)))
    return sorted(result, key=lambda item: tuple(item.get(key, "").encode("utf-8")
                  for key in ("source_id", "relation_id", "target_id")))


