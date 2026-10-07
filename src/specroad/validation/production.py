"""Existing language, SRX and formal approval kernels over actual loaded inputs."""
from ..graph.relations import SourceRelations
from ..languages import evaluate_language
from ..languages.containers import evaluate_project_languages
from ..languages.container_values import ContainerModel
from ..model.language_policy import LanguagePolicy
from ..model.canonical import canonical_json_sha256
from ..profiles.fields import _applies as rule_applies
from ..srx import SrxProgram, EvaluationContext, evaluate
from ..srx.errors import SrxError
from ..srx.graph import LoadedGraph
from ..srx.resources import ResourcePolicy
from .approval import formal_requirement_findings
from .approval_values import ApprovalContext
from .values import ModelGate


def _dependencies(context):
    # Both project mixing and SRX graph queries may inspect outside the selected
    # component. W conservatively retains the entire supplied model dependency.
    return context.dependency_result({identity: list(context.all_ids) for identity in context.subjects})


def profile_applies(profile, artifact):
    return any(rule_applies(rule, artifact) for rule in profile["merge"]["lint_rules"])


def _paths(context):
    return {r.identity.id: r.path for r in
            (SourceRelations(d.content, path=d.path) for d in context.documents)}


def _language(context, resources):
    policy = LanguagePolicy(resources.configuration.data.get("language_policy", {}))
    paths, findings = _paths(context), []
    for identity in context.subjects:
        value = context.artifact(identity)
        report = evaluate_language(value["language"], policy=policy, registry=resources.registry)
        findings.extend({**item, "artifact_id": identity, "path": paths[identity],
                         "pointer": "/language"} for item in report["diagnostics"])
    model = ContainerModel(tuple(d.content for d in context.documents))
    mixed = evaluate_project_languages(model, policy=policy, registry=resources.registry)
    # Declarations were checked above, including historical Requirements. The
    # existing container kernel owns the active project mixing membership.
    findings.extend({**item, "related_ids": item["requirement_ids"]}
                    for item in mixed["diagnostics"] if item["code"] == "SRV180")
    return context.result(findings)


def _profile(context, resources):
    paths, findings = _paths(context), []
    sources = tuple(SourceRelations(d.content, path=d.path) for d in context.documents)
    for rule in context.profile_data["merge"]["lint_rules"]:
        rule_id = rule["rule_id"]
        graph = LoadedGraph(sources, rule_id=rule_id)
        for identity in context.subjects:
            artifact = context.artifact(identity)
            if not rule_applies(rule, artifact):
                continue
            common = {"artifact_id": identity, "path": paths[identity],
                      "rule_id": rule_id, "origin": "profile_rule", "rule_version": rule["version"],
                      "rule_sha256": canonical_json_sha256(rule)}
            try:
                project = resources.configuration.data
                current = ResourcePolicy.from_project(project, rule_id=rule_id).structure
                for key, default in (("srx_nodes", current.ast_nodes), ("srx_depth", current.ast_depth)):
                    if key in context.profile_data["merge"]["hard_limits"]:
                        project.setdefault("resource_limits", {})[key] = min(
                            default, context.profile_data["merge"]["hard_limits"][key])
                roots = graph.candidate_roots({"project": project,
                    "configuration": None}, identity, rule_id=rule_id)
                result = evaluate(SrxProgram(rule["program"], rule_id=rule_id),
                    EvaluationContext(roots, rule_id=rule_id, graph=graph))
                if type(result) is not bool:
                    raise SrxError("profile_lint_boolean_required", rule_id=rule_id,
                                   expected="boolean", actual="non_boolean")
                if not result:
                    findings.append({**common, "code": "PROFILE_LINT", "severity": rule["severity"],
                        "reason": "profile_lint_predicate_false", "pointer": ""})
            except SrxError as error:
                findings.append({**error.diagnostic(), **common, "severity": "error"})
    return context.result(findings)


def production_gates(resources, profile):
    gates = []
    if resources.registry is not None:
        gates.append(ModelGate("language_policy", "production-language-v1", _dependencies,
            lambda context: _language(context, resources), resources.sha256))
    if profile is not None and profile.data["merge"]["lint_rules"]:
        gates.append(ModelGate("profile_lint", "production-profile-srx-v1", _dependencies,
            lambda context: _profile(context, resources), resources.sha256))
    return tuple(gates)


def formal_findings(documents, records, checked, profile, resources):
    findings, identities = [], []
    for record in records:
        value = record.data
        if (record.identity.id not in checked or value["artifact_type"] != "requirement"
                or value["maturity"] not in ("in_review", "approved")):
            continue
        identities.append(record.identity.id)
        context = ApprovalContext(record.identity.id, documents, profile=profile,
            configuration=resources.configuration.data,
            mode="stored" if value["maturity"] == "approved" else "transition")
        for item in formal_requirement_findings(context):
            diagnostic = item["diagnostic"]
            findings.append({**diagnostic, "reason": item["reason"],
                             "path": diagnostic.get("path") or record.path})
    return findings, identities
