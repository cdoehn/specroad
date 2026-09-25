"""Pure Change Plan parsing, binding and operation routing, without writes."""
from dataclasses import dataclass
import re
from ..model._schema import validate_builtin
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.artifact_types import artifact_types
from ..model.identity_values import ArtifactIdentity, artifact_identity
from ..model.audit_values import Actor, UtcTimestamp
from ..model.paths import project_path
from ..model.attachments import AttachmentDescriptor
from ..model.record_contracts import RECORD_TYPES, SPECIAL_STATES
from ..model.record_schemas import validate_record_fields, require_generic_mutation
from ..model.domain_schemas import validate_domain_fields
from ..graph.relations import Relation
from ..graph.scope_descriptors import ScopeDescriptor
from ..storage.json_syntax import parse_json_object
from .errors import ChangePlanError
from .schema import FORMAT_VERSION, METADATA_POLICY, OPERATION_TYPES, change_plan_schema, operation_schema

_CONTROLLED = frozenset({"id", "id_scheme", "artifact_type", "schema_version", "maturity", "revision",
    "created_at", "created_by", "updated_at", "updated_by", "relations"})


def _at(pointer, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ChangePlanError:
        raise
    except ModelError as error:
        raise ChangePlanError(error.reason, pointer=pointer + error.pointer) from error
    except (ValueError, TypeError, RecursionError) as error:
        raise ChangePlanError("invalid_change_plan_value", pointer=pointer) from error


def _text(value, pointer):
    if type(value) is not str or not value.strip() or "\0" in value:
        raise ChangePlanError("nonempty_text_required", pointer=pointer)


def _reference(value, pointer):
    _text(value, pointer)
    parts = value.split("-")
    if len(parts) != 3:
        raise ChangePlanError("invalid_artifact_reference", pointer=pointer)
    kind = next((item.artifact_type for item in artifact_types() if item.prefix == parts[1]), None)
    scheme = "legacy-sequential-v1" if re.fullmatch(r"[0-9]{4}", parts[2]) else "random128-v1"
    return _at(pointer, ArtifactIdentity, value, scheme, kind, parts[0])


def _artifact(value, pointer, expected_type=None):
    if type(value) is not dict:
        raise ChangePlanError("artifact_object_required", pointer=pointer)
    kind = value.get("artifact_type")
    validator = validate_record_fields if kind in RECORD_TYPES else validate_domain_fields
    _at(pointer, validator, value, expected_type=expected_type)
    return _at(pointer, artifact_identity, value)


def _generic(identity, pointer):
    if identity.artifact_type in SPECIAL_STATES:
        _at(pointer, require_generic_mutation, identity.artifact_type, "patch")


def _pointer(value, pointer):
    if type(value) is not str or (value and not value.startswith("/")) or re.search(r"~(?![01])", value):
        raise ChangePlanError("invalid_json_pointer", pointer=pointer)
    return [p.replace("~1", "/").replace("~0", "~") for p in value.split("/")[1:]]


def _mutable_pointer(value, pointer):
    parts = _pointer(value, pointer)
    if not parts or parts[0] in _CONTROLLED or parts[0] in {v[0] for v in SPECIAL_STATES.values()}:
        raise ChangePlanError("controlled_field_mutation", pointer=pointer)


def _patch(items, pointer):
    for index, item in enumerate(items):
        at = pointer + "/" + str(index)
        _pointer(item["path"], at + "/path")
        if item["op"] != "test":
            _mutable_pointer(item["path"], at + "/path")
        if "from" in item:
            _pointer(item["from"], at + "/from")
            if item["op"] == "move":
                _mutable_pointer(item["from"], at + "/from")


def _validate_operation(value, pointer=""):
    if type(value) is not dict or type(value.get("op")) is not str or value["op"] not in OPERATION_TYPES:
        raise ChangePlanError("unknown_operation", pointer=pointer + "/op")
    kind = value["op"]
    _at(pointer, validate_builtin, value, operation_schema(kind))
    for name in ("reason",):
        if name in value:
            _text(value[name], pointer + "/" + name)
    for name in ("source", "target"):
        if name in value:
            identity = _reference(value[name], pointer + "/" + name)
            if (name == "source" and kind.startswith("relation_") and kind != "relation_review_record"
                    or name == "target" and kind in ("update", "transition", "retire", "attachment_add", "attachment_remove")):
                _generic(identity, pointer + "/" + name)
    if kind == "create":
        identity = _artifact(value["artifact"], pointer + "/artifact")
        _generic(identity, pointer + "/artifact")
        if identity.id_scheme != "random128-v1":
            raise ChangePlanError("new_identity_requires_random128", pointer=pointer + "/artifact/id_scheme")
        if value["result_id"] != identity.id:
            raise ChangePlanError("creation_identity_mismatch", pointer=pointer + "/result_id", code="SRV146")
    elif kind == "update":
        _patch(value["patch"], pointer + "/patch")
    elif kind == "relation_add":
        _at(pointer + "/relation", Relation, _reference(value["source"], pointer + "/source"), value["relation"])
        if value["relation"].get("id_scheme") != "random128-v1":
            raise ChangePlanError("new_relation_requires_random128", pointer=pointer + "/relation/id_scheme")
    elif kind == "relation_remove":
        token = value["relation_id"]
        if not token.startswith("REL-"):
            raise ChangePlanError("invalid_relation_reference", pointer=pointer + "/relation_id")
        from ..model.identity_tokens import decode128
        _at(pointer + "/relation_id", decode128, token[4:])
    elif kind == "evidence_record":
        _artifact(value["evidence"], pointer + "/evidence", "evidence")
    elif kind == "attachment_add":
        _at(pointer + "/attachment", AttachmentDescriptor.from_data, value["attachment"])
        if not value["attachment"]["path"].startswith("attachments/"):
            raise ChangePlanError("attachment_path_required", pointer=pointer + "/attachment/path")
    elif kind == "attachment_remove":
        _at(pointer + "/path", project_path, value["path"])
        if not value["path"].startswith("attachments/"):
            raise ChangePlanError("attachment_path_required", pointer=pointer + "/path")
    elif kind == "representation_normalize":
        _at(pointer + "/path", project_path, value["path"])
    elif kind == "relation_review_record":
        _artifact(value["record"], pointer + "/record", "relation_review")
        if value["record"]["reviewer"]["actor_type"] != "human":
            raise ChangePlanError("human_review_required", pointer=pointer + "/record/reviewer")
        for index, entry in enumerate(value["approval_withdrawals"]):
            _reference(entry["target"], pointer + "/approval_withdrawals/" + str(index) + "/target")
    elif kind == "proposal_control":
        if _reference(value["target"], pointer + "/target").artifact_type != "proposal":
            raise ChangePlanError("proposal_target_required", pointer=pointer + "/target")
    return value


def _validate_plan(value, *, hash_present=True):
    if type(value) is not dict:
        raise ChangePlanError("plan_object_required")
    if value.get("metadata_policy_version") != METADATA_POLICY:
        raise ChangePlanError("unsupported_regular_metadata_policy", pointer="/metadata_policy_version", code="SRV174")
    schema = change_plan_schema()
    if not hash_present:
        schema["required"].remove("change_plan_sha256")
        schema["properties"].pop("change_plan_sha256")
    _at("", validate_builtin, value, schema)
    for name in ("change_plan_id", "request_id"):
        _text(value[name], "/" + name)
    _at("/planned_at", UtcTimestamp, value["planned_at"])
    _at("/actor", Actor, **value["actor"])
    _at("/base/scope_descriptor", ScopeDescriptor, value["base"]["scope_descriptor"])
    for index, operation in enumerate(value["operations"]):
        _validate_operation(operation, "/operations/" + str(index))
    for index, precondition in enumerate(value["preconditions"]):
        at = "/preconditions/" + str(index)
        if precondition["kind"] == "artifact":
            _reference(precondition["artifact_id"], at + "/artifact_id")
        else:
            _at(at + "/path", project_path, precondition["path"])
    seen = set()
    for index, result in enumerate(value["result_artifacts"]):
        at = "/result_artifacts/" + str(index)
        identity = _artifact(result["artifact"], at + "/artifact")
        if identity.id in seen:
            raise ChangePlanError("duplicate_result_identity", pointer=at, code="SRV146")
        seen.add(identity.id)
        if canonical_json_sha256(result["artifact"]) != result["sha256"]:
            raise ChangePlanError("result_hash_mismatch", pointer=at + "/sha256", code="SRV146")
    if hash_present:
        expected = canonical_json_sha256({k: v for k, v in value.items() if k != "change_plan_sha256"})
        if expected != value["change_plan_sha256"]:
            raise ChangePlanError("change_plan_hash_mismatch", pointer="/change_plan_sha256", code="SRV146")


@dataclass(frozen=True, init=False)
class ChangeOperation:
    """Immutable tagged operation data. Its workflow name is not authorization."""
    _encoded: bytes

    def __init__(self, value):
        encoded = _at("", canonical_json_bytes, value)
        owned = _at("", parse_json_object, encoded)
        _validate_operation(owned)
        object.__setattr__(self, "_encoded", encoded)

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def op(self):
        return self.data["op"]

    @property
    def executable(self):
        return False


@dataclass(frozen=True, init=False)
class ChangePlan:
    """A byte-preserving parsed plan, NOT a checked live-state or write ticket."""
    source_bytes: bytes
    _encoded: bytes

    def __init__(self, raw):
        if type(raw) is not bytes:
            raise ChangePlanError("bytes_required")
        value = _at("", parse_json_object, raw)
        _validate_plan(value)
        object.__setattr__(self, "source_bytes", raw)
        object.__setattr__(self, "_encoded", _at("", canonical_json_bytes, value))

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def canonical_bytes(self):
        return self._encoded

    @property
    def sha256(self):
        return self.data["change_plan_sha256"]

    @property
    def operations(self):
        return tuple(ChangeOperation(item) for item in self.data["operations"])

    @property
    def validation_scope(self):
        return "change_plan_fields_only"

    @property
    def write_authorized(self):
        return False

    @property
    def execution_ready(self):
        return False


def prepare_change_plan(value):
    """Bind supplied plan values; never invent IDs, actor, time or target data.

    Caller supplies an unsigned data object. Existing self-hashes must be read
    with ChangePlan instead of silently being replaced with a recalculated hash.
    """
    encoded = _at("", canonical_json_bytes, value)
    owned = _at("", parse_json_object, encoded)
    _validate_plan(owned, hash_present=False)
    owned["change_plan_sha256"] = canonical_json_sha256(owned)
    return ChangePlan(canonical_json_bytes(owned))
