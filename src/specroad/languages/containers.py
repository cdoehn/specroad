"""Evaluate declared Requirement-language mixing on resolved container sets.

Inputs come from the immutable model/presentation boundary, not a text detector.
The result is not a complete physical-project inventory or approval.
"""
from ..model.language_policy import LanguagePolicy, LanguagePolicyError
from ..model.language_registry import LanguageRegistry
from ..cli.option_values import policy_exit_code
from .policy import evaluate_language
from ._severity import failure_options
from .container_values import (ContainerModel, ContainerLanguageError, ResolvedRequirementScope, QueryRows, _model)
from ._container_projection import project_containers, document_containers

def _evaluate(model, selections, *, policy, registry, fail_on, strict):
    if type(policy) is not LanguagePolicy:
        raise LanguagePolicyError("language_policy_required")
    values = _model(model)
    # Even an empty selection cannot turn a malformed registry binding green.
    if type(registry) is not LanguageRegistry:
        raise LanguagePolicyError("language_registry_required")
    LanguageRegistry(registry.source_bytes, expected_sha256=registry.sha256, expected_version=registry.version)
    options = failure_options(fail_on, strict)
    data = policy.data
    observed = {}
    reports = []
    for selection in selections:
        tags, keys, diagnostics, declarations = set(), set(), [], []
        hard_error = False
        for key in selection["requirement_ids"]:
            language = values[key]["language"]
            if language not in observed:
                observed[language] = evaluate_language(language, policy=policy, registry=registry, fail_on=fail_on, strict=strict)
            finding = observed[language]
            assessment = finding["assessment"]
            canonical = assessment.get("canonical")
            tags.add(canonical if canonical is not None else language)
            comparison = finding["comparison_key"]
            if comparison is not None:
                keys.add(comparison)
            hard_error = hard_error or finding["exit_code"] == 3
            diagnostics.extend({**d, "requirement_id": key} for d in finding["diagnostics"])
            declarations.append({"requirement_id": key, "declared_language": language,
                                 "normalized_tag": canonical, "comparison_key": comparison})
        action = selection["mixed_languages_override"] or data["mixed_languages"][selection["container_kind"]]
        mixed = len(keys) > 1
        tags = sorted(tags, key=lambda x: (x.lower(), x))
        if mixed and action != "allow":
            diagnostics.append({"code": "SRV180", "severity": action, "reason": "mixed_requirement_languages",
                "container_kind": selection["container_kind"], "container_id": selection["container_id"],
                "occurrence_path": list(selection["occurrence_path"]), "tags": tags,
                "requirement_ids": list(selection["requirement_ids"]), "comparison": data["mixed_languages"]["comparison"]})
        reports.append({**selection, "format_version": 1, "tags": tags, "comparison_keys": sorted(keys),
            "declarations": declarations, "mixed": mixed, "action": action,
            "policy": policy.data, "policy_sha256": policy.sha256, "diagnostics": diagnostics,
            "exit_code": 3 if hard_error else policy_exit_code([d["severity"] for d in diagnostics], options),
            "validation_scope": "resolved_container_requirements_only", "project_complete": False,
            "atomic_snapshot": False, "approval_granted": False, "language_detection_performed": False})
    return reports


def evaluate_project_languages(model, *, policy, registry, fail_on="error", strict=False, scope=None):
    return _evaluate(model, project_containers(model, scope=scope), policy=policy, registry=registry,
                     fail_on=fail_on, strict=strict)[0]


def evaluate_document_languages(model, root_id, *, policy, registry, fail_on="error", strict=False, scope=None, query_rows=()):
    return _evaluate(model, document_containers(model, root_id, scope=scope, query_rows=query_rows), policy=policy, registry=registry,
                     fail_on=fail_on, strict=strict)
