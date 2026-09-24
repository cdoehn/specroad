"""One read-only validation pipeline for an explicitly supplied model.

The caller owns loading/inventory and registers trusted Python validators; JSON
cannot choose imports or callbacks. A missing applicable validator is a missing
check, never a successful stub. Results never authorize publication or approval.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Callable

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.domain_schemas import DOMAIN_TYPES, validate_domain_fields
from ..model.record_schemas import RECORD_TYPES, validate_record_fields
from ..profiles.composition import check_composed_fields
from ..profiles.composition_values import EffectiveProfile
from ..storage.json_syntax import parse_json_object
from ..graph.relations import SourceRelations
from ..graph.references import RelationReferences
from ..graph.hierarchies import validate_hierarchies
from ..graph.symmetry import require_canonical_relations
from ..graph.relation_obligations import RelationObligations

VALIDATION_VERSION = "model-validation-v1"
# These semantic services have their own planned implementations. Field schemas
# do not certify sealed baselines, current evidence or legitimate approvals.
HOOK_NAMES = (
    "lifecycle", "baseline_integrity", "evidence_currentness", "review_currentness",
    "profile_lint", "language_policy", "document_model", "external_resources", "configuration",
)


def _text(value, reason):
    if type(value) is not str or not value.strip():
        raise ModelError(reason)
    return value


def _sequence(value, reason):
    if type(value) not in (tuple, list):
        raise ModelError(reason)
    return tuple(value)


def _ids(values):
    values = _sequence(values, "validation_ids_required")
    for value in values:
        _text(value, "validation_id_required")
    if len(set(values)) != len(values):
        raise ModelError("duplicate_validation_id")
    return tuple(sorted(values))


@dataclass(frozen=True)
class ModelDocument:
    """A logical source label and exact already-loaded bytes, never a file opener."""
    path: str
    content: bytes

    def __post_init__(self):
        _text(self.path, "validation_source_label_required")
        if type(self.content) is not bytes:
            raise ModelError("validation_source_bytes_required", path=self.path)


def _diagnostics(value):
    items = _sequence(value, "validation_diagnostics_required")
    for item in items:
        if type(item) is not dict:
            raise ModelError("validation_diagnostic_required")
        _text(item.get("reason"), "validation_diagnostic_reason_required")
        if item.get("severity", "error") not in ("info", "warning", "error"):
            raise ModelError("validation_diagnostic_severity_invalid")
        for key in ("artifact_id", "path"):
            if key in item and item[key] is not None and type(item[key]) is not str:
                raise ModelError("validation_diagnostic_location_invalid")
        if "pointer" in item and (type(item["pointer"]) is not str or
                                   (item["pointer"] and not item["pointer"].startswith("/"))):
            raise ModelError("validation_diagnostic_pointer_invalid")
    return canonical_json_bytes(list(items))


@dataclass(frozen=True, init=False)
class GateResult:
    """A result bound to one gate, exact sources, selection and complete subjects."""
    input_sha256: str
    checked_ids: tuple
    _diagnostics: bytes

    def __init__(self, input_sha256, checked_ids, diagnostics=()):
        _text(input_sha256, "validation_binding_required")
        object.__setattr__(self, "input_sha256", input_sha256)
        object.__setattr__(self, "checked_ids", _ids(checked_ids))
        object.__setattr__(self, "_diagnostics", _diagnostics(diagnostics))

    @property
    def diagnostics(self):
        return parse_json_object(b'{"items":' + self._diagnostics + b'}')["items"]


@dataclass(frozen=True, init=False)
class GateDependencies:
    """Explicit empty lists count; omitted sources do not. No resources are fetched."""
    input_sha256: str
    _encoded: bytes

    def __init__(self, input_sha256, by_artifact):
        _text(input_sha256, "validation_binding_required")
        if type(by_artifact) is not dict:
            raise ModelError("validation_dependency_mapping_required")
        owned = {}
        for source, targets in by_artifact.items():
            _text(source, "validation_dependency_source_required")
            owned[source] = list(_ids(targets))
        object.__setattr__(self, "input_sha256", input_sha256)
        object.__setattr__(self, "_encoded", canonical_json_bytes(owned))

    @property
    def by_artifact(self):
        return parse_json_object(self._encoded)


@dataclass(frozen=True)
class ModelGate:
    """Explicit trusted code only. Version identifies a gate, not proof of trust.

    Built-in checks cannot be replaced. Reserved semantic hooks apply according
    to Core policy; an extra ``extension:...`` gate applies to all selected IDs.
    Both discovery and checking must return the bound, complete result contract.
    """
    gate_id: str
    version: str
    dependencies: Callable
    check: Callable
    resources_sha256: str | None = None

    def __post_init__(self):
        _text(self.gate_id, "validation_gate_id_required")
        _text(self.version, "validation_gate_version_required")
        if self.gate_id not in HOOK_NAMES and not self.gate_id.startswith("extension:"):
            raise ModelError("validation_gate_id_reserved_or_unknown")
        if self.gate_id == "extension:":
            raise ModelError("validation_gate_id_required")
        if self.resources_sha256 is not None and (type(self.resources_sha256) is not str or
                re.fullmatch(r"[0-9a-f]{64}", self.resources_sha256) is None):
            raise ModelError("validation_gate_resource_binding_invalid")
        if not callable(self.dependencies) or not callable(self.check):
            raise ModelError("validation_trusted_gate_callable_required")


@dataclass(frozen=True, init=False)
class GateContext:
    """Owned bytes and immutable IDs; reads return detached JSON values."""
    documents: tuple
    subjects: tuple
    gate_id: str
    version: str
    phase: str
    input_sha256: str
    _profile_bytes: bytes | None
    _records: tuple
    resources_sha256: str | None

    def __init__(self, *args, **kwargs):
        raise TypeError("Gate contexts are created by the validation pipeline")

    @classmethod
    def _create(cls, records, documents, profile, subjects, gate, phase, basis):
        obj = object.__new__(cls)
        subjects = _ids(subjects)
        binding = canonical_json_sha256({"model": basis, "gate": gate.gate_id,
            "version": gate.version, "phase": phase, "subjects": list(subjects)})
        for name, value in (("documents", documents), ("subjects", subjects),
                            ("gate_id", gate.gate_id), ("version", gate.version),
                            ("phase", phase), ("input_sha256", binding),
                            ("_profile_bytes", profile.canonical_bytes if profile is not None else None),
                            ("_records", tuple((r.identity.id, r.source_bytes) for r in records)),
                            ("resources_sha256", gate.resources_sha256)):
            object.__setattr__(obj, name, value)
        return obj

    @property
    def all_ids(self):
        return tuple(identity for identity, _ in self._records)

    def artifact(self, identity):
        for key, raw in self._records:
            if key == identity:
                return parse_json_object(raw)
        raise ModelError("validation_context_artifact_missing")

    @property
    def profile_data(self):
        return None if self._profile_bytes is None else parse_json_object(self._profile_bytes)

    def result(self, diagnostics=()):
        return GateResult(self.input_sha256, self.subjects, diagnostics)

    def dependency_result(self, by_artifact):
        return GateDependencies(self.input_sha256, by_artifact)


@dataclass(frozen=True, init=False)
class ValidationReport:
    """Pipeline observation, not permission, inventory authentication or a snapshot."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError("Use validate_model to obtain a report")

    def __bool__(self):
        raise TypeError("Use report.passed explicitly; an incomplete report is not success")

    @classmethod
    def _create(cls, data):
        obj = object.__new__(cls)
        object.__setattr__(obj, "_encoded", canonical_json_bytes(data))
        return obj

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def passed(self):
        return self.data["model_valid"] is True

    @property
    def complete(self):
        return self.data["checks_complete"]

    @property
    def diagnostics(self):
        return tuple(item for stage in self.data["stages"] for item in stage["diagnostics"])


