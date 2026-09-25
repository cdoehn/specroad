"""Real root reads, no writes, and passive diagnostics at the library boundary."""
from dataclasses import FrozenInstanceError
from pathlib import Path
import tempfile
import unittest

from specroad.storage.read_only import (validate_project_read_only, lint_project_read_only,
                                       diagnose_read_only)
from specroad.model.paths import artifact_path
from tests.support.read_only import (make_project, profile_resources, literal_policy,
                                     inventory, no_write_attempts)
from tests.support.model_validation import artifact, edge
from tests.support.model import put
from tests.support.domain import approved_value
from tests.support.artifacts import artifact_bytes


class ReadOnlyValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def validate(self, **kwargs):
        return validate_project_read_only(self.root, profile_resources=profile_resources(),
                                         core_key="core@0.2.0", **kwargs)

    def test_valid_root_without_cache_is_checked_without_writes(self):
        a = artifact()
        make_project(self.root, a)
        before = inventory(self.root)
        with no_write_attempts():
            result = self.validate()
        self.assertTrue(result.passed)
        self.assertEqual(result.data["validation"]["source_report"]["checked_ids"], [a["id"]])
        self.assertEqual(inventory(self.root), before)
        self.assertFalse((self.root / ".specroad").exists())

    def test_read_only_permissions_do_not_require_write_probe(self):
        make_project(self.root, artifact())
        paths = [self.root, *self.root.rglob("*")]
        for p in paths:
            p.chmod(0o555 if p.is_dir() else 0o444)
        try:
            before = inventory(self.root)
            with no_write_attempts():
                self.assertTrue(self.validate().passed)
            self.assertEqual(inventory(self.root), before)
        finally:
            for p in paths:
                p.chmod(0o755 if p.is_dir() else 0o644)

    def test_cache_contents_are_not_required_or_rewritten(self):
        make_project(self.root, artifact())
        put(self.root, ".specroad/cache/broken.db", b"broken cache")
        before = inventory(self.root)
        with no_write_attempts():
            result = self.validate()
        self.assertTrue(result.passed)
        self.assertFalse(result.data["operational"]["cache_contents_loaded"])
        self.assertEqual(inventory(self.root), before)

    def test_generated_attachments_and_archives_are_not_scanned(self):
        make_project(self.root, artifact())
        for name in ("generated/fake.json", "attachments/unused.bin", "archive/objects/old"):
            put(self.root, name, b"not JSON")
        before = inventory(self.root)
        self.assertTrue(self.validate().passed)
        self.assertEqual(inventory(self.root), before)

    def test_real_schema_failure_remains_read_only(self):
        a = artifact(); del a["statement"]
        make_project(self.root, a)
        before = inventory(self.root)
        with no_write_attempts():
            r = self.validate()
        self.assertFalse(r.passed)
        self.assertEqual(r.exit_code, 3)
        self.assertEqual(inventory(self.root), before)

    def test_bad_json_is_a_diagnosis_not_a_repair(self):
        a = artifact(); make_project(self.root, a)
        put(self.root, artifact_path("goal", a["id"], "SR"), b'{"id":}')
        before = inventory(self.root)
        with no_write_attempts():
            r = self.validate()
        self.assertFalse(r.passed)
        self.assertEqual(r.data["validation"]["source_report"]["stages"][0]["status"], "failed")
        self.assertEqual(inventory(self.root), before)

    def test_selected_target_includes_incoming_dependencies(self):
        a, b = artifact(), artifact(number=1)
        a["relations"] = [edge(b)]
        make_project(self.root, a, b)
        r = self.validate(selected_ids=(b["id"],))
        self.assertTrue(r.passed)
        self.assertEqual(r.data["validation"]["source_report"]["checked_ids"], sorted((a["id"], b["id"])))

    def test_absent_semantic_gate_is_not_passed(self):
        make_project(self.root, approved_value("goal"))
        r = self.validate()
        self.assertFalse(r.passed)
        self.assertFalse(r.data["checks_complete"])

    def test_profile_conflict_precedes_model_loading(self):
        make_project(self.root, artifact())
        p = profile_resources(required_fields=[{"artifact_types": ["goal"], "maturities": [], "fields": ["/statement"]}],
                              forbidden_fields=[{"artifact_types": ["goal"], "maturities": [], "fields": ["/statement"]}])
        before = inventory(self.root)
        with no_write_attempts():
            r = validate_project_read_only(self.root, profile_resources=p, core_key="core@0.2.0")
        self.assertFalse(r.passed)
        self.assertFalse(r.data["model_loaded"])
        self.assertEqual(r.data["diagnostics"][0]["code"], "SRV142")
        self.assertEqual(inventory(self.root), before)

    def test_active_transaction_blocks_before_model_load(self):
        make_project(self.root, artifact())
        put(self.root, ".specroad/transactions/tx/journal.json", b"unclear")
        before = inventory(self.root)
        with no_write_attempts():
            r = self.validate()
        self.assertEqual(r.exit_code, 5)
        self.assertTrue(r.data["operational"]["recovery_required"])
        self.assertFalse(r.data["normal_operation_started"])
        self.assertFalse(r.data["model_loaded"])
        self.assertEqual(inventory(self.root), before)

    def test_auto_recover_configuration_does_not_authorize_writes(self):
        make_project(self.root, artifact(), transaction_policy={"auto_recover": True})
        put(self.root, ".specroad/transactions/tx/journal.json", b"{}")
        with no_write_attempts():
            r = self.validate()
        self.assertEqual(r.exit_code, 5)
        self.assertFalse(r.data["operational"]["recovery_performed"])

    def test_receipts_alone_do_not_require_active_recovery(self):
        make_project(self.root, artifact())
        put(self.root, ".specroad/transactions/receipts/previous.json", b"not read")
        put(self.root, ".specroad/requests/previous.json", b"not read")
        self.assertTrue(self.validate().passed)

    def test_unknown_operational_record_never_means_no_lock(self):
        make_project(self.root, artifact())
        put(self.root, ".specroad/writer.record", b'{"pid": 1}')
        r = self.validate()
        self.assertEqual(r.exit_code, 5)
        self.assertIsNone(r.data["operational"]["writer_owner"])
        self.assertFalse(r.data["operational"]["writer_ownership_verified"])

    def test_metadata_diagnosis_works_without_configuration(self):
        put(self.root, ".specroad/transactions/lost/staging", b"payload")
        before = inventory(self.root)
        with no_write_attempts():
            r = diagnose_read_only(self.root)
        self.assertEqual(r.exit_code, 0)
        self.assertIsNone(r.data["passed"])
        self.assertTrue(r.data["operational"]["recovery_required"])
        self.assertFalse(r.data["model_loaded"])
        self.assertEqual(inventory(self.root), before)

    def test_diagnosis_does_not_parse_corrupt_configuration(self):
        put(self.root, "specroad.json", b"not JSON")
        with no_write_attempts():
            r = diagnose_read_only(self.root)
        self.assertEqual(r.exit_code, 0)
        self.assertIsNone(r.data["project_id"])

    def test_lint_approved_placeholder_without_output_files(self):
        a = approved_value("requirement"); a["statement"] = "TODO define threshold"
        make_project(self.root, a)
        before = inventory(self.root)
        with no_write_attempts():
            r = lint_project_read_only(self.root, policy=literal_policy(), selected_ids=(a["id"],))
        self.assertEqual(r.exit_code, 1)
        self.assertEqual(r.data["lint"]["diagnostics"][0]["code"], "SRV033")
        self.assertEqual(inventory(self.root), before)

    def test_lint_does_not_invent_applicable_language_checks(self):
        a = artifact("requirement", language="de")
        make_project(self.root, a)
        r = lint_project_read_only(self.root, policy=literal_policy(), selected_ids=(a["id"],))
        self.assertIsNone(r.data["passed"])
        self.assertFalse(r.data["checks_complete"])

    def test_lint_recovery_is_not_a_pass_with_empty_diagnostics(self):
        a = artifact("requirement"); make_project(self.root, a)
        put(self.root, ".specroad/recovery/retained", b"do not delete")
        with no_write_attempts():
            r = lint_project_read_only(self.root, policy=literal_policy(), selected_ids=(a["id"],))
        self.assertEqual(r.exit_code, 5)
        self.assertIsNone(r.data["lint"])

    def test_lint_missing_selection_fails(self):
        make_project(self.root, artifact("requirement"))
        r = lint_project_read_only(self.root, policy=literal_policy(), selected_ids=("SR-REQ-9999",))
        self.assertFalse(r.passed)
        self.assertEqual(r.data["diagnostics"][0]["reason"], "read_only_selected_id_missing")

    def test_wrong_project_identity_is_rejected(self):
        make_project(self.root, artifact())
        self.assertFalse(self.validate(expected_project_id="other").passed)

    def test_detached_result_cannot_mutate_later_reads(self):
        make_project(self.root, artifact())
        r = self.validate(); value = r.data
        value["validation"]["source_report"]["checked_ids"].clear()
        self.assertEqual(len(r.data["validation"]["source_report"]["checked_ids"]), 1)
        with self.assertRaises(FrozenInstanceError):
            r._encoded = b"{}"
        with self.assertRaises(TypeError):
            bool(r)

    def test_no_read_result_is_write_or_approval_authority(self):
        make_project(self.root, artifact())
        for r in (self.validate(), diagnose_read_only(self.root)):
            for field in ("write_authorized", "approval_granted", "atomic_snapshot", "project_complete"):
                self.assertIs(r.data[field], False)

    def test_mismatched_filename_cannot_select_other_identity(self):
        a = artifact(); b = artifact(number=1)
        make_project(self.root, a)
        put(self.root, artifact_path("goal", a["id"], "SR"), artifact_bytes(b))
        self.assertEqual(self.validate().data["diagnostics"][0]["reason"], "artifact_path_identity_mismatch")

    def test_missing_root_is_not_created(self):
        absent = self.root / "absent"
        with no_write_attempts():
            r = diagnose_read_only(absent)
        self.assertEqual(r.exit_code, 5)
        self.assertFalse(absent.exists())
