"""Actual Core and project lint findings; no injected always-passing gates."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from specroad.lint import lint_core
from specroad.model.paths import artifact_path
from specroad.profiles.composition import compose_profiles
from specroad.storage.profiles import load_bundled_profile
from specroad.storage.read_only import lint_project_read_only
from tests.support.core_lint import requirement_graph, sources
from tests.support.domain import approved_value
from tests.support.read_only import inventory, literal_policy, make_project, no_write_attempts


class CoreLintWorkTests(unittest.TestCase):
    def setUp(self):
        self.values = requirement_graph()
        self.requirement = self.values[0]
        self.selected = (self.requirement["id"],)

    def observe(self, **kwargs):
        return lint_core(sources(self.values), selected_ids=self.selected, **kwargs)

    def test_complete_minima_and_rationale_are_clear_but_not_approval(self):
        records = sources(self.values)
        report = lint_core(records, selected_ids=self.selected)
        self.assertEqual(report["diagnostics"], [])
        self.assertTrue(report["checks_complete"])
        self.assertTrue(report["core_checks_passed"])
        self.assertEqual(report["checked_ids"], list(self.selected))
        self.assertEqual({b["artifact_id"]: b["sha256"] for b in report["source_bindings"]},
                         {s.identity.id: sha256(s.source_bytes).hexdigest() for s in records})
        for field in ("approval_granted", "write_authorized", "project_complete",
                      "full_schema_checked", "full_profile_checked", "review_status_checked",
                      "language_detection_performed", "profile_minima_checked"):
            self.assertIs(report[field], False)

    def test_missing_rationale_has_its_own_bound_diagnostic(self):
        del self.requirement["rationale"]
        report = self.observe()
        self.assertFalse(report["core_checks_passed"])
        self.assertEqual(report["diagnostics"], [{
            "code": "SRV002", "severity": "error", "reason": "missing_rationale",
            "origin": "core_rule", "rule_id": "core:requirement-rationale",
            "artifact_id": self.requirement["id"], "pointer": "/rationale",
            "path": artifact_path("requirement", self.requirement["id"], "SR")}])

    def test_invalid_rationale_uses_the_existing_field_contract(self):
        for value in ("", None, [], 7):
            with self.subTest(value=value):
                self.requirement["rationale"] = value
                findings = self.observe()["diagnostics"]
                self.assertEqual(len(findings), 1)
                self.assertEqual(findings[0]["reason"], "invalid_rationale")
                self.assertEqual(findings[0]["code"], "SRV002")
                self.assertEqual(findings[0]["pointer"], "/rationale")

    def test_missing_verification_has_actual_minimum_and_identity(self):
        self.requirement["relations"].pop()
        findings = self.observe()["diagnostics"]
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual((finding["code"], finding["rule_id"], finding["pointer"]),
                         ("SRV032", "core:requirement-verification", "/relations"))
        self.assertEqual((finding["minimum"], finding["actual"]), (1, 0))
        self.assertEqual(finding["artifact_id"], self.requirement["id"])
        self.assertEqual(finding["relation_types"], ["verified_by"])

    def test_missing_origin_is_separate_from_verification(self):
        self.requirement["relations"].pop(0)
        findings = self.observe()["diagnostics"]
        self.assertEqual(len(findings), 1)
        self.assertEqual((findings[0]["code"], findings[0]["rule_id"]),
                         ("SRV031", "core:requirement-origin"))
        self.assertEqual(findings[0]["pointer"], "/relations")

    def test_approved_need_uses_its_own_rationale_rule(self):
        need = approved_value("need")
        self.assertEqual(lint_core(sources((need,)))["diagnostics"], [])
        del need["rationale"]
        findings = lint_core(sources((need,)))["diagnostics"]
        self.assertEqual(len(findings), 1)
        self.assertEqual((findings[0]["rule_id"], findings[0]["artifact_id"]),
                         ("core:need-rationale", need["id"]))

    def test_draft_does_not_inherit_approved_obligations(self):
        self.requirement["maturity"] = "draft"
        del self.requirement["rationale"]
        self.requirement["relations"] = []
        self.assertEqual(self.observe()["diagnostics"], [])

    def test_shipped_profile_minimum_is_observed_with_its_binding(self):
        resources = tuple(load_bundled_profile(key) for key in
                          ("core@0.2.0", "software-en@0.2.0"))
        profile = compose_profiles(resources, core_key="core@0.2.0",
                                   project_profiles=("software-en@0.2.0",))
        self.assertEqual(self.observe(profile=profile)["diagnostics"], [])
        self.requirement["relations"].pop()
        report = self.observe(profile=profile)
        self.assertEqual({(d["code"], d["rule_id"]) for d in report["diagnostics"]},
                         {("SRV032", "core:requirement-verification"),
                          ("SRV023", "software:requirement-verification")})
        self.assertEqual(report["profile_binding"], profile.binding())
        self.assertTrue(report["profile_minima_checked"])
        self.assertFalse(report["full_profile_checked"])


class ProjectCoreLintWorkTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.values = requirement_graph()
        self.requirement = self.values[0]

    def read(self, **kwargs):
        return lint_project_read_only(self.root, policy=literal_policy(),
            selected_ids=(self.requirement["id"],), **kwargs)

    def test_complete_project_read_has_no_writes_or_approval(self):
        make_project(self.root, *self.values)
        before = inventory(self.root)
        with no_write_attempts():
            result = self.read()
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.passed)
        self.assertTrue(result.data["freshness_verified"])
        self.assertEqual(result.data["lint"]["diagnostics"], [])
        for field in ("approval_granted", "write_authorized", "project_complete", "atomic_snapshot"):
            self.assertIs(result.data[field], False)
        self.assertEqual(inventory(self.root), before)

    def test_project_reader_exposes_each_missing_core_obligation(self):
        for omission, expected in (("rationale", "SRV002"), ("origin", "SRV031"),
                                   ("verification", "SRV032")):
            with self.subTest(omission=omission), TemporaryDirectory() as directory:
                values = requirement_graph()
                if omission == "rationale":
                    del values[0]["rationale"]
                else:
                    values[0]["relations"].pop(0 if omission == "origin" else 1)
                root = Path(directory)
                make_project(root, *values)
                before = inventory(root)
                with no_write_attempts():
                    result = lint_project_read_only(root, policy=literal_policy(),
                        selected_ids=(values[0]["id"],))
                self.assertEqual(result.exit_code, 1)
                self.assertFalse(result.passed)
                self.assertTrue(result.data["checks_complete"])
                self.assertEqual([d["code"] for d in result.data["lint"]["diagnostics"]], [expected])
                self.assertEqual(inventory(root), before)

    def test_project_profile_minimum_uses_activated_resources(self):
        self.requirement["relations"].pop()
        make_project(self.root, *self.values, profiles=["software-en@0.2.0"])
        resources = tuple(load_bundled_profile(key) for key in
                          ("core@0.2.0", "software-en@0.2.0"))
        with no_write_attempts():
            result = self.read(profile_resources=resources, core_key="core@0.2.0")
        self.assertEqual(result.exit_code, 1)
        self.assertEqual({d["rule_id"] for d in result.data["lint"]["diagnostics"]},
                         {"core:requirement-verification", "software:requirement-verification"})

    def test_core_findings_preserve_literal_findings(self):
        del self.requirement["rationale"]
        self.requirement["relations"] = []
        self.requirement["statement"] = "TODO define the response."
        make_project(self.root, *self.values)
        result = self.read()
        self.assertEqual(result.exit_code, 1)
        self.assertEqual({d["code"] for d in result.data["lint"]["diagnostics"]},
                         {"SRV002", "SRV031", "SRV032", "SRV033"})
        self.assertEqual([d["code"] for d in result.data["lint"]["reports"][0]["diagnostics"]],
                         ["SRV033"])

    def test_activated_profile_without_resources_cannot_pass(self):
        make_project(self.root, *self.values, profiles=["software-en@0.2.0"])
        with no_write_attempts():
            result = self.read()
        self.assertEqual(result.exit_code, 2)
        self.assertFalse(result.passed)
        self.assertFalse(result.data["model_loaded"])
        self.assertIsNone(result.data["lint"])
        self.assertEqual(result.data["diagnostics"][0]["reason"],
                         "read_only_lint_profile_resources_required")

    def test_unresolved_relation_cannot_satisfy_a_minimum(self):
        make_project(self.root, self.requirement, self.values[1])
        with no_write_attempts():
            result = self.read()
        self.assertEqual(result.exit_code, 3)
        self.assertFalse(result.passed)
        self.assertFalse(result.data["checks_complete"])
        self.assertIsNone(result.data["lint"])
        self.assertEqual(result.data["diagnostics"][0]["reason"], "missing_relation_target")
