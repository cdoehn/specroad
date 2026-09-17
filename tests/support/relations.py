"""Owned relation fixtures. No stored approval or external authenticity claim."""

from specroad.model.artifact_types import artifact_type
from specroad.model.identity_tokens import encode128
from .artifacts import common_artifact, artifact_bytes


def rid(number=1):
    return "REL-" + encode128(number.to_bytes(16, "big"))


def aid(kind="requirement", number=1, project="SR"):
    return project + "-" + artifact_type(kind).prefix + "-" + encode128(number.to_bytes(16, "big"))


def external(**changes):
    result = {"source_system": "reqif", "source_document": "supplier.reqif", "external_id": "_req-10"}
    result.update(changes)
    return result


def edge(kind="refines", target=None, number=1, **changes):
    result = {"relation_id": rid(number), "id_scheme": "random128-v1", "type": kind,
              "target": target or aid(number=2), "external_identities": [], "extensions": {}}
    if kind == "contains": result["position"] = 0
    result.update(changes)
    return result


def artifact(kind="requirement", number=1, relations=(), project="SR", **changes):
    return common_artifact(kind, artifact_type(kind).prefix, id=aid(kind, number, project),
                           relations=list(relations), **changes)
