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
