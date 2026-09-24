"""Machine diagnostic contracts; no assertions on messages, styling or docs."""
import json
import unittest
from dataclasses import FrozenInstanceError
from itertools import permutations

from specroad.diagnostics import (Diagnostic, FailPolicy, ResultContractError, assess_diagnostics,
                                  code_metadata, diagnostic_schema, from_model_error)
from specroad.model._schema import validate_builtin
from specroad.model.errors import ModelError
from specroad.storage.json_syntax import parse_json_object
from specroad.cli.results import CommandResult, serialize_result


def finding(code="SRV053", severity="warning", **kwargs):
    return Diagnostic(code, severity, "lint", "A finding.", **kwargs)


class DiagnosticWorkTests(unittest.TestCase):
    def test_serialized_contract_has_all_required_fields(self):
        data=finding().as_dict()
        self.assertEqual(set(data), {"code","severity","category","message","origin","rule_id",
            "artifact_id","path","location","rationale","remediation","related_ids"})
        self.assertEqual(data["origin"], "core_rule")
        validate_builtin(data,diagnostic_schema())

    def test_all_seven_origins_remain_distinct(self):
        for origin in ("core_rule","profile_rule","import_rule","migration_rule","merge_rule",
                       "analyzer_observation","ai_suggestion"):
            with self.subTest(origin=origin): self.assertEqual(finding(origin=origin).as_dict()["origin"],origin)

    def test_invalid_origin_is_not_mislabeled_core(self):
        for value in ("core","external",None,True,[],"",1):
            with self.subTest(value=value),self.assertRaises(ResultContractError): finding(origin=value)

    def test_only_three_severities_are_accepted(self):
        for value in ("fatal", "Warning", None, 1, []):
            with self.subTest(value=value),self.assertRaises(ResultContractError): finding(severity=value)
        for value in ("error","warning","info"):self.assertEqual(finding(severity=value).severity,value)

    def test_unknown_code_and_rule_id_are_preserved(self):
        value=finding("VENDOR:future-11",rule_id="unknown:rule")
        self.assertIsNone(code_metadata(value.code))
        self.assertEqual(Diagnostic.from_dict(value.as_dict()),value)
        self.assertEqual(assess_diagnostics([value]).diagnostics[0].rule_id,"unknown:rule")

    def test_location_is_owned_and_cannot_be_changed(self):
        where={"pointer":"/a~1b/~0","line":2,"column":7}
        d=finding(location=where);where["line"]=99
        self.assertEqual(d.location["line"],2)
        with self.assertRaises(TypeError):d.location["line"]=5
        copy=d.as_dict();copy["location"]["line"]=44
        self.assertEqual(d.location["line"],2)
        with self.assertRaises(FrozenInstanceError):d.code="other"

    def test_related_ids_are_values_not_verified_references(self):
        ids=["missing:B","A","A"]
        d=finding(related_ids=ids);ids.append("later")
        self.assertEqual(d.related_ids,("A","missing:B"))
        d.as_dict()["related_ids"].append("mutation")
        self.assertEqual(d.related_ids,("A","missing:B"))

    def test_location_allows_null_and_root_pointer(self):
        self.assertIsNone(finding().location)
        self.assertEqual(finding(location={"pointer":"","line":None}).location["pointer"],"")

    def test_invalid_pointers_and_coordinates_are_rejected(self):
        for loc in ({"pointer":"title"},{"pointer":"/~2"},{"pointer":"/~"},{"line":0},
                    {"column":False},{"byte_offset":-1},{"line":1.2},{"other":9}):
            with self.subTest(loc=loc),self.assertRaises(ResultContractError): finding(location=loc)

    def test_coordinates_have_distinct_units(self):
        d=finding(location={"line":1,"column":1,"byte_offset":0,"character_offset":0})
        self.assertEqual(d.as_dict()["location"]["byte_offset"],0)
        with self.assertRaises(ResultContractError):finding(location={"line":2,"column":8,"end_line":2,"end_column":7})

    def test_sort_prioritizes_severity_before_file(self):
        a=finding("I","info",path="a.json");b=finding("E","error",path="z.json")
        self.assertEqual([x.code for x in assess_diagnostics([a,b]).diagnostics],["E","I"])

    def test_sort_file_artifact_pointer_code_order(self):
        values=[finding("B",path="b.json"),finding("Z",path="a.json",artifact_id="B"),
                finding("A",path="a.json",artifact_id="A",location={"pointer":"/z"}),
                finding("Z",path="a.json",artifact_id="A",location={"pointer":"/a"})]
        self.assertEqual([d.code for d in assess_diagnostics(values).diagnostics],["Z","A","Z","B"])

    def test_input_permutations_have_identical_machine_results(self):
        values=[finding("B",path="b.json"),finding("A","error"),finding("C",location={"pointer":"/c"})]
        expected=assess_diagnostics(values).as_dict()
        for shuffled in permutations(values):self.assertEqual(assess_diagnostics(shuffled).as_dict(),expected)

    def test_missing_location_differs_from_root_location(self):
        absent=finding("A");root=finding("A",location={"pointer":""})
        self.assertEqual(assess_diagnostics([root,absent]).diagnostics,(absent,root))

    def test_duplicate_findings_are_not_silently_deduplicated(self):
        d=finding();a=assess_diagnostics([d,d],checked_ids=["B","A","B"])
        self.assertEqual(len(a.diagnostics),2)
        self.assertEqual(a.summary,{"checked_artifacts":2,"diagnostic_count":2,
            "diagnostics_by_severity":{"error":0,"warning":2,"info":0}})

    def test_warning_does_not_fail_default_policy(self):
        d=finding();a=assess_diagnostics([d]);self.assertTrue(a.passed);self.assertEqual(a.exit_code,0)
        self.assertEqual(a.diagnostics[0].severity,"warning")

    def test_warning_fails_at_warning_threshold_without_promotion(self):
        d=finding();a=assess_diagnostics([d],fail_on="warning")
        self.assertFalse(a.passed);self.assertEqual(a.exit_code,1);self.assertEqual(a.diagnostics,(d,))

    def test_strict_uses_warning_threshold_without_executing_rules(self):
        a=assess_diagnostics([finding()],strict=True)
        self.assertEqual(a.as_dict()["fail_on"],"warning");self.assertEqual(a.exit_code,1)

    def test_info_does_not_fail_strict(self):
        self.assertTrue(assess_diagnostics([finding(severity="info")],strict=True).passed)

    def test_errors_fail_both_thresholds(self):
        for threshold in ("warning","error"):
            self.assertEqual(assess_diagnostics([finding(severity="error")],fail_on=threshold).exit_code,1)

    def test_incomplete_empty_observation_is_never_success_or_checkpoint(self):
        a=assess_diagnostics([],complete=False)
        self.assertFalse(a.passed);self.assertEqual(a.exit_code,5)
        self.assertFalse(a.as_dict()["approval_granted"])
        with self.assertRaises(TypeError):bool(a)

    def test_independent_model_error_retains_its_exit_class(self):
        for code in range(2,8):
            self.assertEqual(assess_diagnostics([],operational_exit_code=code).exit_code,code)
        for code in (0,1,8,False,"3"):
            with self.subTest(code=code),self.assertRaises(ResultContractError):assess_diagnostics([],operational_exit_code=code)

    def test_policy_rejects_coercible_values(self):
        for value in (None,"info",[],1):
            with self.subTest(value=value),self.assertRaises(ResultContractError):FailPolicy(value)
        with self.assertRaises(ResultContractError):FailPolicy(strict=1)

    def test_json_parse_failure_retains_file_line_and_column(self):
        raw='{"é": 1,\n "b": ]}'.encode()
        try:parse_json_object(raw,path="requirements/a.json")
        except ModelError as error:d=from_model_error(error,source=raw)
        self.assertEqual((d.code,d.path,d.artifact_id),("SRV001","requirements/a.json",None))
        self.assertEqual((d.location["line"],d.location["column"]),(2,7))
        self.assertEqual(d.location["byte_offset"],d.location["character_offset"]+1)

    def test_utf8_failure_has_byte_position_without_fabricated_columns(self):
        raw=b'{"a": "\xff"}'
        try:parse_json_object(raw,path="bad.json")
        except ModelError as error:
            d=from_model_error(error);enriched=from_model_error(error,source=raw)
        self.assertEqual(d.location["byte_offset"],7);self.assertIsNone(d.location["line"])
        self.assertEqual(enriched.location["column"],8)

    def test_duplicate_key_retains_pointer_without_guessed_position(self):
        raw=b'{"a/b": 1, "a/b": 2}'
        try:parse_json_object(raw,path="bad.json")
        except ModelError as error:d=from_model_error(error,source=raw)
        self.assertEqual(d.location["pointer"],"/a~1b")
        self.assertIsNone(d.location["byte_offset"])

    def test_schema_failure_retains_supplied_unknown_artifact_id(self):
        d=from_model_error(ModelError("field_required",path="a.json",pointer="/title"),artifact_id="unresolved:ID")
        self.assertEqual((d.code,d.artifact_id,d.location["pointer"]),("SRV002","unresolved:ID","/title"))

    def test_existing_envelope_uses_same_machine_diagnostics(self):
        findings=[finding("W",path="a.json"),finding("E","error",path="z.json")]
        result=CommandResult("fixture.check",diagnostics=findings)
        parsed=json.loads(serialize_result(result))
        self.assertEqual(parsed["diagnostics"],[d.as_dict() for d in assess_diagnostics(findings).diagnostics])

    def test_schema_rejects_unknown_origin_and_severity(self):
        data=finding().as_dict()
        for key,value in (("origin","core"),("severity","fatal")):
            with self.assertRaises(ModelError):validate_builtin({**data,key:value},diagnostic_schema())

    def test_catalog_returns_detached_stable_metadata(self):
        data=code_metadata("SRV001");self.assertEqual(data["default_severity"],"error")
        data["default_severity"]="info"
        self.assertEqual(code_metadata("SRV001")["default_severity"],"error")

    def test_structural_errors_cannot_be_downgraded(self):
        for key in ("SRV001", "SRV002", "SRV080", "SRV042"):
            with self.subTest(code=key),self.assertRaises(ResultContractError):finding(key,"warning")
        with self.assertRaises(ResultContractError):finding("CUSTOM","info",rule_id="core:requirement-verification")

    def test_pointer_can_reference_an_escaped_nul_json_key(self):
        d=finding(location={"pointer":"/a\0b"})
        self.assertEqual(Diagnostic.from_dict(json.loads(json.dumps(d.as_dict()))),d)
