"""Structural presentation projection, not a trace closure or text scan."""
from ..model.canonical import canonical_json_sha256
from .container_values import (ContainerLanguageError, ResolvedRequirementScope, QueryRows, _model)

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


