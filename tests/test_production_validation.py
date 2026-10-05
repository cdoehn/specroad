"""Productive language/SRX/approval observations; no successful substitute gates."""
from pathlib import Path
import tempfile
import unittest

from specroad.changes import assess_change_target, dry_run_change
from specroad.model.errors import ModelError
from specroad.storage.read_only import validate_project_read_only
from specroad.validation import validate_model, assess_validation, ModelGate
from tests.support.core_lint import requirement_graph
from tests.support.domain import domain_value
from tests.support.folds import edit
from tests.support.profile_composition import lint
from tests.support.production_validation import inputs, write_project, target_model
from tests.support.read_only import inventory, no_write_attempts
from tests.support.targets import plan, POLICY


def validate(data):
    return validate_model(data.documents, profile=data.profile, resources=data.resources)


def assessment(data):
    return assess_validation(validate(data), documents=data.documents)


def stages(report):
    return {s["stage"]: s for s in report.data["stages"]}


class ProductionValidationWorkTests(unittest.TestCase):
    def test_shipped_software_draft_passes_actual_model_gates(self):
        data = inputs([domain_value("requirement", language="en")])
        report = validate(data)
        self.assertTrue(report.passed)
        self.assertTrue(report.complete)
        self.assertEqual(stages(report)["language_policy"]["status"], "passed")
        self.assertEqual(stages(report)["profile_lint"]["status"], "passed")
        self.assertFalse(report.data["approval_granted"])
        self.assertFalse(report.data["write_authorized"])

    def test_german_named_software_profile_does_not_invent_content_language(self):
        data = inputs([domain_value("requirement", language="en")], software="software-de@0.2.0")
        self.assertEqual(assessment(data).exit_code, 0)

    def test_disallowed_language_has_bound_code_artifact_and_pointer(self):
        value = domain_value("requirement", language="de")
        data = inputs([value])
        result = assessment(data)
        self.assertEqual(result.exit_code, 1)
        finding = next(d for d in result.diagnostics if d.code == "SRV179")
        self.assertEqual((finding.artifact_id, finding.path, finding.location["pointer"]),
                         (value["id"], data.documents[0].path, "/language"))

    def test_false_profile_predicate_is_a_finding_not_an_invalid_expression(self):
        value = domain_value("requirement", language="en")
        data = inputs([value], rules=[lint("local:reject", value=False, severity="error")])
        result = assessment(data)
        self.assertEqual(result.exit_code, 1)
        finding = next(d for d in result.diagnostics if d.rule_id == "local:reject")
        self.assertEqual((finding.code, finding.origin, finding.artifact_id),
                         ("PROFILE_LINT", "profile_rule", value["id"]))

    def test_profile_evaluates_actual_project_configuration(self):
        rule = lint("local:project", severity="error")
        rule["program"]["expression"] = {"op": "eq", "args": [
            {"op": "field", "context": "project", "pointer": "/project_name"},
            {"op": "literal", "value": "Actual project"}]}
        values = [domain_value("requirement", language="en")]
        self.assertTrue(validate(inputs(values, rules=[rule], project_name="Actual project")).passed)
        self.assertFalse(validate(inputs(values, rules=[rule], project_name="Other project")).passed)

    def test_non_boolean_profile_result_cannot_pass(self):
        data = inputs([domain_value("requirement", language="en")], rules=[lint(value=1)])
        report = validate(data)
        self.assertFalse(report.passed)
        self.assertTrue(any(d["code"] == "SRV110" and d["reason"] == "profile_lint_boolean_required"
                            for d in report.diagnostics))

    def test_formal_placeholder_is_in_common_diagnostics(self):
        requirement, goal, verification = requirement_graph()
        requirement["statement"] = "TODO define the response."
        data = inputs([requirement, goal, verification])
        report = validate(data)
        self.assertEqual(stages(report)["approval_formal"]["status"], "failed")
        finding = next(d for d in assess_validation(report, documents=data.documents).diagnostics if d.code == "SRV033")
        self.assertEqual(finding.artifact_id, requirement["id"])
        self.assertEqual(finding.location["pointer"], "/statement")
        self.assertEqual(finding.path, data.documents[0].path)

    def test_formal_verification_subject_mismatch_is_retained(self):
        requirement, goal, verification = requirement_graph()
        verification["subjects"] = [goal["id"]]
        report = validate(inputs([requirement, goal, verification]))
        self.assertTrue(any(d["code"] == "SRV032" and
            d["reason"] == "approval_verification_subject_mismatch" for d in report.diagnostics))

    def test_formal_success_leaves_real_reviews_evidence_and_history_unavailable(self):
        report = validate(inputs(requirement_graph()))
        self.assertEqual(stages(report)["approval_formal"]["status"], "passed")
        for name in ("review_currentness", "evidence_currentness", "lifecycle"):
            self.assertEqual(stages(report)[name]["status"], "unavailable")
        self.assertFalse(report.complete)
        self.assertEqual(assess_validation(report).exit_code, 5)
        self.assertFalse(report.data["approval_granted"])

    def test_absent_registry_has_no_distribution_fallback(self):
        data = inputs([domain_value("requirement", language="en")], registry_present=False)
        report = validate(data)
        self.assertEqual(stages(report)["language_policy"]["status"], "unavailable")
        self.assertEqual(stages(report)["profile_lint"]["status"], "passed")
        self.assertEqual(assess_validation(report).exit_code, 5)

    def test_supplied_gate_cannot_replace_available_production_check(self):
        data = inputs([domain_value("requirement", language="de")])
        substitute = ModelGate("language_policy", "untrusted-substitute",
            lambda c: c.dependency_result({i: [] for i in c.subjects}), lambda c: c.result())
        with self.assertRaisesRegex(ModelError, "validation_builtin_gate_override"):
            validate_model(data.documents, profile=data.profile, resources=data.resources, gates=[substitute])


