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


def _observed_sources(context):
    sources = tuple(SourceRelations(d.content, path=d.path) for d in context.documents)
    return sources, {source.identity.id: source.path for source in sources}


def _language(context, resources):
    policy = LanguagePolicy(resources.configuration.data.get("language_policy", {}))
    _, paths = _observed_sources(context)
    findings = []
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


def _rule_project(resources, profile, rule_id):
    """Combine actual project policy and composed hard limits on detached data."""
    project = resources.configuration.data
    current = ResourcePolicy.from_project(project, rule_id=rule_id).structure
    limits = profile["merge"]["hard_limits"]
    for key, default in (("srx_nodes", current.ast_nodes), ("srx_depth", current.ast_depth)):
        if key in limits:
            project.setdefault("resource_limits", {})[key] = min(default, limits[key])
    return project


def _profile_origin(rule, identity, path):
    return {"artifact_id": identity, "path": path, "rule_id": rule["rule_id"],
            "origin": "profile_rule", "rule_version": rule["version"],
            "rule_sha256": canonical_json_sha256(rule)}


def _profile(context, resources):
    sources, paths = _observed_sources(context)
    findings = []
    for rule in context.profile_data["merge"]["lint_rules"]:
        rule_id = rule["rule_id"]
        graph = LoadedGraph(sources, rule_id=rule_id)
        for identity in context.subjects:
            artifact = context.artifact(identity)
            if not rule_applies(rule, artifact):
                continue
            common = _profile_origin(rule, identity, paths[identity])
            try:
                project = _rule_project(resources, context.profile_data, rule_id)
                selected = context.configuration_data
                from ..configurations._context import srx_configuration_root
                configuration = None if selected is None else srx_configuration_root(
                    selected['configuration_id'], selected['effective_values'])
                roots = graph.candidate_roots({"project": project,
                    "configuration": configuration}, identity, rule_id=rule_id)
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


def formal_findings(documents, records, checked, profile, resources, *, configuration=None,
                    approval_contexts=()):
    findings, identities = [], []
    contexts = {c.requirement_id: c for c in approval_contexts}
    for record in records:
        value = record.data
        if (record.identity.id not in checked or value["artifact_type"] != "requirement"
                or value["maturity"] not in ("in_review", "approved")):
            continue
        identities.append(record.identity.id)
        supplied = contexts.pop(record.identity.id, None)
        projections = {} if supplied is None else {key: supplied.data[key]
            for key in ('quality_fields', 'interface_fields')}
        context = ApprovalContext(record.identity.id, documents, profile=profile,
            configuration=(resources.configuration.data if configuration is None else
                           {'project': resources.configuration.data, 'selected': configuration}),
            mode="stored" if value["maturity"] == "approved" else "transition", **projections)
        if supplied is not None and supplied.input_sha256 != context.input_sha256:
            from ..model.errors import ModelError
            raise ModelError('approval_context_binding_mismatch', path=record.path)
        for item in formal_requirement_findings(context):
            diagnostic = item["diagnostic"]
            findings.append({**diagnostic, "reason": item["reason"],
                             "path": diagnostic.get("path") or record.path})
    if contexts:
        from ..model.errors import ModelError
        raise ModelError('approval_context_subject_outside_selection')
    return findings, identities
