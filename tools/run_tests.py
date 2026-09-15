"""Run the actual development suite and optionally retain its bound JSON evidence."""

import argparse
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

import unittest
from verification import (CatalogError, bind_tests, json_bytes, load_catalog, make_report,
                          evidence_target, observe_suite, platform_identity, publish_report, sha256, source_identity)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--expected-tests", type=int)
    args = parser.parse_args(argv)
    try:
        if args.expected_tests is not None and args.expected_tests <= 0:
            raise CatalogError("Expected test count must be positive")
        if args.evidence is not None:
            evidence_target(args.evidence, ROOT)
        catalog = load_catalog(ROOT / "verification")
        # Integrity binding of the normative input, not a documentation test.
        specification = ROOT / "docs/specification/SpecRoad_Spezifikation.md"
        if sha256(specification.read_bytes()) != catalog.specification_sha256:
            raise CatalogError("Catalog is not bound to the current specification bytes")
        identity = source_identity(ROOT)
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
        discovered = bind_tests(catalog, suite)
        if args.expected_tests is not None and len(discovered) != args.expected_tests:
            raise CatalogError("Discovered suite size differs from the expected behavior gate")
        runtime = platform_identity()
        binding = {"run_id": str(uuid.uuid4()), "tool_build_sha256": identity,
                   "platform_sha256": sha256(json_bytes(runtime)),
                   "configuration_sha256": sha256(json_bytes({"suite": "unittest-discover-v1",
                       "stdin": "closed", "test_timeout": None, "suite_timeout": None}))}
        result = observe_suite(suite)
        if (source_identity(ROOT) != identity
                or sha256(specification.read_bytes()) != catalog.specification_sha256):
            raise CatalogError("Inputs changed during test execution; no current pass evidence")
        report = make_report(catalog, binding, result, discovered)
        report["runtime"] = runtime
        if args.evidence is not None:
            publish_report(args.evidence, ROOT, report)
        print(json.dumps({"tests_run": report["tests_run"], "suite_passed": report["suite_passed"],
                          "requirement_counts": report["requirement_counts"],
                          "release_approved": False}, sort_keys=True))
        return 0 if report["suite_passed"] else 1
    except (CatalogError, OSError) as error:
        print("Development verification failed: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