def _issue(error, artifact_id=None, path=None):
    return {**error.diagnostic(), "artifact_id": artifact_id,
            "path": error.path if error.path is not None else path, "severity": "error"}


def _applies(hook, data, profile):
    kind, maturity = data["artifact_type"], data["maturity"]
    if hook == "lifecycle":
        return maturity != "draft" or kind in ("proposal", "baseline", "evidence", "relation_review")
    if hook == "baseline_integrity":
        return kind == "baseline"
    if hook == "evidence_currentness":
        return kind in ("evidence", "verification", "test")
    if hook == "review_currentness":
        return kind == "relation_review" or (kind == "requirement" and maturity == "approved")
    if hook == "profile_lint":
        return profile is not None and bool(profile.data["merge"]["lint_rules"])
    if hook == "language_policy":
        return "language" in data
    if hook == "document_model":
        return kind in ("document", "section", "content_block", "view")
    if hook == "external_resources":
        return kind in ("source", "code_ref") or bool(data.get("attachments"))
    if hook == "configuration":
        return kind == "configuration" or "applicability" in data
    return hook.startswith("extension:")


def _foreign_edges(records, references):
    """Only declared Core reference fields; never scan arbitrary strings/Extensions."""
    index = {r.identity.id: r for r in records}
    relations = {e.relation.identity.id: e for e in references.relations}
    edges = []
    for record in records:
        data, source = record.data, record.identity.id
        kind = data["artifact_type"]
        candidates = []
        if kind == "interface":
            candidates.extend((data[k], "/" + k, "component") for k in ("source_component", "target_component"))
        if kind == "verification":
            candidates.extend((v, "/subjects/" + str(i), None) for i, v in enumerate(data["subjects"]))
            candidates.extend((v["test_id"], "/evidence_slots/" + str(i) + "/test_id", "test")
                              for i, v in enumerate(data["evidence_slots"]) if v["test_id"] is not None)
        if kind == "evidence":
            candidates.extend((v["artifact_id"], "/subjects/" + str(i) + "/artifact_id", None)
                              for i, v in enumerate(data["subjects"]))
            if data["run_context"] is not None and data["run_context"]["test_id"] is not None:
                candidates.append((data["run_context"]["test_id"], "/run_context/test_id", "test"))
        if kind == "configuration" and data.get("parent") is not None:
            candidates.append((data["parent"], "/parent", "configuration"))
        if kind == "relation_review":
            relation = relations.get(data["relation_id"])
            if relation is None:
                raise ModelError("validation_review_relation_missing", path=record.path, pointer="/relation_id")
            candidates.extend((v, "/relation_id", None) for v in (relation.source.id, relation.target.id))
        for i, provenance in enumerate(data.get("provenance", ())):
            if provenance.get("source_id") is not None:
                candidates.append((provenance["source_id"], "/provenance/" + str(i) + "/source_id", "source"))
        if data.get("verification_waiver") is not None:
            candidates.append((data["verification_waiver"]["human_review_id"], "/verification_waiver/human_review_id", "relation_review"))
        for target, pointer, target_kind in candidates:
            if target not in index:
                raise ModelError("validation_field_target_missing", path=record.path, pointer=pointer)
            if target_kind is not None and index[target].identity.artifact_type != target_kind:
                raise ModelError("validation_field_target_type", path=record.path, pointer=pointer)
            edges.append((source, target))
    return edges


