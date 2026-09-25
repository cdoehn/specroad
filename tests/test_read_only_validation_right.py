"""Freshness failures and unavailable operational state never permit repair/writes."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from specroad.storage import read_only as reader
from specroad.storage.project import ProjectSource
from specroad.security import ProjectBoundary
from specroad.model.paths import artifact_path
from specroad.validation import ModelGate
from tests.support.artifacts import artifact_bytes
from tests.support.model import put
from tests.support.model_validation import artifact, no_dependencies
from tests.support.read_only import (make_project, profile_resources, literal_policy,
                                     inventory, no_write_attempts)
from tests.support.literal_lint import term
from tests.support.portable import build_distribution
from tests.support.processes import run_python


class ReadOnlyRobustnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir()
        self.value = artifact()
        make_project(self.root, self.value)
        self.path = self.root / artifact_path("goal", self.value["id"], "SR")

    def validate(self, **kw):
        return reader.validate_project_read_only(self.root, profile_resources=profile_resources(),
                                                core_key="core@0.2.0", **kw)

    def gate(self, action):
        def check(c):
            action()
            return c.result()
        return ModelGate("extension:controlled-change", "1", no_dependencies, check)

    def rejected_freshness(self, result):
        self.assertFalse(result.passed)
        self.assertFalse(result.data["freshness_verified"])
        self.assertFalse(result.data["checks_complete"])
        self.assertIsNone(result.data["source_observation_sha256"])
        self.assertIsNone(result.data["validation"])
        self.assertIsNone(result.data["lint"])

    def test_normative_read_does_not_call_write_authorization(self):
        with patch.object(ProjectSource, "require_write_target", side_effect=AssertionError("write authorization")):
            with no_write_attempts():
                self.assertTrue(self.validate().passed)

    def test_diagnosis_opens_neither_configuration_nor_model_bytes(self):
        put(self.root, ".specroad/transactions/test/journal.json", b'not json')
        with patch.object(ProjectBoundary, "read_bytes", side_effect=AssertionError("model read")):
            with no_write_attempts():
                r = reader.diagnose_read_only(self.root)
        self.assertEqual(r.exit_code, 0)
        self.assertTrue(r.data["operational"]["recovery_required"])
        self.assertFalse(r.data["operational"]["journal_contents_loaded"])

    def test_journal_claimed_complete_does_not_authorize_normal_read(self):
        put(self.root, ".specroad/transactions/tx/journal.json", b'{"state":"completed"}')
        before = inventory(self.root)
        with no_write_attempts():
            r = self.validate()
        self.assertEqual(r.exit_code, 5)
        self.assertEqual(inventory(self.root), before)

    def test_unknown_lock_data_is_preserved_without_pid_probe(self):
        put(self.root, ".specroad/lock.json", b'{"pid":9999999,"host":"not-consulted"}')
        before = inventory(self.root)
        with patch.object(os, "kill", side_effect=AssertionError("PID probe")):
            with no_write_attempts():
                r = self.validate()
        self.assertEqual(r.exit_code, 5)
        self.assertIsNone(r.data["operational"]["writer_owner"])
        self.assertEqual(inventory(self.root), before)

    def test_recovery_appearing_during_composition_blocks_model_start(self):
        compose = reader.compose_profiles
        def changing(*a, **kw):
            result = compose(*a, **kw)
            put(self.root, ".specroad/recovery/pending", b"keep")
            return result
        with patch.object(reader, "compose_profiles", changing):
            with patch.object(ProjectSource, "read_normative", side_effect=AssertionError("model started")):
                r = self.validate()
        self.assertEqual(r.exit_code, 5)
        self.assertFalse(r.data["model_loaded"])
        self.assertFalse(r.data["normal_operation_started"])
        self.assertTrue(r.data["operational"]["recovery_required"])

    def test_empty_operational_directory_creation_is_observed(self):
        compose = reader.compose_profiles
        def changing(*a, **kw):
            result = compose(*a, **kw)
            (self.root / ".specroad").mkdir()
            return result
        with patch.object(reader, "compose_profiles", changing):
            r = self.validate()
        self.assertEqual(r.exit_code, 5)
        self.assertFalse(r.data["normal_operation_started"])
        self.rejected_freshness(r)

    def test_configuration_change_during_composition_stops_before_model(self):
        compose = reader.compose_profiles
        def changing(*a, **kw):
            result = compose(*a, **kw)
            p = self.root / "specroad.json"; p.write_bytes(p.read_bytes() + b"\n")
            return result
        with patch.object(reader, "compose_profiles", changing):
            r = self.validate()
        self.assertFalse(r.data["normal_operation_started"])
        self.assertEqual(r.exit_code, 5)
        self.rejected_freshness(r)

    def test_created_source_during_validation_is_not_omitted(self):
        def change():
            a = artifact(number=1)
            put(self.root, artifact_path("goal", a["id"], "SR"), artifact_bytes(a))
        r = self.validate(gates=[self.gate(change)])
        self.assertEqual(r.exit_code, 5)
        self.assertEqual(r.data["diagnostics"][0]["reason"], "read_only_membership_changed")
        self.rejected_freshness(r)

    def test_deleted_source_during_validation_fails(self):
        r = self.validate(gates=[self.gate(lambda: self.path.unlink())])
        self.assertEqual(r.exit_code, 5)
        self.rejected_freshness(r)

    def test_same_size_change_with_restored_mtime_is_not_cached(self):
        original = self.path.read_bytes(); info = self.path.stat()
        changed = original.replace(b'"Sample"', b'"Change"', 1)
        self.assertNotEqual(changed, original)
        self.assertEqual(len(changed), len(original))
        def change():
            self.path.write_bytes(changed)
            os.utime(self.path, ns=(info.st_atime_ns, info.st_mtime_ns))
        r = self.validate(gates=[self.gate(change)])
        self.assertEqual(r.exit_code, 5)
        self.rejected_freshness(r)
        self.assertEqual(self.path.read_bytes(), changed)

    def test_configuration_change_during_validation_invalidates_result(self):
        def change():
            p = self.root / "specroad.json"; p.write_bytes(p.read_bytes() + b" ")
        r = self.validate(gates=[self.gate(change)])
        self.assertEqual(r.exit_code, 5)
        self.rejected_freshness(r)

    def test_recovery_appearing_during_validation_invalidates_result(self):
        r = self.validate(gates=[self.gate(lambda: put(self.root, ".specroad/recovery/pending", b"keep"))])
        self.assertEqual(r.exit_code, 5)
        self.rejected_freshness(r)
        self.assertEqual((self.root / ".specroad/recovery/pending").read_bytes(), b"keep")

    def test_final_read_cannot_hide_new_source_membership(self):
        original = ProjectSource.read_normative
        count = 0
        def reading(source, name, **kw):
            nonlocal count
            raw = original(source, name, **kw)
            if name == str(self.path.relative_to(self.root)):
                count += 1
                if count == 2:
                    a = artifact(number=3)
                    put(self.root, artifact_path("goal", a["id"], "SR"), artifact_bytes(a))
            return raw
        with patch.object(ProjectSource, "read_normative", reading):
            r = self.validate()
        self.assertEqual(r.exit_code, 5)
        self.rejected_freshness(r)

    def test_permission_error_is_not_a_partial_success(self):
        with patch.object(ProjectSource, "read_normative", side_effect=PermissionError(13, "denied")):
            with no_write_attempts():
                r = self.validate()
        self.assertEqual(r.exit_code, 5)
        self.rejected_freshness(r)

    def test_symlinked_source_is_not_followed_or_repaired(self):
        external = self.root.parent / "outside.json"
        external.write_bytes(self.path.read_bytes())
        self.path.unlink(); self.path.symlink_to(external)
        before = inventory(self.root)
        with no_write_attempts():
            r = self.validate()
        self.assertEqual(r.exit_code, 7)
        self.assertEqual(inventory(self.root), before)

    def test_special_source_is_rejected_without_opening_it(self):
        self.path.unlink(); os.mkfifo(self.path)
        try:
            with no_write_attempts():
                r = self.validate()
            self.assertEqual(r.exit_code, 7)
        finally:
            self.path.unlink()

    def test_linked_operational_directory_is_not_followed(self):
        outside = self.root.parent / "outside"; outside.mkdir()
        (self.root / ".specroad").symlink_to(outside, target_is_directory=True)
        with no_write_attempts():
            r = reader.diagnose_read_only(self.root)
        self.assertEqual(r.exit_code, 7)
        self.assertFalse(r.data["model_loaded"])

    def test_nested_project_marker_is_rejected(self):
        put(self.root, str(self.path.parent.relative_to(self.root)) + "/specroad.json", b"{}")
        with no_write_attempts():
            r = self.validate()
        self.assertEqual(r.exit_code, 7)

    def test_configured_external_path_does_not_escape_root(self):
        p = self.root / "specroad.json"; data = json.loads(p.read_bytes())
        data["managed_paths"][0] = "../outside"; p.write_bytes(artifact_bytes(data))
        with no_write_attempts():
            r = self.validate()
        self.assertFalse(r.passed)
        self.assertFalse(r.data["normal_operation_started"])

    def test_corrupt_unselected_source_is_not_hidden(self):
        a = artifact(number=5)
        put(self.root, artifact_path("goal", a["id"], "SR"), b"not JSON")
        r = self.validate(selected_ids=(self.value["id"],))
        self.assertFalse(r.passed)
        self.assertEqual(r.exit_code, 3)

    def test_invalid_fail_policy_does_not_start_a_model_read(self):
        for kwargs in ({"strict":1}, {"fail_on":"info"}, {"fail_on":None}):
            with self.subTest(policy=kwargs):
                with patch.object(ProjectBoundary, "read_bytes", side_effect=AssertionError("read")):
                    r = self.validate(**kwargs)
                self.assertEqual(r.exit_code, 2)
                self.assertFalse(r.data["normal_operation_started"])

    def test_validation_threshold_does_not_change_warning_severity(self):
        def check(c):
            return c.result([{"reason":"review_advice", "severity":"warning", "artifact_id":self.value["id"]}])
        gate = ModelGate("extension:advice", "1", no_dependencies, check)
        normal, strict = self.validate(gates=[gate]), self.validate(gates=[gate], strict=True)
        self.assertTrue(normal.passed)
        self.assertFalse(strict.passed)
        self.assertEqual([d["severity"] for d in strict.data["validation"]["diagnostics"]], ["warning"])

    def test_lint_uses_stored_terms_without_rewriting_them(self):
        a = artifact("requirement", statement="A fuzzy constraint", language="en")
        t = term(language="en", forbidden_synonyms=["fuzzy"]).data
        make_project(self.root, a, t)
        before = inventory(self.root)
        with no_write_attempts():
            r = reader.lint_project_read_only(self.root,
                policy=literal_policy(term_ids=[t["id"]]), selected_ids=[a["id"]])
        self.assertEqual(r.data["lint"]["diagnostics"][0]["code"], "SRV053")
        self.assertEqual(inventory(self.root), before)

    def test_lint_invalid_selection_never_opens_project(self):
        for ids in ([], ["x", "x"], [None], "SR-REQ-1"):
            with self.subTest(ids=ids):
                with patch.object(ProjectBoundary, "read_bytes", side_effect=AssertionError("read")):
                    r = reader.lint_project_read_only(self.root, policy=literal_policy(), selected_ids=ids)
                self.assertEqual(r.exit_code, 2)

    def test_lint_config_change_after_match_discards_success(self):
        a = artifact("requirement", language="en"); make_project(self.root, a)
        match = reader.lint_literals
        def changed(*args, **kw):
            value = match(*args, **kw)
            p = self.root / "specroad.json"; p.write_bytes(p.read_bytes() + b"\n")
            return value
        with patch.object(reader, "lint_literals", changed):
            r = reader.lint_project_read_only(self.root, policy=literal_policy(), selected_ids=[a["id"]])
        self.assertEqual(r.exit_code, 5)
        self.rejected_freshness(r)

    def test_literal_lint_without_policy_does_not_guess_from_locale(self):
        a = artifact("requirement"); make_project(self.root, a)
        with no_write_attempts():
            r = reader.lint_project_read_only(self.root, policy=None, selected_ids=[a["id"]])
        self.assertEqual(r.data["diagnostics"][0]["reason"], "read_only_literal_policy_required")

    def test_explicit_profile_absence_does_not_fallback_to_distribution(self):
        with no_write_attempts():
            r = reader.validate_project_read_only(self.root, profile_resources=[], core_key="core@0.2.0")
        self.assertFalse(r.passed)
        self.assertFalse(r.data["model_loaded"])

    def test_exact_configuration_and_artifact_bytes_are_bound(self):
        r = self.validate()
        self.assertTrue(r.data["freshness_verified"])
        self.assertEqual(r.data["configuration_sha256"], sha256((self.root / "specroad.json").read_bytes()).hexdigest())
        self.assertEqual(r.data["source_bindings"], [{"path":str(self.path.relative_to(self.root)), "sha256":sha256(self.path.read_bytes()).hexdigest()}])
        self.assertEqual(len(r.data["source_observation_sha256"]), 64)

    def test_format_only_change_also_changes_source_observation(self):
        first = self.validate().data["source_observation_sha256"]
        self.path.write_bytes(self.path.read_bytes() + b"\n")
        second = self.validate()
        self.assertTrue(second.passed)
        self.assertNotEqual(first, second.data["source_observation_sha256"])

    def test_repeated_readers_do_not_share_mutable_outcomes(self):
        r = self.validate(); d = r.data; d["source_bindings"].clear()
        self.assertEqual(r.data, self.validate().data)
        self.assertEqual(len(r.data["source_bindings"]), 1)

    def test_concurrent_readers_keep_independent_results(self):
        before = inventory(self.root)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.validate().data, range(4)))
        self.assertTrue(all(r == results[0] for r in results))
        self.assertTrue(all(r["passed"] for r in results))
        self.assertEqual(inventory(self.root), before)

    def test_diagnostic_paths_are_complete_beyond_display_limits(self):
        for i in range(151):
            put(self.root, f".specroad/transactions/tx-{i:03d}/journal.json", b"not opened")
        with no_write_attempts():
            r = reader.diagnose_read_only(self.root)
        paths = r.data["operational"]["unresolved_paths"]
        self.assertEqual(len(paths), 151)
        self.assertEqual(paths, sorted(paths))
        self.assertFalse(r.data["operational"]["journal_contents_loaded"])

    def test_valid_artifact_text_is_not_executed(self):
        a = artifact(statement="__import__('os').remove('specroad.json') /../../etc/passwd")
        make_project(self.root, a)
        before = inventory(self.root)
        with no_write_attempts():
            self.assertTrue(self.validate().passed)
        self.assertEqual(inventory(self.root), before)

    def test_passive_diagnostic_returns_unknown_ownership(self):
        r = reader.diagnose_read_only(self.root)
        self.assertIsNone(r.data["operational"]["writer_owner"])
        self.assertFalse(r.data["operational"]["writer_ownership_verified"])
        self.assertIsNone(r.data["passed"])
        self.assertFalse(r.data["checks_complete"])

    def test_module_and_zipapp_read_without_project_side_effects(self):
        module, archive = build_distribution(self.root.parent / "distribution")
        resources = profile_resources()[0].source_bytes
        body = """import json,sys
