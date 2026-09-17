"""Passive relation field checks; no record storage, graph or mutation code."""

import re
from ..model.artifact_types import artifact_types
from ..model.audit_values import Actor, UtcTimestamp
from ..model.configuration import _json_values
from ..model.errors import ModelError
from ..model.metadata import validate_extensions
from ..model.paths import artifact_path
from ..model.relation_identity import relation_identity
from .relation_types import require_relation_type

KEY_FIELDS = ("relation_id", "id_scheme", "type", "target")
REQUIRED_FIELDS = KEY_FIELDS + ("external_identities", "extensions")
OPTIONAL_FIELDS = ("rationale", "created_at", "created_by", "position")
IMPORT_FIELDS = ("mapping_id", "last_imported_projection_sha256",
                 "last_source_projection_sha256", "last_source_payload_sha256", "imported_at")
EXTERNAL_KEY = ("source_system", "source_document", "external_id")


def _json_data(value):
    try:
        _json_values(value)
    except RecursionError as error:
        raise ModelError("unsupported_json_nesting") from error


def _text(value, pointer):
    if type(value) is not str or not value.strip():
        raise ModelError("nonempty_string_required", pointer=pointer)


def _reference(value):
    if type(value) is not str:
        raise ModelError("invalid_artifact_reference", pointer="/target")
    pieces = value.split("-")
    if len(pieces) != 3:
        raise ModelError("invalid_artifact_reference", pointer="/target")
    kind = next((item.artifact_type for item in artifact_types() if item.prefix == pieces[1]), None)
    if kind is None:
        raise ModelError("invalid_artifact_reference", pointer="/target")
    try:
        artifact_path(kind, value, pieces[0])
    except ModelError as error:
        raise ModelError("invalid_artifact_reference", pointer="/target") from error


def _external_identities(values):
    if type(values) is not list:
        raise ModelError("external_identity_array_required", pointer="/external_identities")
    seen = set()
    allowed = set(EXTERNAL_KEY + IMPORT_FIELDS + ("external_revision", "extensions"))
    for index, value in enumerate(values):
        pointer = "/external_identities/" + str(index)
        if type(value) is not dict:
            raise ModelError("external_identity_object_required", pointer=pointer)
        if set(value) - allowed:
            raise ModelError("unknown_external_identity_field", pointer=pointer)
        for name in EXTERNAL_KEY:
            _text(value.get(name), pointer + "/" + name)
        key = tuple(value[name] for name in EXTERNAL_KEY)
        if key in seen:
            raise ModelError("duplicate_external_identity", pointer=pointer)
        seen.add(key)
        if "external_revision" in value and type(value["external_revision"]) is not str:
            raise ModelError("external_revision_string_required", pointer=pointer + "/external_revision")
        if any(name in value for name in IMPORT_FIELDS):
            if not set(IMPORT_FIELDS) <= value.keys():
                raise ModelError("incomplete_import_binding", pointer=pointer)
            _text(value["mapping_id"], pointer + "/mapping_id")
            for name in IMPORT_FIELDS[1:4]:
                if type(value[name]) is not str or re.fullmatch(r"[0-9a-f]{64}", value[name]) is None:
                    raise ModelError("invalid_sha256", pointer=pointer + "/" + name)
            try:
                UtcTimestamp(value["imported_at"])
            except ModelError as error:
                error.pointer = pointer + "/imported_at"
                raise
        if "extensions" in value:
            validate_extensions(value["extensions"], pointer=pointer + "/extensions")


def _validate_fields(value):
    if type(value) is not dict:
        raise ModelError("relation_object_required")
    _json_data(value)
    for name in REQUIRED_FIELDS:
        if name not in value:
            raise ModelError("missing_relation_field", pointer="/" + name)
    if set(value) - set(REQUIRED_FIELDS + OPTIONAL_FIELDS):
        raise ModelError("unknown_relation_field")
    relation_identity(value)
    require_relation_type(value["type"])
    _reference(value["target"])
    validate_extensions(value["extensions"])
    _external_identities(value["external_identities"])
    if "rationale" in value and type(value["rationale"]) is not str:
        raise ModelError("rationale_string_required", pointer="/rationale")
    if "created_at" in value:
        try:
            UtcTimestamp(value["created_at"])
        except ModelError as error:
            error.pointer = "/created_at"
            raise
    if "created_by" in value:
        actor = value["created_by"]
        if type(actor) is not dict or set(actor) != {"actor_type", "actor_id"}:
            raise ModelError("invalid_actor", pointer="/created_by")
        try:
            Actor(actor["actor_type"], actor["actor_id"])
        except ModelError as error:
            error.pointer = "/created_by" + error.pointer
            raise
    if value["type"] == "contains":
        position = value.get("position")
        # Use the same JSON-integer semantics as the existing field validators.
        if type(position) not in (int, float) or position < 0 or int(position) != position:
            raise ModelError("invalid_relation_position", pointer="/position")
    elif "position" in value:
        raise ModelError("position_only_for_contains", pointer="/position")


