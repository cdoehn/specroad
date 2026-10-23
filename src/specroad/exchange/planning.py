"""Read-only artifact import planning over explicit parsed candidates.

Format adapters supply source bytes and candidates; this service does not claim
to parse those bytes. Actual mappings, native lookup and the conflict policy
derive operations, then the ordinary Change Plan service checks the whole
target. IDs, creation envelopes, actor, time and trusted gates are explicit.
No filesystem discovery, writer, approval or completed import is involved.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..changes import ChangePlan, TargetModel, prepare_change_target
from ..changes._patch_policy import _mutable_pointer
from ..graph.relations import SourceRelations
from ..mappings import select_mapping
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from .comparison import ImportComparison
from .identities import ExternalIdentity, ImportIdentityError, NativeIdentityIndex
from ._identity_errors import _error


def _pointer(value):
    return "/" + value.replace("~", "~0").replace("/", "~1")


@dataclass(frozen=True, init=False)
class ImportPlan:
    """Owned plan/report, not a transaction or an import-completion receipt.

Only a conflict-free, loss-free, completely validated target exposes a regular
ChangePlan. Reload canonical_bytes through assess_import_plan with explicit
current inputs before reuse. The future writer must still check live inventory,
authorization and transaction gates before writing.
"""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError("Use prepare_import_plan to obtain a bound import plan")

    @classmethod
    def _create(cls, value):
        encoded = canonical_json_bytes(value)
        parse_json_object(encoded)
        result = object.__new__(cls)
        object.__setattr__(result, "_encoded", encoded)
        return result

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def canonical_bytes(self):
        """Passive serialization; loading these bytes alone grants no validity."""
        return self._encoded

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    @property
    def plan_valid(self):
        return self.data["plan_valid"]

    def require_valid(self):
        if not self.plan_valid:
            raise ImportIdentityError("valid_import_plan_required")
        return self

    @property
    def plan(self):
        self.require_valid()
        return ChangePlan(canonical_json_bytes(self.data["change_plan"]))

    @property
    def write_authorized(self):
        return False

    def __bool__(self):
        raise TypeError("Use plan_valid explicitly; an import report is not success")


def assess_import_plan(raw, model, candidates, *, input_format, input_bytes,
        mapping_resources, mapping_key, mapping_sha256, strategy,
        change_plan_id, request_id, actor, planned_at, scope_descriptor,
        metadata_policy_version, policy, gates=(), strict=False):
    """Recompute a saved envelope from explicitly supplied current inputs.

    The saved JSON never supplies its own expected input, basis, authoring
    metadata, policy or gates. Mapping/candidate/whole-target checks run again,
    including the actual source-file and resource byte bindings. All declared
    operations, results, diagnostics and negative authority flags must match
    the new observation. A changed gate result requires a newly prepared plan;
    an unchanged invalid report remains inspectable, never executable.

    JSON member order/whitespace in the envelope is immaterial. Exact source
    bytes remain bound separately. This does not parse the source payload or
    prove a live filesystem snapshot, authorization or successful import.
    """
    if type(raw) is not bytes:
        raise ImportIdentityError("import_plan_bytes_required")
    try:
        saved = parse_json_object(raw)
        canonical_json_bytes(saved)
    except ModelError as error:
        raise _error(error) from error
    if saved.get("format_version") != "artifact-import-plan-v1":
        raise ImportIdentityError("import_plan_format_unsupported", pointer="/format_version")
    current = prepare_import_plan(model, candidates, input_format=input_format,
        input_bytes=input_bytes, mapping_resources=mapping_resources,
        mapping_key=mapping_key, mapping_sha256=mapping_sha256, strategy=strategy,
        change_plan_id=change_plan_id, request_id=request_id, actor=actor,
        planned_at=planned_at, scope_descriptor=scope_descriptor,
        metadata_policy_version=metadata_policy_version, policy=policy, gates=gates, strict=strict)
    observed = current.data
    if set(saved) != set(observed):
        raise ImportIdentityError("import_plan_fields_mismatch")
    if canonical_json_bytes(saved["binding"]) != canonical_json_bytes(observed["binding"]):
        raise ImportIdentityError("import_plan_binding_mismatch", pointer="/binding")
    for name in sorted(observed):
        if canonical_json_bytes(saved[name]) != canonical_json_bytes(observed[name]):
            raise ImportIdentityError("import_plan_observation_mismatch", pointer=_pointer(name))
    return current


def prepare_import_plan(model, candidates, *, input_format, input_bytes,
        mapping_resources, mapping_key, mapping_sha256, strategy,
        change_plan_id, request_id, actor, planned_at, scope_descriptor,
        metadata_policy_version, policy, gates=(), strict=False):
    """Map artifact candidates into a bound, completely checked Change Plan.

