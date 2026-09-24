"""Normalized pipeline diagnostics, complete source binding and fail thresholds."""
import json
import unittest
from specroad.validation import (validate_model, assess_validation, validation_command_result,
                                ModelDocument, ModelGate)
from specroad.diagnostics import ResultContractError
from specroad.cli.results import serialize_result
from support.model_validation import artifact,doc,profile,no_dependencies


def check(*values, **kwargs):
    return validate_model(tuple(doc(v) for v in values),profile=profile(),**kwargs)


class ValidationDiagnosticWorkTests(unittest.TestCase):
    def test_valid_model_has_no_diagnostics_and_exact_summary(self):
        a=assess_validation(check(artifact()))
        self.assertTrue(a.passed);self.assertEqual(a.summary["checked_artifacts"],1)
        self.assertEqual(a.summary["diagnostic_count"],0)
        self.assertFalse(a.as_dict()["write_authorized"])

    def test_two_parse_failures_are_both_retained(self):
        documents=(ModelDocument("b.json",b'{bad'),ModelDocument("a.json",b'{]'))
        r=validate_model(documents,profile=profile());a=assess_validation(r,documents=documents)
        self.assertEqual(a.exit_code,3)
        self.assertEqual([d.path for d in a.diagnostics],["a.json","b.json"])
        self.assertEqual([d.code for d in a.diagnostics],["SRV001","SRV001"])
        self.assertEqual(a.as_dict()["source_report"],r.data)

    def test_schema_errors_retain_id_and_pointer(self):
        value=artifact();del value["title"]
        a=assess_validation(check(value))
        self.assertEqual(a.diagnostics[0].artifact_id,value["id"])
        self.assertEqual(a.diagnostics[0].location["pointer"],"/title")
        self.assertEqual(a.exit_code,3)

    def test_supplied_source_bytes_must_match_actual_observation(self):
        document=doc(artifact());r=validate_model((document,),profile=profile())
        with self.assertRaises(ResultContractError):
            assess_validation(r,documents=(ModelDocument(document.path,document.content+b" "),))

    def test_unknown_producer_codes_and_details_are_not_lost(self):
        issue={"reason":"vendor_error","code":"VENDOR:99","origin":"analyzer_observation",
               "severity":"warning","artifact_id":artifact()["id"],"extra":{"items":[1,2]}}
        gate=ModelGate("extension:vendor","1",no_dependencies,lambda c:c.result([issue]))
        r=check(artifact(),gates=(gate,));a=assess_validation(r)
        self.assertEqual(a.diagnostics[0].code,"VENDOR:99")
        self.assertEqual(a.diagnostics[0].origin,"analyzer_observation")
        self.assertEqual(a.as_dict()["source_report"],r.data)

    def test_warning_threshold_only_changes_decision(self):
        gate=ModelGate("extension:lint","1",no_dependencies,
                       lambda c:c.result([{"reason":"lint","severity":"warning"}]))
        r=check(artifact(),gates=(gate,))
        a,b=assess_validation(r),assess_validation(r,strict=True)
        self.assertTrue(a.passed);self.assertEqual(b.exit_code,1)
        self.assertEqual(a.diagnostics,b.diagnostics);self.assertEqual(a.as_dict()["source_report"],b.as_dict()["source_report"])

    def test_unavailable_services_cannot_pass_an_empty_result(self):
        a=assess_validation(validate_model((doc(artifact()),)))
        self.assertFalse(a.passed);self.assertEqual(a.exit_code,5)
        self.assertFalse(a.as_dict()["checks_complete"])
        self.assertIn("VALIDATION_UNAVAILABLE",[d.code for d in a.diagnostics])

    def test_command_adapter_preserves_model_failure_and_diagnostics(self):
        r=validate_model((ModelDocument("bad.json",b'{]'),),profile=profile())
        a=assess_validation(r);o=validation_command_result("fixture.validate",a)
        data=json.loads(serialize_result(o))
        self.assertEqual(o.exit_code,3);self.assertEqual(data["summary"]["diagnostic_count"],1)
        self.assertEqual(data["diagnostics"][0]["code"],"SRV001")
        self.assertFalse(data["summary"]["complete"])

    def test_result_mutation_cannot_change_stored_report(self):
        a=assess_validation(check(artifact()))
        data=a.as_dict();data["source_report"]["stages"].clear();data["summary"]["checked_artifacts"]=99
        self.assertEqual(a.summary["checked_artifacts"],1)
        self.assertTrue(a.as_dict()["source_report"]["stages"])

    def test_invalid_observation_not_accepted_as_report(self):
        with self.assertRaises(ResultContractError):assess_validation({})
