"""Compare already completed gates; this does not distribute or schedule tests."""

import argparse
import json
from pathlib import Path
import sys


class ComparisonError(ValueError):
    pass


def _signature(report):
    if (not isinstance(report, dict) or report.get("report_format_version") != 2
            or report.get("purpose") != "development_behavior_evidence"
            or report.get("suite_passed") is not True):
        raise ComparisonError("Only complete passing development evidence can be compared")
    observation = report.get("observation", {})
    ids = observation.get("nodeids", [])
    aliases = observation.get("nodeid_to_test_id", {})
    outcomes = report.get("test_outcomes", {})
    counts = observation.get("worker_test_counts", {})
    if (not ids or len(ids) != len(set(ids)) or set(aliases) != set(ids)
            or len(set(aliases.values())) != len(ids) or set(outcomes) != set(aliases.values())
            or any(state != "passed" for state in outcomes.values())
            or observation.get("test_outcomes") != outcomes
            or observation.get("suite_passed") is not True or observation.get("errors") != []
            or observation.get("pytest_exit_code") != 0
            or observation.get("tests_run") != len(ids) or report.get("tests_run") != len(ids)
            or not counts or any(type(count) is not int or count < 0 for count in counts.values())
            or sum(counts.values()) != len(ids)):
        raise ComparisonError("Incomplete, inconsistent or nonpassing observation")
    binding_names = ("tool_build_sha256", "specification_sha256", "catalog_sha256", "platform_sha256")
    binding = tuple(report.get(name) for name in binding_names)
    if any(not isinstance(value, str) or len(value) != 64 or
           any(character not in "0123456789abcdef" for character in value) for value in binding):
        raise ComparisonError("Missing current input bindings")
    return binding, tuple(sorted(ids)), tuple(sorted(aliases.items())), tuple(sorted(outcomes.items()))


def compare_reports(reports):
    if len(reports) < 2:
        raise ComparisonError("At least two independent runs are required")
    signatures = [_signature(report) for report in reports]
    run_ids = [report.get("run_id") for report in reports]
    if any(not isinstance(value, str) or not value for value in run_ids) or len(set(run_ids)) != len(run_ids):
        raise ComparisonError("Independent run identities are required")
    if any(signature != signatures[0] for signature in signatures[1:]):
        raise ComparisonError("Collected tests, identities, outcomes or source bindings differ")
    return {"equivalent": True, "runs": len(reports), "tests": reports[0]["tests_run"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", type=Path, nargs="+")
    arguments = parser.parse_args(argv)
    try:
        reports = [json.loads(path.read_text(encoding="utf-8")) for path in arguments.reports]
        print(json.dumps(compare_reports(reports), sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("Test-run comparison failed: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
