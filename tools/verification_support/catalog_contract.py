"""Exact collection and report contracts; no pytest hooks or scheduling."""
from pathlib import Path

from .catalog import load_catalog
from .common import sha256


def collection_contract(catalog, pairs):
    """Check exact IDs, including parametrization; never import or guess an ID."""
    rows = tuple(pairs)
    if any(type(row) not in (tuple, list) for row in rows):
        raise ValueError("Identity pairs must be two-element sequences")
    rows = tuple(tuple(row) for row in rows)
    if any(len(row) != 2 or any(type(v) is not str or not v for v in row) for row in rows):
        raise ValueError("Invalid collected identity pairs")
    nodes = [row[0] for row in rows]
    aliases = [row[1] for row in rows]
    errors = []
    if not nodes:
        errors.append("empty_collection")
    if len(set(nodes)) != len(nodes) or len(set(aliases)) != len(aliases):
        errors.append("ambiguous_test_identity")
    available = set(aliases)
    missing = {case.data["test_case_id"]: sorted(set(case.data["test_ids"]) - available)
               for case in catalog.cases if not set(case.data["test_ids"]) <= available}
    if missing:
        errors.append("unavailable_test_reference")
    return {"collected_tests": len(rows), "nodeid_to_test_id": dict(rows),
            "missing_test_ids": missing, "errors": errors}


def validate_preflight_report(root, report, expected_source):
    """Fail closed on malformed, stale or execution-shaped collection reports."""
    fields = {"format_version", "purpose", "catalog_valid", "tests_run", "full_suite_passed",
              "collected_tests", "nodeid_to_test_id", "missing_test_ids", "errors",
              "source_sha256", "specification_sha256", "catalog_sha256", "collection_exit_code"}
    if (type(report) is not dict or set(report) != fields
            or type(report["format_version"]) is not int or report["format_version"] != 1
            or report["purpose"] != "catalog_collection_preflight"
            or report["catalog_valid"] is not True or report["errors"] != []
            or type(report["tests_run"]) is not int or report["tests_run"] != 0
            or report["full_suite_passed"] is not None
            or type(report["collection_exit_code"]) is not int or report["collection_exit_code"] != 0
            or report["source_sha256"] != expected_source
            or type(report["collected_tests"]) is not int or report["collected_tests"] < 1):
        return False
    catalog = load_catalog(Path(root) / "verification")
    pairs = report["nodeid_to_test_id"]
    if type(pairs) is not dict:
        return False
    checked = collection_contract(catalog, pairs.items())
    return (not checked["errors"] and checked["collected_tests"] == report["collected_tests"]
            and checked["missing_test_ids"] == report["missing_test_ids"]
            and report["catalog_sha256"] == catalog.catalog_sha256
            and report["specification_sha256"] == catalog.specification_sha256
            == sha256((Path(root) / "docs/specification/SpecRoad_Spezifikation.md").read_bytes()))

