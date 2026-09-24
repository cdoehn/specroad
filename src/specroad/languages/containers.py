"""Declared-language checks over exact project and presentation selections.

The supplied model is immutable but not proof of a complete on-disk project.
No detector, trace closure, query execution or implicit file access occurs here.
"""
from dataclasses import dataclass
from types import MappingProxyType

from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from ..model.language_policy import LanguagePolicy, LanguagePolicyError
from ..graph.relation_values import SourceRelations
from ..graph.references import RelationReferences
from ..storage.domain_artifact import DomainArtifact
from ..storage.record_artifact import RecordArtifact
from ..cli.option_values import policy_exit_code
from .policy import evaluate_language
from ._severity import failure_options


class ContainerLanguageError(ModelError):
    """Invalid or incomplete model selection, not a linguistic finding."""


@dataclass(frozen=True, init=False)
class ContainerModel:
    """An explicitly supplied, source-bound model. No project completeness claim."""
    _records: object
    sha256: str

    def __init__(self, sources):
        if type(sources) not in (list, tuple):
            raise ContainerLanguageError("container_sources_required")
        records = []
        for raw in sources:
            if type(raw) is not bytes:
                raise ContainerLanguageError("container_source_bytes_required")
            record = SourceRelations(raw)
            kind = record.identity.artifact_type
            if kind == "requirement":
                DomainArtifact(raw, expected_type=kind)
            elif kind in {"document", "section", "content_block", "view", "configuration"}:
                RecordArtifact(raw, expected_type=kind)
            records.append(record)
        RelationReferences(records)
        ordered = sorted(records, key=lambda r: r.identity.id)
        object.__setattr__(self, "_records", MappingProxyType({r.identity.id: r for r in ordered}))
        object.__setattr__(self, "sha256", canonical_json_sha256([r.data for r in ordered]))

    def values(self):
        """Return caller-owned values, never mutation handles into this model."""
        return {key: value.data for key, value in self._records.items()}


def _model(model):
    if type(model) is not ContainerModel:
        raise ContainerLanguageError("container_model_required")
    return model.values()


def _children(value):
    return sorted((r for r in value["relations"] if r["type"] == "contains"),
                  key=lambda r: (r["position"], r["target"], r["relation_id"]))


def _block_target(value):
    references = [r for r in value["relations"] if r["type"] == "references"]
    if len(references) != 1:
        raise ContainerLanguageError("presentation_reference_required", pointer="/relations")
    return references[0]


def project_containers(model):
    """Project S.5 set excludes the three historical lifecycle states only."""
    values = _model(model)
    ids = sorted(key for key, value in values.items() if value["artifact_type"] == "requirement"
                 and value["maturity"] not in {"retired", "superseded", "rejected"})
    return [{"container_kind": "project", "container_id": None, "occurrence_path": [],
             "requirement_ids": ids, "mixed_languages_override": None,
             "model_sha256": model.sha256, "configuration": None}]


def document_containers(model, root_id):
    """Resolve contains/artifact_ref only; additional resolvers are explicit."""
    values = _model(model)
    if type(root_id) is not str or root_id not in values or values[root_id]["artifact_type"] not in {"document", "section"}:
        raise ContainerLanguageError("presentation_container_required")
    # Each occurrence has a separate local set. Parent sets include descendants.
    stack = [("enter", root_id, (), ())]
    frames, complete = [], []
    active = set()
    while stack:
        action, key, path, _ = stack.pop()
        if action == "leave":
            frame = frames.pop()
            active.remove(key)
            frame["requirement_ids"] = sorted(frame["requirement_ids"])
            complete.append(frame)
            if frames:
                frames[-1]["requirement_ids"].update(frame["requirement_ids"])
            continue
        value = values[key]
        kind = value["artifact_type"]
        if kind in {"document", "section"}:
            if key in active:
                raise ContainerLanguageError("presentation_cycle", pointer="/relations")
            active.add(key)
            frames.append({"container_kind": kind, "container_id": key,
                "occurrence_path": list(path), "requirement_ids": set(),
                "mixed_languages_override": value.get("language_policy_override", {}).get("mixed_languages"),
                "model_sha256": model.sha256, "configuration": None})
            stack.append(("leave", key, path, ()))
            for edge in reversed(_children(value)):
                stack.append(("enter", edge["target"], path + (edge["relation_id"],), ()))
        elif kind == "content_block":
            block = value["block_kind"]
            if block == "artifact_ref":
                target = _block_target(value)["target"]
                if values[target]["artifact_type"] == "requirement":
                    frames[-1]["requirement_ids"].add(target)
            elif block in {"query", "include_document"} or (block == "table" and value["payload"].get("source") == "view"):
                raise ContainerLanguageError("presentation_resolver_required", pointer="/payload")
            # Prose, admonitions, code snippets and literal table cells are data.
    complete.reverse()
    return complete


def _evaluate(model, selections, *, policy, registry, fail_on, strict):
    if type(policy) is not LanguagePolicy:
        raise LanguagePolicyError("language_policy_required")
    values = _model(model)
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


def evaluate_project_languages(model, *, policy, registry, fail_on="error", strict=False):
    return _evaluate(model, project_containers(model), policy=policy, registry=registry,
                     fail_on=fail_on, strict=strict)[0]


def evaluate_document_languages(model, root_id, *, policy, registry, fail_on="error", strict=False):
    return _evaluate(model, document_containers(model, root_id), policy=policy, registry=registry,
                     fail_on=fail_on, strict=strict)