sys.path.insert(0,sys.argv[1])
from specroad.profiles.values import ProfileResource
from specroad.storage.read_only import validate_project_read_only, diagnose_read_only
result=validate_project_read_only(sys.argv[2], profile_resources=[ProfileResource(%r)],core_key='core@0.2.0')
print(json.dumps({'validation':result.data,'diagnosis':diagnose_read_only(sys.argv[2]).data}))
""" % resources
        before = inventory(self.root)
        for location in (module, archive):
            with self.subTest(distribution=location.name):
                result = run_python(["-I", "-S", "-B", "-c", body, str(location), str(self.root)], self.root.parent, capture=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                data = json.loads(result.stdout)
                self.assertTrue(data["validation"]["passed"])
                self.assertEqual(data["diagnosis"]["exit_code"], 0)
        self.assertEqual(inventory(self.root), before)

    def test_profile_conflict_is_configuration_exit_not_a_model_success(self):
        p = profile_resources(required_fields=[{"artifact_types":["goal"],"maturities":[],"fields":["/statement"]}],
                              forbidden_fields=[{"artifact_types":["goal"],"maturities":[],"fields":["/statement"]}])
        r = reader.validate_project_read_only(self.root, profile_resources=p, core_key="core@0.2.0")
        self.assertEqual(r.exit_code, 2)
        self.assertEqual(r.data["diagnostics"][0]["exit_code"], 2)
        self.assertEqual(r.data["diagnostics"][0]["code"], "SRV142")
        self.assertFalse(r.data["normal_operation_started"])

    def test_absent_literal_checks_return_incomplete_not_success_exit(self):
        a = artifact("requirement", language="de")
        make_project(self.root, a)
        r = reader.lint_project_read_only(self.root, policy=literal_policy(), selected_ids=[a["id"]])
        self.assertIsNone(r.data["passed"])
        self.assertEqual(r.data["status"], "incomplete")
        self.assertEqual(r.exit_code, 5)

    def test_lint_warning_threshold_retains_the_original_severity(self):
        a = artifact("requirement", statement="A fuzzy requirement", language="en")
        t = term(language="en", forbidden_synonyms=["fuzzy"]).data
        make_project(self.root, a, t)
        kwargs = dict(policy=literal_policy(term_ids=[t["id"]]), selected_ids=[a["id"]])
        normal = reader.lint_project_read_only(self.root, **kwargs)
        strict = reader.lint_project_read_only(self.root, strict=True, **kwargs)
        self.assertTrue(normal.passed)
        self.assertEqual(normal.exit_code, 0)
        self.assertFalse(strict.passed)
        self.assertEqual(strict.exit_code, 1)
        self.assertEqual(strict.data["lint"]["diagnostics"], normal.data["lint"]["diagnostics"])
        self.assertEqual(strict.data["lint"]["diagnostics"][0]["severity"], "warning")
