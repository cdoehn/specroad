"""Declared-language checks over exact project and presentation selections.

The supplied model is immutable but not proof of a complete on-disk project.
No detector, trace closure, query execution or implicit file access occurs here.
"""
from dataclasses import dataclass
from types import MappingProxyType

from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from ..model.language_policy import LanguagePolicy, LanguagePolicyError
from ..model.language_registry import LanguageRegistry
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



def _digest(value, reason):
    if type(value) is not str or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ContainerLanguageError(reason)
    return value


def _ids(values, *, duplicates=False):
    if type(values) not in (list, tuple) or any(type(x) is not str or not x for x in values):
        raise ContainerLanguageError("resolved_identity_list_required")
    if not duplicates and len(set(values)) != len(values):
        raise ContainerLanguageError("duplicate_resolved_identity")
    return tuple(values)


@dataclass(frozen=True)
class ResolvedRequirementScope:
    """Supplied applicability result, not evaluated or authenticated here.

    IDs may include historical requirements; project filtering is independent.
    The configuration hash binds the exact supplied configuration artifact.
    """
    model_sha256: str
    configuration_id: str
    configuration_sha256: str
    requirement_ids: tuple
    complete: bool = True

    def __post_init__(self):
        _digest(self.model_sha256, "invalid_scope_model_hash")
        _digest(self.configuration_sha256, "invalid_scope_configuration_hash")
        if type(self.configuration_id) is not str or not self.configuration_id:
            raise ContainerLanguageError("scope_configuration_id_required")
        if self.complete is not True:
            raise ContainerLanguageError("incomplete_requirement_scope")
        object.__setattr__(self, "requirement_ids", _ids(self.requirement_ids))


@dataclass(frozen=True)
class QueryRows:
    """A complete resolved display selection bound to one block occurrence.

    Rows preserve order and duplication. This does not execute SRX, authenticate
    an external resolver, or infer artifact IDs from text or rendered cells.
    """
    model_sha256: str
    block_id: str
    occurrence_path: tuple
    artifact_ids: tuple
    configuration_sha256: str | None = None
    complete: bool = True

    def __post_init__(self):
        _digest(self.model_sha256, "invalid_query_model_hash")
        if type(self.block_id) is not str or not self.block_id:
            raise ContainerLanguageError("query_block_id_required")
        object.__setattr__(self, "occurrence_path", _ids(self.occurrence_path))
        object.__setattr__(self, "artifact_ids", _ids(self.artifact_ids, duplicates=True))
        if self.configuration_sha256 is not None:
            _digest(self.configuration_sha256, "invalid_query_configuration_hash")
        if self.complete is not True:
            raise ContainerLanguageError("incomplete_query_rows")


def _membership(model, values, scope):
    if scope is None:
        return {key for key,v in values.items() if v["artifact_type"] == "requirement"}, None
    if type(scope) is not ResolvedRequirementScope or scope.model_sha256 != model.sha256:
        raise ContainerLanguageError("stale_or_invalid_requirement_scope")
    config = values.get(scope.configuration_id)
    if (config is None or config["artifact_type"] != "configuration"
            or canonical_json_sha256(config) != scope.configuration_sha256):
        raise ContainerLanguageError("configuration_scope_mismatch")
    for key in scope.requirement_ids:
        if key not in values or values[key]["artifact_type"] != "requirement":
            raise ContainerLanguageError("invalid_scope_requirement")
    return set(scope.requirement_ids), {"configuration_id": scope.configuration_id,
        "configuration_sha256": scope.configuration_sha256}


