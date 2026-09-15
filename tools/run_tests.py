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
                          observe_suite, platform_identity, sha256, source_identity)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--expected-tests", type=int)
    args = parser.parse_args(argv)
    try:
        if args.evidence is not None and (args.evidence.exists() or args.evidence.is_symlink()):
            raise CatalogError("Existing evidence is never overwritten")
        catalog = load_catalog(ROOT / "verification")
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
        if source_identity(ROOT) != identity:
            raise CatalogError("Inputs changed during test execution; no current pass evidence")
        report = make_report(catalog, binding, result, discovered)
        report["runtime"] = runtime
        if args.evidence is not None:
            args.evidence.parent.mkdir(parents=True, exist_ok=True)
            with args.evidence.open("xb") as stream:
                stream.write(json_bytes(report) + b"\n")
        print(json.dumps({"tests_run": report["tests_run"], "suite_passed": report["suite_passed"],
                          "requirement_counts": report["requirement_counts"],
                          "release_approved": False}, sort_keys=True))
        return 0 if report["suite_passed"] else 1
    except (CatalogError, OSError) as error:
        print("Development verification failed: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
