"""Owned synthetic field-fold inputs; no filesystem or real approvals."""
from .domain import domain_value
from specroad.model.identity_tokens import encode128


def goal(number=0, **values):
    return domain_value("goal", id="SR-GOAL-" + encode128(number.to_bytes(16, "big")), **values)


def edit(artifact, text, **guards):
    return {"op": "update", "target": artifact["id"],
            **(guards or {"expected_revision": artifact["revision"]}),
            "patch": [{"op": "replace", "path": "/statement", "value": text}]}


def create(artifact):
    return {"op": "create", "artifact": artifact, "result_id": artifact["id"]}


def add_relation(source, target, number=1, kind="supersedes", **changes):
    from .relations import edge
    return {"op":"relation_add", "source":source["id"],
            "relation":edge(kind, target["id"], number, **changes)}


def remove_relation(source, relation, **changes):
    from specroad.model.canonical import canonical_json_sha256
    return {"op":"relation_remove", "source":source["id"],
            "relation_id":relation["relation_id"], "expected_sha256":canonical_json_sha256(relation),
            "reason":"Explicitly remove this relation", **changes}