Each candidate has identity, external_type, fields and new_artifact. The last
is a complete explicit creation envelope for an unknown key, otherwise None.
Mapped values override creation defaults; controlled fields cannot be mapped.
Existing relations and nonmapped fields remain intact. Attachment references
must resolve to actual bytes already bound by TargetModel; new attachment
publication and relation/registry candidates belong to later import adapters.
Unmapped source fields are individually reported as unaccepted losses.
"""
    if type(model) is not TargetModel:
        raise ImportIdentityError("import_target_model_required")
    if type(input_bytes) is not bytes:
        raise ImportIdentityError("source_payload_bytes_required", pointer="/input_bytes")
    if type(input_format) is not str or input_format not in ("csv", "ndjson", "reqif", "reqifz"):
        raise ImportIdentityError("import_format_required", pointer="/input_format")
    if type(candidates) not in (list, tuple):
        raise ImportIdentityError("import_candidates_required", pointer="/candidates")
    try:
        candidates = parse_json_object(canonical_json_bytes({"candidates": list(candidates)}))["candidates"]
    except ModelError as error:
        raise _error(error) from error
    selected = select_mapping(mapping_resources, key=mapping_key, expected_sha256=mapping_sha256)
    resource = selected.resource
    if resource.data["source_format"] != ("reqif" if input_format == "reqifz" else input_format):
        raise ImportIdentityError("import_mapping_format_mismatch", pointer="/input_format")
    # Validate the explicit strategy even for an empty candidate set.
    ImportComparison(None, mapping_id=resource.key, strategy=strategy,
                     local_projection={}, source_projection={})
    model = model.snapshot()
    native = NativeIdentityIndex([SourceRelations(d.content, path=d.path) for d in model.documents])
    artifacts = {value["id"]: value for value in model.artifacts}
    operations, objects, losses, diagnostics, conflicts = [], [], [], [], []
    keys, owners = set(), set()
    for number, candidate in enumerate(candidates):
        at = "/candidates/" + str(number)
        if type(candidate) is not dict or set(candidate) != {"identity", "external_type", "fields", "new_artifact"}:
            raise ImportIdentityError("import_artifact_candidate_required", pointer=at)
        identity = ExternalIdentity(candidate["identity"])
        if set(identity.data) - {"source_system", "source_document", "external_id", "external_revision"}:
            raise ImportIdentityError("import_source_identity_fields_unsupported", pointer=at + "/identity")
        if identity.key in keys:
            raise ImportIdentityError("duplicate_external_artifact_identity", pointer=at + "/identity")
        keys.add(identity.key)
        mapped = selected.artifact(candidate["external_type"], candidate["fields"])
        projection = mapped["artifact"]
        for name in projection:
            if name == "artifact_type":
                continue
            if name == "external_identities":
                raise ImportIdentityError("import_mapping_identity_mutation", pointer=at + "/fields")
            # Reuse the ordinary update contract, also for new-object mappings.
            _mutable_pointer(_pointer(name), at + "/fields")
        owner = native.lookup("artifact", *identity.key)
        old = None if owner is None else artifacts[owner["artifact_id"]]
        if old is None:
            template = candidate["new_artifact"]
            if type(template) is not dict:
                raise ImportIdentityError("import_creation_envelope_required", pointer=at + "/new_artifact")
            if template.get("artifact_type") != projection["artifact_type"]:
                raise ImportIdentityError("import_native_type_mismatch", pointer=at + "/new_artifact/artifact_type")
            if template.get("external_identities") or template.get("relations"):
                raise ImportIdentityError("import_creation_links_unsupported", pointer=at + "/new_artifact")
            native_id = template.get("id")
        else:
            if candidate["new_artifact"] is not None:
                raise ImportIdentityError("import_known_creation_envelope", pointer=at + "/new_artifact")
            if old["artifact_type"] != projection["artifact_type"]:
                raise ImportIdentityError("import_native_type_mismatch", pointer=at + "/external_type")
            native_id = old["id"]
        if type(native_id) is not str:
            raise ImportIdentityError("import_native_id_required", pointer=at + "/new_artifact/id")
        if native_id in owners:
            raise ImportIdentityError("import_duplicate_native_candidate", pointer=at)
        owners.add(native_id)
        for field, value in sorted(mapped["unmapped"].items()):
            pointer = at + "/fields" + _pointer(field)
            losses.append({"candidate_index": number, "artifact_id": native_id,
                "pointer": pointer, "reason": "unmapped_external_field", "value": value,
                "accepted": False})
            diagnostics.append(ImportIdentityError("unaccepted_import_loss", pointer=pointer).diagnostic())
        local = {} if old is None else {key: old[key] for key in projection if key in old}
        comparison = ImportComparison(None if owner is None else owner["identity"],
            mapping_id=resource.key, strategy=strategy, local_projection=local, source_projection=projection).data
        observed = {"candidate_index": number, "artifact_id": native_id,
            "identity": identity.data, "comparison": comparison["comparison"],
            "action": "create" if old is None else comparison["action"]}
        objects.append(observed)
        diagnostics.extend({**d, "candidate_index": number, "artifact_id": native_id}
                           for d in comparison["diagnostics"])
        if comparison["comparison"] == "diverged":
            conflicts.append({**observed, "code": "SRV148", "resolved": False})
        if old is not None and comparison["action"] != "adopt":
            # No-op may retain its baseline; skip/retain/reject MUST retain it.
            continue
        source_identity = identity.data if old is None else {**owner["identity"], **identity.data}
        history = ExternalIdentity(source_identity).with_import_history(mapping_id=resource.key,
            imported_projection=projection, source_projection=projection,
            source_payload=input_bytes, imported_at=planned_at).data
        if old is None:
            value = {**template, **projection, "external_identities": [history]}
            operations.append({"op": "create", "artifact": value, "result_id": native_id})
        else:
            identities = [history if ExternalIdentity(item).key == identity.key else item
                          for item in old["external_identities"]]
            desired = {**projection, "external_identities": identities}
            patch = [{"op": "replace" if key in old else "add", "path": _pointer(key), "value": value}
                     for key, value in sorted(desired.items())
                     if key not in old or canonical_json_bytes(old[key]) != canonical_json_bytes(value)]
            if patch:
                operations.append({"op": "update", "target": native_id,
                    "expected_sha256": canonical_json_sha256(old), "patch": patch})
    target = prepare_change_target(model, operations, change_plan_id=change_plan_id,
        request_id=request_id, actor=actor, planned_at=planned_at, scope_descriptor=scope_descriptor,
        metadata_policy_version=metadata_policy_version, policy=policy, gates=gates, strict=strict)
    assessment = target.data
    plan = target.plan
    diagnostics.extend(assessment["validation"]["diagnostics"])
    created = [op["result_id"] for op in operations if op["op"] == "create"]
    updated = [op["target"] for op in operations if op["op"] == "update"]
    binding = {"input_format": input_format, "input_sha256": sha256(input_bytes).hexdigest(),
        "input_size": len(input_bytes), "mapping": resource.binding(),
        "mapping_source_sha256": resource.source_sha256,
        "candidates_sha256": canonical_json_sha256(candidates),
        "base_model_root_sha256": plan.data["base"]["model_root_sha256"],
        "change_plan_sha256": plan.sha256, "target_binding": assessment["binding"]}
    valid = target.target_validated and not losses and not conflicts and not any(
        item.get("exit_code", 0) for item in diagnostics)
    return ImportPlan._create({"format_version": "artifact-import-plan-v1", "binding": binding,
        "strategy": strategy, "change_plan_id": change_plan_id,
        "input_sha256": binding["input_sha256"], "mapping_sha256": resource.sha256,
        "operations": operations, "created_ids": sorted(created), "updated_ids": sorted(updated),
        "objects": objects, "skipped": [item for item in objects if item["action"] == "skip"],
        "conflicts": conflicts, "losses": losses, "diagnostics": diagnostics,
        "attachments": assessment["target_manifest"]["attachments"],
        "attachment_scope": "complete_supplied_target",
        "target_model_root_sha256": plan.data["expected_result"]["model_root_sha256"],
        "target_assessment": assessment, "change_plan": plan.data,
        "plan_valid": bool(valid), "exit_code": 0 if valid else max(3, assessment["validation"]["exit_code"]),
        "candidate_origin": "explicit_parsed_artifacts", "input_parsed": False,
        "import_completed": False, "execution_ready": False, "write_authorized": False})
