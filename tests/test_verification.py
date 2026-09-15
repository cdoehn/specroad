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


class CatalogRobustnessTests(unittest.TestCase):
    def test_missing_required_primary_case_is_not_a_complete_catalog(self):
        files = fixture_files(manifest())
        index = json.loads(files['catalog.json'])
        index['complete'] = True
        index['required_test_case_ids'] = ['SR-TC-0001', 'SR-TC-0002']
        files['catalog.json'] = json_bytes(index)
        with temporary_project(files) as root, self.assertRaises(CatalogError):
            load_catalog(root)

    def test_missing_or_extra_manifest_is_rejected_without_mutation(self):
        files = fixture_files(manifest())
        with temporary_project(files) as root:
            extra = root / 'requirements/SR-TC-0002.json'
            extra.write_bytes(files['requirements/SR-TC-0001.json'])
            before = tree_state(root)
            with self.assertRaises(CatalogError):
                load_catalog(root)
            self.assertEqual(tree_state(root), before)
            extra.unlink()
            (root / 'requirements/SR-TC-0001.json').unlink()
            with self.assertRaises(CatalogError):
                load_catalog(root)

    def test_duplicate_json_keys_wrong_spec_and_boolean_versions_are_invalid(self):
        files = fixture_files(manifest())
        with temporary_project(files) as root:
            path = root / 'requirements/SR-TC-0001.json'
            for raw in (b'{"x":1,"x":2}',
                        json_bytes({**manifest(), 'specification_sha256': 'f' * 64}),
                        json_bytes({**manifest(), 'test_case_format_version': True})):
                path.write_bytes(raw)
                with self.assertRaises(CatalogError):
                    load_catalog(root)

    def test_linked_manifest_is_not_read_as_owned_evidence(self):
        import os
        files = fixture_files(manifest())
        with temporary_project(files) as root, temporary_project({'external': b'keep'}) as outside:
            path = root / 'requirements/SR-TC-0001.json'
            path.unlink()
            os.symlink(outside / 'external', path)
            before = tree_state(outside)
            with self.assertRaises(CatalogError):
                load_catalog(root)
            self.assertEqual(tree_state(outside), before)

    def test_required_metadata_and_human_oracles_cannot_be_satisfied_with_dummy_bindings(self):
        for field in ('primary_verification_id', 'oracle', 'fixture_ids', 'expected_exit_codes', 'required_environment'):
            data = manifest()
            del data[field]
            with self.subTest(field=field), self.assertRaises(CatalogError):
                as_case(data)
        for kind in ('manual_presentation', 'pending'):
            data = manifest()
            data['oracle']['kind'] = kind
            with self.assertRaises(CatalogError):
                as_case(data)
        with self.assertRaises(CatalogError):
            as_case(manifest(test_ids=[]))

    def test_open_case_without_tests_stays_open_even_in_green_suite(self):
        data = manifest(state='open', test_ids=[])
        data['method'] = 'pending'
        data['oracle'] = {'kind': 'pending'}
        case = as_case(data)
        evidence = case_evidence(case, BINDING, {'unrelated.test': 'passed'})
        self.assertEqual(evidence['status'], 'open')
        self.assertEqual(evidence['test_outcomes'], {})

    def test_case_snapshot_is_not_mutated_by_caller_or_report_access(self):
        data = manifest()
        case = as_case(data)
        data['test_ids'].clear()
        exposed = case.data
        exposed['test_ids'].clear()
        self.assertEqual(case.data['test_ids'], ['test.actual'])
        self.assertEqual(case_evidence(case, BINDING, {'test.actual': 'passed'})['status'], 'passed')

    def test_missing_or_conflicting_binding_cannot_create_passed_evidence(self):
        case = as_case(manifest())
        invalid = ({}, {**BINDING, 'tool_build_sha256': None}, {**BINDING, 'run_id': 'unknown'},
                   {**BINDING, 'manifest_sha256': 'f' * 64})
        for binding in invalid:
            with self.subTest(binding=binding), self.assertRaises(CatalogError):
                case_evidence(case, binding, {'test.actual': 'passed'})

    def test_stale_manifest_spec_build_platform_configuration_or_run_is_not_passed(self):
        from verification import current_evidence_status
        case = as_case(manifest())
        evidence = case_evidence(case, BINDING, {'test.actual': 'passed'})
        self.assertEqual(current_evidence_status(case, BINDING, evidence), 'passed')
        for field in ('manifest_sha256', 'specification_sha256', 'tool_build_sha256', 'platform_sha256',
                      'configuration_sha256', 'run_id', 'requirement_id'):
            changed = {**evidence, field: 'different'}
            self.assertEqual(current_evidence_status(case, BINDING, changed), 'stale')

    def test_claimed_pass_with_missing_extra_or_nonpassing_results_is_invalid(self):
        from verification import current_evidence_status
        case = as_case(manifest())
        evidence = case_evidence(case, BINDING, {'test.actual': 'passed'})
        for outcomes in ({}, {'test.actual': True}, {'test.actual': 'skipped'},
                         {'test.actual': 'passed', 'extra': 'passed'}):
            changed = {**evidence, 'test_outcomes': outcomes}
            self.assertEqual(current_evidence_status(case, BINDING, changed), 'invalid')

    def test_subtest_skip_and_failure_never_produce_parent_pass(self):
        class Behavior(unittest.TestCase):
            def test_skipped_subtest(self):
                with self.subTest(part=1):
                    self.skipTest('controlled skip')
                with self.subTest(part=2):
                    self.assertEqual(2, 2)
            def test_failed_subtest(self):
                with self.subTest(part=1):
                    self.fail('controlled failure')
        result = observe_suite(unittest.defaultTestLoader.loadTestsFromTestCase(Behavior), stream=io.StringIO())
        self.assertEqual(sorted(result.outcomes.values()), ['failed', 'skipped'])

    def test_expected_failure_unexpected_success_and_setup_error_are_not_passed(self):
        class Behavior(unittest.TestCase):
            @unittest.expectedFailure
            def test_expected(self):
                self.fail('controlled failure')
            @unittest.expectedFailure
            def test_unexpected(self):
                self.assertEqual(2, 2)
        class BrokenSetup(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                raise RuntimeError('controlled setup error')
            def test_never_runs(self):
                raise AssertionError('must not execute')
        for cls in (Behavior, BrokenSetup):
            suite = unittest.defaultTestLoader.loadTestsFromTestCase(cls)
            ids = tuple(test.id() for test in suite)
            catalog = Catalog((), SPEC_HASH, 'e' * 64, False)
            result = observe_suite(suite, stream=io.StringIO())
            report = make_report(catalog, BINDING, result, ids)
            self.assertFalse(report['suite_passed'])
            self.assertFalse(report['release_approved'])

    def test_zero_executions_cannot_be_green(self):
        result = observe_suite(unittest.TestSuite(), stream=io.StringIO())
        report = make_report(Catalog((), SPEC_HASH, 'e' * 64, False), BINDING, result, ())
        self.assertFalse(report['suite_passed'])

    def test_current_report_publication_is_exclusive_and_preserves_source_inputs(self):
        from verification import publish_report
        with temporary_project({'src/source': b'keep'}) as root:
            target = root / 'build/evidence.json'
            report = {'report_format_version': 1, 'release_approved': False}
            publish_report(target, root, report)
            self.assertEqual(json.loads(target.read_bytes()), report)
            with self.assertRaises(CatalogError):
                publish_report(target, root, {'replaced': True})
            with self.assertRaises(CatalogError):
                publish_report(root / 'src/new.py', root, report)
            with self.assertRaises(CatalogError):
                publish_report(root / '.git/fake', root, report)
            self.assertEqual((root / 'src/source').read_bytes(), b'keep')
            self.assertFalse((root / 'src/new.py').exists())

    def test_linked_output_parent_cannot_redirect_evidence(self):
        import os
        from verification import publish_report
        with temporary_project() as root, temporary_project({'valuable': b'keep'}) as outside:
            before = tree_state(outside)
            os.symlink(outside, root / 'build', target_is_directory=True)
            with self.assertRaises(CatalogError):
                publish_report(root / 'build/report.json', root, {'run': 'new'})
            self.assertEqual(tree_state(outside), before)

    def test_build_identity_tracks_real_source_not_ignored_output_or_editable_siblings(self):
        from verification import source_identity
        with temporary_project({'src/specroad/__init__.py': b'value = 1\n', 'tests/test_case.py': b'# test\n',
                                'tools/runner.py': b'# runner\n', 'verification/manifest.json': b'{}',
                                'pyproject.toml': b'[project]\n'}) as root:
            first = source_identity(root)
            (root / 'build').mkdir()
            (root / 'build/evidence.json').write_bytes(b'prior output')
            (root / 'src/local.egg-info').mkdir()
            (root / 'src/local.egg-info/metadata').write_bytes(b'local')
            self.assertEqual(source_identity(root), first)
            (root / 'src/specroad/__init__.py').write_bytes(b'value = 2\n')
            self.assertNotEqual(source_identity(root), first)