def validate_model(documents, *, profile=None, selected_ids=None, gates=()):
    """Validate all loaded documents, or a conservatively expanded selection.

    Parsing/schema/reference checks inspect the ENTIRE supplied model, even for
    a selection: an unreadable outside source cannot silently hide an incoming
    dependency. Semantic checks use its dependency-expanded connected component.
    File inventory, actual prior lifecycle states and semantic service data must
    come from their trusted providers. Nothing is read, changed or downloaded.
    """
    documents = _sequence(documents, "validation_documents_required")
    if any(type(d) is not ModelDocument for d in documents):
        raise ModelError("validation_document_required")
    if len({d.path for d in documents}) != len(documents):
        raise ModelError("duplicate_validation_source")
    documents = tuple(sorted(documents, key=lambda d: d.path))
    if profile is not None and type(profile) is not EffectiveProfile:
        raise ModelError("validation_effective_profile_required")
    selected = None if selected_ids is None else _ids(selected_ids)
    if selected == ():
        raise ModelError("empty_validation_selection")
    gates = _sequence(gates, "validation_gates_required")
    if any(type(g) is not ModelGate for g in gates):
        raise ModelError("validation_gate_required")
    gate_index = {g.gate_id: g for g in gates}
    if len(gate_index) != len(gates):
        raise ModelError("duplicate_validation_gate")
    basis = canonical_json_sha256({"version": VALIDATION_VERSION,
        "documents": [{"path": d.path, "sha256": sha256(d.content).hexdigest()} for d in documents],
        "selection": None if selected is None else list(selected),
        "profile": profile.binding() if profile is not None else None,
        "gates": [{"id": g.gate_id, "version": g.version, "resources_sha256": g.resources_sha256}
                  for g in sorted(gates, key=lambda g:g.gate_id)]})
    stages, records, checked = [], [], ()

    def stage(name, diagnostics=(), status=None, ids=()):
        diagnostics = list(diagnostics)
        if status is None:
            status = "failed" if any(d.get("severity", "error") == "error" for d in diagnostics) else "passed"
        stages.append({"stage": name, "status": status, "checked_ids": list(ids), "diagnostics": diagnostics})

    def report():
        failed = any(s["status"] == "failed" for s in stages)
        complete = all(s["status"] in ("passed", "failed", "not_applicable") for s in stages)
        return ValidationReport._create({"format_version": VALIDATION_VERSION,
            "input_sha256": basis, "validation_scope": "loaded_model" if selected is None else "dependency_expanded_loaded_scope",
            "source_count": len(documents), "structural_scope": "all_supplied_documents",
            "requested_ids": None if selected is None else list(selected), "checked_ids": list(checked),
            "stages": stages, "checks_complete": complete,
            "model_valid": False if failed else True if complete else None,
            "approval_granted": False, "write_authorized": False,
            "project_files_verified": False, "atomic_snapshot": False})

    parsed, errors = [], []
    for document in documents:
        try:
            parsed.append((document, parse_json_object(document.content, path=document.path)))
        except ModelError as error:
            errors.append(_issue(error))
    stage("parsing", errors)
    schema_errors = []
    for document, data in parsed:
        try:
            kind = data.get("artifact_type")
            if type(kind) is not str:
                raise ModelError("artifact_type_required", pointer="/artifact_type")
            if kind in DOMAIN_TYPES:
                validate_domain_fields(data)
            elif kind in RECORD_TYPES:
                validate_record_fields(data)
            else:
                raise ModelError("unknown_artifact_type", pointer="/artifact_type")
            records.append(SourceRelations(document.content, path=document.path))
        except ModelError as error:
            identity = data.get("id") if type(data.get("id")) is str else None
            schema_errors.append(_issue(error, identity, document.path))
    stage("schema_types_identity_fields", schema_errors,
          status="failed" if schema_errors else "blocked" if errors else "passed",
          ids=tuple(r.identity.id for r in records))
    if errors or schema_errors:
        stage("model_dependencies", status="blocked")
        return report()
    records = tuple(sorted(records, key=lambda r: r.identity.id))
    try:
        references = RelationReferences(records)
        foreign = _foreign_edges(records, references)
        stage("identities_references", ids=tuple(r.identity.id for r in records))
    except ModelError as error:
        stage("identities_references", [_issue(error)])
        stage("graph_and_semantics", status="blocked")
        return report()
    try:
        require_canonical_relations(references)
        validate_hierarchies(references)
        stage("graph", ids=tuple(r.identity.id for r in records))
    except ModelError as error:
        stage("graph", [_issue(error)])
        stage("model_semantics", status="blocked")
        return report()
    index = {r.identity.id: r for r in records}
    checked = tuple(index) if selected is None else selected
    if any(identity not in index for identity in checked):
        stage("scope", [{"reason": "validation_selected_id_missing", "severity": "error"}])
        stage("model_semantics", status="blocked")
        return report()
    adjacency = {identity:set() for identity in index}
    for source, target in [*( (e.source.id, e.target.id) for e in references.relations), *foreign]:
        adjacency[source].add(target)
        adjacency[target].add(source)
    # Discovery examines all applicable sources to avoid losing dependencies
    # arriving from an outside artifact. The result must be explicitly complete.
    dependency_errors = []
    for gate in sorted(gates, key=lambda g:g.gate_id):
        subjects = tuple(r.identity.id for r in records if _applies(gate.gate_id, r.data, profile))
        if not subjects:
            continue
        context = GateContext._create(records, documents, profile, subjects, gate, "dependencies", basis)
        try:
            observation = gate.dependencies(context)
            if (type(observation) is not GateDependencies or observation.input_sha256 != context.input_sha256
                    or set(observation.by_artifact) != set(subjects)):
                raise ModelError("validation_gate_dependencies_unbound_or_incomplete")
            for source, targets in observation.by_artifact.items():
                for target in targets:
                    if target not in index:
                        raise ModelError("validation_gate_dependency_missing")
                    adjacency[source].add(target)
                    adjacency[target].add(source)
        except ModelError as error:
            dependency_errors.append({**_issue(error), "gate_id": gate.gate_id})
        except Exception:
            dependency_errors.append({"reason": "validation_gate_discovery_failed", "severity": "error", "gate_id":gate.gate_id})
    if dependency_errors:
        stage("scope", dependency_errors)
        stage("model_semantics", status="blocked")
        return report()
    pending, visited = deque(checked), set(checked)
    while pending:
        for target in sorted(adjacency[pending.popleft()]):
            if target not in visited:
                visited.add(target);pending.append(target)
    checked = tuple(sorted(visited))
    stage("scope", ids=checked)
    if profile is None:
        stage("profiles", [{"reason":"validation_profile_unavailable", "severity":"error"}], status="unavailable", ids=checked)
    else:
        field_errors = []
        for identity in checked:
            field_errors.extend({**d,"artifact_id":identity,"path":index[identity].path}
                                for d in check_composed_fields(profile, index[identity].data)["diagnostics"])
        stage("profiles", field_errors, ids=checked)
    rules = () if profile is None else profile.minimum_relation_rules()
    obligations = RelationObligations(records, profile_rules=rules)
    stage("minimum_relations", [d for d in obligations.diagnostics if d["artifact_id"] in visited], ids=checked)
    # The local schema already checked maturity, revision/actor/time value types
    # and special-state couplings. It did NOT verify historical authorization.
    stage("stored_lifecycle_fields", ids=checked)
    names = sorted(set(HOOK_NAMES) | set(gate_index))
    for name in names:
        subjects = tuple(identity for identity in checked if _applies(name, index[identity].data, profile))
        if not subjects:
            stage(name, status="not_applicable")
            continue
        gate = gate_index.get(name)
        if gate is None:
            stage(name, [{"reason":"validation_required_gate_unavailable", "severity":"error", "gate_id":name}],
                  status="unavailable", ids=subjects)
            continue
        context = GateContext._create(records, documents, profile, subjects, gate, "check", basis)
        try:
            outcome = gate.check(context)
            if (type(outcome) is not GateResult or outcome.input_sha256 != context.input_sha256
                    or outcome.checked_ids != subjects):
                raise ModelError("validation_gate_result_unbound_or_incomplete")
            diagnostics = outcome.diagnostics
            _diagnostics(diagnostics)
            if any(d.get("artifact_id") is not None and d["artifact_id"] not in subjects for d in diagnostics):
                raise ModelError("validation_gate_diagnostic_outside_subjects")
            stage(name, diagnostics, ids=subjects)
        except ModelError as error:
            stage(name, [_issue(error)], ids=subjects)
        except Exception:
            stage(name, [{"reason":"validation_gate_check_failed", "severity":"error"}], ids=subjects)
    return report()
