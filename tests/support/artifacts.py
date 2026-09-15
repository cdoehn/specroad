"""Common artifact envelopes, intentionally NOT complete per-type fixtures."""

import json


def common_artifact(kind="goal", prefix="GOAL", **overrides):
    value = {"schema_version": "0.2.0", "id": "SR-" + prefix + "-" + "0" * 26,
             "id_scheme": "random128-v1", "artifact_type": kind, "title": "Sample",
             "maturity": "draft", "revision": 1, "created_at": "2026-01-01T00:00:00Z",
             "updated_at": "2026-01-01T00:00:00Z",
             "created_by": {"actor_type": "human", "actor_id": "test-author"},
             "updated_by": {"actor_type": "human", "actor_id": "test-author"},
             "relations": [], "extensions": {}}
    if kind in ("requirement", "document", "term"):
        value["language"] = "de-DE"
    value.update(overrides)
    return value


def artifact_bytes(value):
    return json.dumps(value, ensure_ascii=False).encode("utf-8")
