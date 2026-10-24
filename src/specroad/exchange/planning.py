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
from ..mappings import select_mapping
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from .comparison import ImportComparison
from .identities import ImportIdentityError
from ._identity_errors import _error
from ._planning_candidates import _pointer, _prepare_candidate_changes
from ._planning_report import _import_plan_report



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
Requirements also require explicit mappings for language, normative_force and
statement; missing content mappings are losses, never filled from an envelope
or an existing artifact, and produce no candidate operation or new history.
"""
    model, candidates, selected = _prepare_import_inputs(model, candidates,
        input_format=input_format, input_bytes=input_bytes, mapping_resources=mapping_resources,
        mapping_key=mapping_key, mapping_sha256=mapping_sha256, strategy=strategy)
    changes = _prepare_candidate_changes(model, candidates, selected, strategy=strategy,
        input_bytes=input_bytes, planned_at=planned_at)
    return _finish_import_plan(model, candidates, selected, changes,
        input_format=input_format, input_bytes=input_bytes, strategy=strategy,
        change_plan_id=change_plan_id, request_id=request_id, actor=actor,
        planned_at=planned_at, scope_descriptor=scope_descriptor,
        metadata_policy_version=metadata_policy_version, policy=policy, gates=gates, strict=strict)


def _prepare_import_inputs(model, candidates, *, input_format, input_bytes,
                           mapping_resources, mapping_key, mapping_sha256, strategy):
    """Own the common direct/Work inputs without executing candidate units."""
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
    return model.snapshot(), candidates, selected


def _finish_import_plan(model, candidates, selected, changes, *, input_format,
        input_bytes, strategy, change_plan_id, request_id, actor, planned_at,
        scope_descriptor, metadata_policy_version, policy, gates=(), strict=False):
    """One complete target reduction, shared by direct and resumed planning."""
    target = prepare_change_target(model, changes.operations, change_plan_id=change_plan_id,
        request_id=request_id, actor=actor, planned_at=planned_at, scope_descriptor=scope_descriptor,
        metadata_policy_version=metadata_policy_version, policy=policy, gates=gates, strict=strict)
    return ImportPlan._create(_import_plan_report(changes, target, candidates, selected.resource,
        input_format=input_format, input_bytes=input_bytes, strategy=strategy,
        change_plan_id=change_plan_id))
