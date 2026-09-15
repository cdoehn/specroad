"""Independent minimal domain records; no evidence or approval is implied."""

from .artifacts import common_artifact

PREFIXES = {"goal": "GOAL", "need": "NEED", "capability": "CAP", "requirement": "REQ",
            "scenario": "SCN", "decision": "DEC", "risk": "RISK", "assumption": "ASM",
            "component": "COMP", "interface": "IFC", "release": "REL", "milestone": "MS", "task": "TASK"}


def relation(kind="part_of", target="SR-REL-" + "0" * 26):
    return {"relation_id": "REL-" + "0" * 26, "id_scheme": "random128-v1", "type": kind,
            "target": target, "external_identities": [], "extensions": {}}


def domain_value(kind="goal", **overrides):
    value = common_artifact(kind, PREFIXES[kind])
    fields = {
        "goal": {"statement": "Reduce setup effort.", "owner": "product"},
        "need": {"stakeholder": "operator", "statement": "An offline workspace is needed.", "owner": "product"},
        "capability": {"description": "Offline editing", "owner": "engineering", "implementation_status": "not_started", "verification_plan_status": "not_planned"},
        "requirement": {"requirement_kind": "functional", "normative_force": "must", "statement": "No network connection is required.", "priority": "mandatory", "criticality": "normal", "implementation_status": "not_started", "verification_plan_status": "not_planned"},
        "scenario": {"actors": ["operator"], "trigger": "A project is selected.", "main_flow": ["Read project", "Inspect a requirement"]},
        "decision": {"context": "The project is portable.", "decision": "Store JSON locally.", "rationale": "Offline operation", "owner": "architecture"},
        "risk": {"description": "A device may be unavailable.", "probability": 0.25, "impact": "high", "risk_status": "open", "owner": "operations"},
        "assumption": {"statement": "A filesystem is available.", "validation_status": "pending", "owner": "engineering"},
        "component": {"description": "Data reader", "responsibility": "Read project files", "owner": "engineering", "implementation_status": "not_started"},
        "interface": {"description": "Reader input", "source_component": "SR-COMP-" + "0" * 26, "target_component": "SR-COMP-" + "1" * 26, "owner": "engineering", "implementation_status": "not_started"},
        "release": {"name": "0.2", "objective": "Enable offline authoring.", "readiness_policy": {}},
        "milestone": {"objective": "Implement the reader.", "owner": "engineering", "relations": [relation()]},
        "task": {"description": "Implement the parser.", "owner": "engineering", "implementation_status": "not_started", "verification_plan_status": "not_planned", "done_criteria": ["Invalid input is rejected."]},
    }
    value.update(fields[kind]); value.update(overrides)
    return value


def waiver():
    return {"reason": "Deferred review", "scope_descriptor": {"scope_kind": "explicit"},
            "expiry_condition": "At next release", "human_review_id": "SR-RREV-" + "0" * 26,
            "artifact_sha256": "a" * 64, "configuration_sha256": None}