class ProjectProductionValidationWorkTests(unittest.TestCase):
    def read(self, data):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_project(root, data)
            before = inventory(root)
            with no_write_attempts():
                result = validate_project_read_only(root, profile_resources=data.profiles,
                                                    core_key=data.profiles[0].key)
            self.assertEqual(inventory(root), before)
            return result

    def test_real_project_draft_passes_without_writes_or_test_gates(self):
        data = inputs([domain_value("requirement", language="en")])
        result = self.read(data)
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.data["checks_complete"])
        self.assertTrue(result.data["freshness_verified"])
        self.assertEqual(result.data["validation"], assessment(data).as_dict())
        self.assertFalse(result.data["write_authorized"])

    def test_project_reader_reports_actual_language_failure(self):
        data = inputs([domain_value("requirement", language="de")])
        result = self.read(data)
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.data["validation"], assessment(data).as_dict())

    def test_project_reader_reports_actual_profile_failure(self):
        data = inputs([domain_value("requirement", language="en")],
                      rules=[lint(value=False, severity="error")])
        result = self.read(data)
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.data["validation"], assessment(data).as_dict())

    def test_project_reader_reports_formal_approval_failure_without_approval(self):
        requirement, goal, verification = requirement_graph()
        requirement["statement"] = "TODO specify behavior."
        data = inputs([requirement, goal, verification])
        result = self.read(data)
        self.assertEqual(result.data["validation"], assessment(data).as_dict())
        self.assertTrue(any(d["code"] == "SRV033" for d in result.data["validation"]["diagnostics"]))
        self.assertFalse(result.data["checks_complete"])
        self.assertFalse(result.data["approval_granted"])


class TargetProductionValidationWorkTests(unittest.TestCase):
    def target(self, data, changed):
        model = target_model(data)
        change = plan(model, [edit(changed, "Changed statement.")])
        with no_write_attempts():
            target = assess_change_target(change, model, policy=POLICY)
            dry = dry_run_change(change, model, policy=POLICY)
        self.assertEqual(target.data, dry.data["assessment"])
        self.assertFalse(target.data["transaction_prepared"])
        self.assertFalse(target.data["write_authorized"])
        return target

    def test_actual_shipped_draft_target_and_dry_run_pass(self):
        requirement = domain_value("requirement", language="en")
        self.assertTrue(self.target(inputs([requirement]), requirement).target_validated)

    def test_language_error_in_unchanged_requirement_blocks_goal_change(self):
        requirement, goal = domain_value("requirement", language="de"), domain_value("goal")
        result = self.target(inputs([requirement, goal]), goal)
        self.assertFalse(result.target_validated)
        self.assertTrue(any(d["code"] == "SRV179" and d["artifact_id"] == requirement["id"]
                            for d in result.data["validation"]["diagnostics"]))

    def test_actual_profile_rule_blocks_target(self):
        requirement = domain_value("requirement", language="en")
        result = self.target(inputs([requirement], rules=[lint(value=False, severity="error")]), requirement)
        self.assertFalse(result.target_validated)
        self.assertTrue(any(d["code"] == "PROFILE_LINT" for d in result.data["validation"]["diagnostics"]))

    def test_formal_error_in_unchanged_requirement_blocks_target(self):
        requirement, goal, verification = requirement_graph()
        requirement["statement"] = "TODO specify behavior."
        result = self.target(inputs([requirement, goal, verification]), goal)
        self.assertFalse(result.target_validated)
        self.assertTrue(any(d["code"] == "SRV033" for d in result.data["validation"]["diagnostics"]))
        self.assertFalse(result.data["checks_complete"])
        self.assertFalse(result.data["approval_granted"])
