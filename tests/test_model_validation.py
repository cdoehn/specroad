"""Actual structure, dependencies and fail-closed service integration, not UI."""
import copy
from dataclasses import FrozenInstanceError
import unittest

from specroad.model.errors import ModelError
from specroad.validation import (ModelDocument, ModelGate, GateResult, GateDependencies, validate_model)
from support.artifacts import artifact_bytes
from support.domain import approved_value
from support.records import record_value
from support.model_validation import artifact, doc, edge, profile, title_gate, no_dependencies


class ModelValidationTests(unittest.TestCase):
    def check_model(self, *values, **kwargs):
        return validate_model(tuple(doc(v) for v in values), profile=profile(), **kwargs)

    def test_one_valid_draft_passes_without_approval(self):
        result = self.check_model(artifact())
        self.assertTrue(result.passed)
        self.assertTrue(result.complete)
        for flag in ("approval_granted", "write_authorized", "project_files_verified", "atomic_snapshot"):
            self.assertIs(result.data[flag], False)

    def test_explicit_empty_model_has_zero_sources(self):
        result = self.check_model()
        self.assertTrue(result.passed)
        self.assertEqual(result.data["checked_ids"], [])

    def test_default_checks_every_loaded_artifact(self):
        values = [artifact(number=i) for i in range(151)]
        result = self.check_model(*values)
        self.assertTrue(result.passed)
        self.assertEqual(result.data["checked_ids"], sorted(v["id"] for v in values))

    def test_original_bytes_and_detached_report_are_preserved(self):
        value = artifact(statement="日本語 e\u0301\nText")
        source = ModelDocument("source.json", b" \n" + artifact_bytes(value) + b"\n")
        before = source.content
        result = validate_model((source,), profile=profile())
        view = result.data; view["checked_ids"].clear(); view["stages"].clear()
        self.assertEqual(source.content, before)
        self.assertEqual(result.data["checked_ids"], [value["id"]])
        with self.assertRaises(FrozenInstanceError):
            source.content = b"changed"

    def test_malformed_json_has_real_position(self):
        result = validate_model((ModelDocument("bad.json", b'{\n"id": }'),), profile=profile())
        self.assertIs(result.data["model_valid"], False)
        self.assertFalse(result.complete)
        error = result.diagnostics[0]
        self.assertEqual(error["path"], "bad.json")
        self.assertEqual(error["line"], 2)
        self.assertIsInstance(error["column"], int)

    def test_duplicate_json_key_is_not_repaired(self):
        result = validate_model((ModelDocument("bad", b'{"id":1,"id":2}'),), profile=profile())
        self.assertEqual(result.diagnostics[0]["reason"], "duplicate_key")
        self.assertFalse(result.passed)

    def test_missing_domain_field_is_rejected(self):
        value = artifact(); del value["statement"]
        result = self.check_model(value)
        self.assertFalse(result.passed)
        self.assertEqual(result.diagnostics[0]["artifact_id"], value["id"])

    def test_unknown_type_is_not_common_schema_success(self):
        result = self.check_model(artifact(artifact_type="custom"))
        self.assertEqual(result.diagnostics[0]["reason"], "unknown_artifact_type")

    def test_identity_prefix_type_conflict_is_rejected(self):
        result = self.check_model(artifact(id="SR-REQ-" + "0" * 26))
        self.assertFalse(result.passed)

    def test_duplicate_artifact_identity_across_paths(self):
        value = artifact()
        result = validate_model((doc(value,"a"), doc(value,"b")), profile=profile())
        self.assertEqual(result.diagnostics[0]["reason"], "duplicate_artifact_id")

    def test_mixed_project_prefix_is_rejected(self):
        result = self.check_model(artifact(), artifact(number=1, id="XX-GOAL-" + "0" * 26))
        self.assertEqual(result.diagnostics[0]["reason"], "mixed_project_prefix")

    def test_missing_stored_target_fails_before_semantics(self):
        a, b = artifact(), artifact(number=1)
        a["relations"] = [edge(b)]
        result = self.check_model(a)
        self.assertEqual(result.diagnostics[0]["reason"], "missing_relation_target")

    def test_invalid_source_target_matrix_is_blocking(self):
        a, b = artifact(), artifact(number=1)
        a["relations"] = [edge(b, "depends_on")]
        self.assertEqual(self.check_model(a,b).diagnostics[0]["reason"], "relation_type_pair_forbidden")

    def test_hierarchy_cycle_has_both_relation_ids(self):
        a, b = artifact(), artifact(number=1)
        a["relations"] = [edge(b, number=1)]; b["relations"] = [edge(a, number=2)]
        result = self.check_model(a,b)
        self.assertFalse(result.passed)
        self.assertEqual(set(result.diagnostics[0]["relation_ids"]), {edge(a,number=1)["relation_id"],edge(a,number=2)["relation_id"]})

    def test_noncanonical_symmetric_data_not_rewritten(self):
        a, b = artifact(), artifact(number=1)
        b["relations"] = [edge(a,"duplicates")]
        original = copy.deepcopy(b)
        result = self.check_model(a,b)
        self.assertEqual(result.diagnostics[0]["reason"], "noncanonical_symmetric_relation")
        self.assertEqual(b, original)

    def test_explicit_selection_expands_incoming_and_outgoing(self):
        a,b,c,other = [artifact(number=i) for i in range(4)]
        a["relations"] = [edge(b,number=1)]; b["relations"] = [edge(c,number=2)]
        result = self.check_model(a,b,c,other,selected_ids=(b["id"],))
        self.assertTrue(result.passed)
        self.assertEqual(result.data["checked_ids"], sorted(v["id"] for v in (a,b,c)))

    def test_missing_selected_id_is_not_an_empty_success(self):
        result = self.check_model(artifact(), selected_ids=(artifact(number=3)["id"],))
        self.assertEqual(result.diagnostics[0]["reason"], "validation_selected_id_missing")

    def test_missing_profile_is_unavailable_not_passed(self):
        result = validate_model((doc(artifact()),))
        self.assertIsNone(result.data["model_valid"])
        self.assertFalse(result.complete)

    def test_composed_profile_rules_are_actually_checked(self):
        p = profile(forbidden_fields=[{"artifact_types":["goal"],"maturities":[],"fields":["/statement"]}])
        result = validate_model((doc(artifact()),), profile=p)
        self.assertFalse(result.passed)
        self.assertIn("profile_forbidden_field", [d["reason"] for d in result.diagnostics])

    def test_missing_lifecycle_validator_is_not_synthetic_pass(self):
        result = self.check_model(approved_value("goal"))
        lifecycle = next(s for s in result.data["stages"] if s["stage"] == "lifecycle")
        self.assertEqual(lifecycle["status"], "unavailable")
        self.assertIsNone(result.data["model_valid"])

    def test_missing_evidence_and_baseline_services_are_visible(self):
        baseline = record_value("baseline")
        result = self.check_model(baseline)
        self.assertIn("baseline_integrity", [s["stage"] for s in result.data["stages"] if s["status"] == "unavailable"])
        self.assertFalse(result.passed)

    def test_approved_requirement_minima_remain_blocking(self):
        result = self.check_model(approved_value("requirement"))
        failures = [d for d in result.diagnostics if d["reason"] == "missing_required_relation"]
        self.assertEqual(len(failures), 2)
        self.assertIs(result.data["model_valid"], False)

    def test_registered_gate_is_run_and_checks_real_values(self):
        result = self.check_model(artifact(title="forbidden"), gates=(title_gate(),))
        self.assertEqual(result.diagnostics[0]["reason"], "invalid_title")
        self.assertFalse(result.passed)
        self.assertTrue(self.check_model(artifact(), gates=(title_gate(),)).passed)

    def test_gate_dependencies_extend_scope_transitively(self):
        a,b,c = [artifact(number=i) for i in range(3)]
        def dependencies(context):
            return context.dependency_result({a["id"]:[b["id"]],b["id"]:[c["id"]],c["id"]:[]})
        result = self.check_model(a,b,c, selected_ids=(a["id"],), gates=(title_gate(dependencies=dependencies),))
        self.assertTrue(result.passed)
        self.assertEqual(result.data["checked_ids"], sorted(v["id"] for v in (a,b,c)))

    def test_gate_boolean_is_not_a_bound_complete_result(self):
        gate = ModelGate("extension:bad", "1", no_dependencies, lambda context: True)
        result = self.check_model(artifact(), gates=(gate,))
        self.assertEqual(result.diagnostics[0]["reason"], "validation_gate_result_unbound_or_incomplete")

    def test_gate_with_wrong_binding_cannot_reuse_success(self):
        gate = ModelGate("extension:stale", "1", no_dependencies, lambda c: GateResult("0"*64,c.subjects))
        self.assertFalse(self.check_model(artifact(), gates=(gate,)).passed)

    def test_gate_with_incomplete_subjects_cannot_claim_success(self):
        gate = ModelGate("extension:partial", "1", no_dependencies, lambda c: GateResult(c.input_sha256,()))
        self.assertFalse(self.check_model(artifact(), gates=(gate,)).passed)

    def test_gate_cannot_replace_builtin_checks(self):
        with self.assertRaises(ModelError):
            ModelGate("graph", "1", no_dependencies, lambda c:c.result())

    def test_incomplete_dependency_observation_is_not_empty(self):
        gate = title_gate(dependencies=lambda c:c.dependency_result({}))
        result = self.check_model(artifact(), gates=(gate,))
        self.assertFalse(result.passed)
        self.assertEqual(result.diagnostics[0]["reason"], "validation_gate_dependencies_unbound_or_incomplete")

    def test_literal_extensions_do_not_choose_validators(self):
        value = artifact(extensions={"test.extra":{"gate":"baseline_integrity","callback":"os.system('bad')"}})
        result = self.check_model(value)
        self.assertTrue(result.passed)

    def test_bad_caller_contracts_raise_without_silent_defaults(self):
        for call in (lambda:validate_model("file.json"), lambda:ModelDocument("x",{}),
                     lambda:self.check_model(artifact(), selected_ids=()),
                     lambda:self.check_model(artifact(), gates=(title_gate(), title_gate()))):
            with self.subTest(call=str(type(call))), self.assertRaises(ModelError):
                call()

    def test_source_order_does_not_change_result(self):
        a,b=artifact(),artifact(number=1)
        self.assertEqual(self.check_model(a,b).data, self.check_model(b,a).data)
