"""One shared read-only pipeline for CLI/planner/adapter integrations.

Loading, resource inventory and trusted service registration belong to callers.
An unavailable required service is not a successful stub or publication approval.
"""
from __future__ import annotations

from collections import deque

from ..model.canonical import canonical_json_sha256
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
from .values import (
    VALIDATION_VERSION, HOOK_NAMES, ModelDocument, ModelGate, GateContext,
    GateDependencies, GateResult, ValidationReport, _sequence, _ids, _diagnostics,
    _document_bindings,
)
from ._model_checks import _issue, _applies, _foreign_edges, _reference_issues
from .resources import ValidationResources
from .production import production_gates, formal_findings, profile_applies


def validate_model(documents, *, profile=None, selected_ids=None, gates=(), resources=None):
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
    if resources is not None:
        if type(resources) is not ValidationResources:
            raise ModelError("validation_resources_required")
        resources = resources.snapshot()
        profile = resources.checked_profile(profile)
        builtins = production_gates(resources, profile)
        if any(g.gate_id in gate_index for g in builtins):
            raise ModelError("validation_builtin_gate_override")
        gates += builtins
        gate_index.update((g.gate_id, g) for g in builtins)
    basis = canonical_json_sha256({"version": VALIDATION_VERSION,
        **({"resources_sha256": resources.sha256} if resources is not None else {}),
        "documents": _document_bindings(documents),
        "selection": None if selected is None else list(selected),
        "profile": profile.binding() if profile is not None else None,
        "gates": [{"id": g.gate_id, "version": g.version, "resources_sha256": g.resources_sha256}
                  for g in sorted(gates, key=lambda g:g.gate_id)]})
    stages, records, checked = [], [], ()

    def applies(name, value):
        if name == "profile_lint" and resources is not None:
            return profile is not None and profile_applies(profile.data, value)
        return _applies(name, value, profile)

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
            "source_bindings": _document_bindings(documents),
            "identified_ids": sorted({v["id"] for _, v in parsed if type(v.get("id")) is str and v["id"]}),
            "identified_sources": [{"path": d.path, "artifact_id": v["id"]} for d, v in parsed
                                   if type(v.get("id")) is str and v["id"]],
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
    reference_issues = _reference_issues(records)
    if reference_issues:
        stage("identities_references", reference_issues)
        stage("graph_and_semantics", status="blocked")
        return report()
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
    missing = [identity for identity in checked if identity not in index]
    if missing:
        stage("scope", [{"reason": "validation_selected_id_missing", "severity": "error",
                         "artifact_id": identity, "related_ids": [identity]}
                        for identity in missing])
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
        subjects = tuple(r.identity.id for r in records if applies(gate.gate_id, r.data))
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
    if resources is not None:
        findings, formal_ids = formal_findings(documents, records, checked, profile, resources)
        stage("approval_formal", findings, ids=formal_ids,
              status=None if formal_ids else "not_applicable")
    names = sorted(set(HOOK_NAMES) | set(gate_index))
    for name in names:
        subjects = tuple(identity for identity in checked if applies(name, index[identity].data))
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