def _query_index(model, values, rows, configuration):
    if type(rows) not in (list, tuple):
        raise ContainerLanguageError("resolved_query_rows_required")
    result = {}
    expected_hash = None if configuration is None else configuration["configuration_sha256"]
    for row in rows:
        if type(row) is not QueryRows or row.model_sha256 != model.sha256 or row.configuration_sha256 != expected_hash:
            raise ContainerLanguageError("stale_or_invalid_query_rows")
        key = (row.block_id, row.occurrence_path)
        if key in result:
            raise ContainerLanguageError("duplicate_query_occurrence")
        if row.block_id not in values or values[row.block_id]["artifact_type"] != "content_block":
            raise ContainerLanguageError("query_block_missing")
        if any(x not in values for x in row.artifact_ids):
            raise ContainerLanguageError("query_result_artifact_missing")
        result[key] = row
    return result

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


def project_containers(model, *, scope=None):
    """Project S.5 set excludes the three historical lifecycle states only."""
    values = _model(model)
    members, configuration = _membership(model, values, scope)
    ids = sorted(key for key in members if values[key]["maturity"] not in {"retired", "superseded", "rejected"})
    return [{"container_kind": "project", "container_id": None, "occurrence_path": [],
             "requirement_ids": ids, "mixed_languages_override": None,
             "model_sha256": model.sha256, "configuration": configuration}]


def document_containers(model, root_id, *, scope=None, query_rows=()):
    """Resolve actual presentation edges and explicit, bound query selections.

    Every occurrence is evaluated independently; IDs count once per container.
    The configuration resolver owns applicability decisions, not this traversal.
    """
    values = _model(model)
    members, configuration = _membership(model, values, scope)
    rows = _query_index(model, values, query_rows, configuration)
    if type(root_id) is not str or root_id not in values or values[root_id]["artifact_type"] not in {"document", "section"}:
        raise ContainerLanguageError("presentation_container_required")
    stack = [("enter", root_id, ())]
    frames, complete, used = [], [], set()
    active = set()
    while stack:
        action, key, path = stack.pop()
        if action == "leave":
            frame = frames.pop()
            active.remove(key)
            frame["requirement_ids"] = sorted(frame["requirement_ids"])
            if frames:
                frames[-1]["requirement_ids"].update(frame["requirement_ids"])
            continue
        value = values[key]
        kind = value["artifact_type"]
        if kind in {"document", "section"}:
            if key in active:
                raise ContainerLanguageError("presentation_cycle", pointer="/relations")
            active.add(key)
            frame = {"container_kind": kind, "container_id": key,
                "occurrence_path": list(path), "requirement_ids": set(),
                "mixed_languages_override": value.get("language_policy_override", {}).get("mixed_languages"),
                "model_sha256": model.sha256, "configuration": configuration}
            frames.append(frame); complete.append(frame)
            stack.append(("leave", key, path))
            for edge in reversed(_children(value)):
                stack.append(("enter", edge["target"], path + (edge["relation_id"],)))
        elif kind == "content_block":
            block = value["block_kind"]
            if block == "artifact_ref":
                target = _block_target(value)["target"]
                if target in members:
                    frames[-1]["requirement_ids"].add(target)
            elif block == "include_document":
                edge = _block_target(value)
                stack.append(("enter", edge["target"], path + (edge["relation_id"],)))
            elif block == "query" or (block == "table" and value["payload"].get("source") == "view"):
                query_key = (key, path)
                if query_key not in rows:
                    raise ContainerLanguageError("presentation_resolver_required", pointer="/payload")
                used.add(query_key)
                ids = rows[query_key].artifact_ids
                if not ids and value["payload"].get("empty_policy") == "error":
                    raise ContainerLanguageError("empty_query_display", pointer="/payload/empty_policy")
                # An applicable requirement absent from the rendered rows is not
                # invented. Nonrequirement rows and their trace edges do not count.
                if any(values[x]["artifact_type"] == "requirement" and x not in members for x in ids):
                    raise ContainerLanguageError("query_scope_mismatch")
                frames[-1]["requirement_ids"].update(x for x in ids if x in members)
            # Prose, admonitions, code snippets and literal table cells are data.
    if used != set(rows):
        raise ContainerLanguageError("unused_query_observation")
    return complete


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
