"""Developer verification: evidence responsibilities."""

import uuid
from .common import CatalogError, _hash


def validate_binding(binding):
    keys = {"run_id", "tool_build_sha256", "platform_sha256", "configuration_sha256"}
    if not isinstance(binding, dict) or set(binding) != keys:
        raise CatalogError("Evidence needs a complete explicit current-run binding")
    try:
        identifier = uuid.UUID(binding["run_id"])
    except (ValueError, TypeError, AttributeError) as error:
        raise CatalogError("Invalid evidence run identity") from error
    if identifier.version != 4 or str(identifier) != binding["run_id"]:
        raise CatalogError("Invalid evidence run identity")
    if not all(_hash(binding[key]) for key in keys - {"run_id"}):
        raise CatalogError("Evidence has missing or invalid input hashes")


def _case_status(data, statuses):
    allowed = {"passed", "failed", "error", "unexpected_success", "expected_failure", "skipped",
               "running", "not_run"}
    if not isinstance(statuses, dict) or set(statuses) != set(data["test_ids"]) or any(
        not isinstance(value, str) or value not in allowed for value in statuses.values()
    ):
        raise CatalogError("Invalid actual test outcomes")
    if any(value in ("failed", "error", "unexpected_success") for value in statuses.values()):
        return "failed"
    if not statuses or any(value != "passed" for value in statuses.values()):
        return "open"
    if data["implementation_status"] != "implemented":
        return "partial"
    return "passed"


def case_evidence(case, binding, outcomes):
    validate_binding(binding)
    data = case.data
    statuses = {name: outcomes.get(name, "not_run") for name in data["test_ids"]}
    return {
        "evidence_kind": data["evidence_kind"], "test_case_id": data["test_case_id"],
        "requirement_id": data["requirement_id"], "specification_sha256": data["specification_sha256"],
        "manifest_sha256": case.manifest_sha256, **binding,
        "test_outcomes": statuses, "status": _case_status(data, statuses),
    }


def current_evidence_status(case, binding, evidence):
    """Compare trusted local evidence with *current* inputs; never trust a pass label.

    Digests do not authenticate an author. This is not a signature verifier or
    product release approval, and is not used to import arbitrary external reports.
    """
    validate_binding(binding)
    expected = case_evidence(case, binding, {})
    if not isinstance(evidence, dict) or set(evidence) != set(expected):
        return "invalid"
    for name in set(expected) - {"test_outcomes", "status"}:
        if evidence[name] != expected[name]:
            return "stale"
    try:
        status = _case_status(case.data, evidence["test_outcomes"])
    except CatalogError:
        return "invalid"
    return status if evidence["status"] == status else "invalid"


def make_report(catalog, binding, result, discovered_ids):
    cases = [case_evidence(case, binding, result.outcomes) for case in catalog.cases]
    suite_passed = (bool(discovered_ids) and len(discovered_ids) == len(set(discovered_ids))
                    and result.wasSuccessful() and result.testsRun == len(discovered_ids)
                    and set(result.outcomes) == set(discovered_ids)
                    and all(value == "passed" for value in result.outcomes.values()))
    counts = {name: sum(case["status"] == name for case in cases)
              for name in ("open", "partial", "failed", "passed")}
    return {
        "report_format_version": 1, "purpose": "development_behavior_evidence", **binding,
        "catalog_sha256": catalog.catalog_sha256, "specification_sha256": catalog.specification_sha256,
        "catalog_complete": catalog.complete, "tests_run": result.testsRun,
        "suite_passed": suite_passed, "test_outcomes": dict(result.outcomes),
        "requirement_counts": counts, "cases": cases,
        "release_approved": False, "release_gate": "not_evaluated",
    }


