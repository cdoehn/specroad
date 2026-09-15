"""Owned synthetic field fixtures, never claims of genuine review or evidence."""

from .artifacts import common_artifact
from .domain import relation

PREFIXES = {"source": "SRC", "verification": "VER", "test": "TEST", "evidence": "EVD", "baseline": "BASE",
            "proposal": "PROP", "issue": "ISSUE", "document": "DOC", "section": "SEC", "content_block": "BLOCK",
            "view": "VIEW", "code_ref": "CODE", "relation_review": "RREV", "configuration": "CFG"}


def ref(prefix="REQ", token="0"):
    return "SR-" + prefix + "-" + token * 26


def srx():
    return {"language": "srx", "version": "1.0", "expression": {"op": "literal", "value": True}}


def record_value(kind="document", **overrides):
    fields = {
        "source": {"source_kind": "document", "locator": "attachments/source.txt", "captured_at": "2026-01-01T00:00:00Z"},
        "verification": {"method": "inspection", "subjects": [ref()], "preconditions": [], "procedure": ["Inspect data"],
                         "oracle": "Required fields exist", "evidence_kinds": ["inspection_report"], "dimensions": ["overall"],
                         "evidence_slots": [{"check_id": "overall", "test_id": None, "dimension": "overall"}],
                         "configuration_policy": "bound"},
        "test": {"test_identity": {"external_id": "suite/test-case"}, "test_type": "behavior", "oracle": "Operation is read-only"},
        "evidence": {"maturity": "approved", "evidence_state": "recorded", "result": "failed",
                     "produced_at": "2026-01-01T00:00:00Z", "producer": {"producer_type": "ci", "producer_id": "test-ci"},
                     "tool": {"name": "test-runner", "version": "1.0"}, "environment": {"platform": "synthetic"},
                     "subjects": [{"artifact_id": ref(), "revision": 1, "artifact_sha256": "a" * 64, "verification_context_sha256": "b" * 64}],
                     "origin": "generated_internal", "run_context": {"subject_id": "fixture-product", "subject_state_sha256": "c" * 64,
                            "run_id": "test-ci:run-1", "check_id": "overall", "test_id": None}},
        "baseline": {"maturity": "approved", "baseline_state": "sealed", "baseline_kind": "working",
                     "scope_descriptor": {"scope_kind": "project"}, "manifest": [], "model_root_sha256": "d" * 64},
        "proposal": {"proposal_status": "draft", "content_revision": 1, "content_sha256": "e" * 64,
                     "control_history": [], "base": {"model_root_sha256": "f" * 64}, "change_plan": {"operations": []}, "rationale": "Model a proposed change"},
        "issue": {"description": "Incomplete reference", "issue_status": "open", "owner": "engineering"},
        "document": {"purpose": "Describe requirements", "audience": "reviewer", "document_role": "primary_specification", "render_policy": {}},
        "section": {},
        "content_block": {"block_kind": "prose", "payload": {"markdown": "A short paragraph."}},
        "view": {"scope_descriptor": {"scope_kind": "project"}, "filter": srx(),
                 "columns": [{"source": {"kind": "artifact_field", "pointer": "/title"}, "heading": "Title", "data_type": "string", "format": "plain", "missing": "error"}],
                 "sort": [], "grouping": [], "relation_projections": [], "formats": ["json", "markdown"]},
        "code_ref": {"path": "src/example.py", "reference_kind": "file", "file_sha256": "a" * 64},
        "relation_review": {"maturity": "approved", "review_state": "recorded", "relation_id": "REL-" + "0" * 26,
                            "relation_content_sha256": "a" * 64, "source_context_sha256": "b" * 64, "target_context_sha256": "c" * 64,
                            "reviewer": {"actor_type": "human", "actor_id": "synthetic-reviewer"}, "decision": "rejected"},
        "configuration": {"name": "Linux", "dimensions": [{"name": "platform", "allowed_values": ["linux", "windows"], "default": "linux"}], "selection": {"platform": "linux"}},
    }
    result = common_artifact(kind, PREFIXES[kind]); result.update(fields[kind]); result.update(overrides)
    return result


def block_value(kind):
    payloads = {"prose": {"markdown": "text"}, "artifact_ref": {"render_mode": "summary"},
                "query": {"source": "view", "columns": [{"field": "/title"}], "empty_policy": "omit"},
                "table": {"columns": [{"field": "name"}], "rows": [["sample"]]},
                "admonition": {"level": "warning", "markdown": "Review this."}, "page_break": {},
                "include_document": {"mode": "content"}}
    value = record_value("content_block", block_kind=kind, payload=payloads[kind])
    if kind in ("artifact_ref", "query", "include_document"):
        prefix = {"artifact_ref": "REQ", "query": "VIEW", "include_document": "DOC"}[kind]
        value["relations"] = [relation("references", ref(prefix))]
    return value
