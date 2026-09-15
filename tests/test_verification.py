"""Executable catalog/evidence behavior; these are data contracts, not doc tests."""

from dataclasses import replace
import io
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from verification import (Case, Catalog, CatalogError, bind_tests, case_evidence, json_bytes,
                          load_catalog, make_report, observe_suite, sha256, validate_manifest)
from support import temporary_project, tree_state

SPEC_HASH = "a" * 64
BINDING = {"run_id": "9bd58939-7169-402a-a84c-ef7a4d363b19", "tool_build_sha256": "b" * 64,
           "platform_sha256": "c" * 64, "configuration_sha256": "d" * 64}


def manifest(*, state="implemented", test_ids=None):
    return {
        "test_case_format_version": 1, "test_case_id": "SR-TC-0001", "requirement_id": "SR-REQ-0001",
        "specification_sha256": SPEC_HASH, "primary_verification_id": "SR-VER-0001",
        "implementation_status": state, "method": "automated_behavior", "fixture_ids": ["temporary-v1"],
        "preconditions": ["owned temporary file"], "steps": ["execute operation and observe bytes"],
        "oracle": {"kind": "behavior", "contract": "actual file bytes are preserved"},
        "expected_diagnostics": [], "expected_exit_codes": [0], "json_pointers": [],
        "required_environment": {"implementation": "cpython"}, "resources": {"temporary_disk": True},
        "evidence_kind": "specroad-dev-unittest-v1", "test_ids": ["test.actual"] if test_ids is None else test_ids,
        "open_items": [] if state == "implemented" else ["remaining real behavior"],
    }


def as_case(data):
    return Case(validate_manifest(data, SPEC_HASH), sha256(json_bytes(data)))


def fixture_files(data):
    return {
        "catalog.json": json_bytes({"catalog_format_version": 1, "specification_sha256": SPEC_HASH,
                                    "test_case_ids": ["SR-TC-0001"], "complete": False}),
        "fixtures.json": json_bytes({"fixture_format_version": 1, "fixture_ids": ["temporary-v1"]}),
        "requirements/SR-TC-0001.json": json_bytes(data),
    }


class CatalogWorkTests(unittest.TestCase):
    def test_manifest_delivers_requirement_fixture_and_verification_binding(self):
        files = fixture_files(manifest())
        with temporary_project(files) as root:
            before = tree_state(root)
            catalog = load_catalog(root)
            case = catalog.cases[0]
            self.assertEqual(case.data["requirement_id"], "SR-REQ-0001")
            self.assertEqual(case.data["primary_verification_id"], "SR-VER-0001")
            self.assertEqual(case.data["fixture_ids"], ["temporary-v1"])
            self.assertEqual(case.manifest_sha256, sha256(files["requirements/SR-TC-0001.json"]))
            self.assertEqual(tree_state(root), before)

    def test_primary_test_number_must_match_requirement(self):
        data = manifest()
        data["requirement_id"] = "SR-REQ-0002"
        with self.assertRaises(CatalogError):
            as_case(data)

    def test_unknown_fixture_is_not_an_executable_binding(self):
        data = manifest()
        data["fixture_ids"] = ["unknown"]
        with temporary_project(fixture_files(data)) as root:
            with self.assertRaises(CatalogError):
                load_catalog(root)

    def test_binding_selects_only_real_discovered_tests_and_never_imports_strings(self):
        class RealTest(unittest.TestCase):
            def test_operation(self):
                with temporary_project({"kept": b"bytes"}) as root:
                    self.assertEqual((root / "kept").read_bytes(), b"bytes")
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(RealTest)
        test_id = next(iter(suite)).id()
        case = as_case(manifest(test_ids=[test_id]))
        catalog = Catalog((case,), SPEC_HASH, "e" * 64, False)
        self.assertEqual(bind_tests(catalog, suite), (test_id,))
        bad = as_case(manifest(test_ids=["os.system('untrusted')"]))
        with self.assertRaises(CatalogError):
            bind_tests(replace(catalog, cases=(bad,)), suite)

    def test_empty_or_duplicate_discovery_is_not_a_success_gate(self):
        catalog = Catalog((as_case(manifest()),), SPEC_HASH, "e" * 64, False)
        with self.assertRaises(CatalogError):
            bind_tests(catalog, unittest.TestSuite())
        test = unittest.FunctionTestCase(lambda: None)
        with self.assertRaises(CatalogError):
            bind_tests(catalog, unittest.TestSuite([test, test]))

    def test_no_execution_is_not_passed_evidence(self):
        evidence = case_evidence(as_case(manifest()), BINDING, {})
        self.assertEqual(evidence["status"], "open")
        self.assertEqual(evidence["test_outcomes"], {"test.actual": "not_run"})

    def test_partial_implementation_does_not_become_passed(self):
        evidence = case_evidence(as_case(manifest(state="partial")), BINDING, {"test.actual": "passed"})
        self.assertEqual(evidence["status"], "partial")

    def test_actual_operation_produces_bound_evidence_without_release_approval(self):
        class RealTest(unittest.TestCase):
            def test_operation(self):
                with temporary_project({"kept": b"bytes"}) as root:
                    self.assertEqual((root / "kept").read_bytes(), b"bytes")
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(RealTest)
        test_id = next(iter(suite)).id()
        case = as_case(manifest(test_ids=[test_id]))
        catalog = Catalog((case,), SPEC_HASH, "e" * 64, False)
        discovered = bind_tests(catalog, suite)
        result = observe_suite(suite, stream=io.StringIO(), verbosity=0)
        report = make_report(catalog, BINDING, result, discovered)
        self.assertTrue(report["suite_passed"])
        evidence = report["cases"][0]
        self.assertEqual(evidence["status"], "passed")
        self.assertEqual(evidence["manifest_sha256"], case.manifest_sha256)
        self.assertEqual(evidence["tool_build_sha256"], BINDING["tool_build_sha256"])
        self.assertFalse(report["release_approved"])
