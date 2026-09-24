"""Boundary, determinism and semantic consistency regressions, no text oracles."""
import copy
import json
import unittest
from itertools import product
from unittest.mock import patch
from specroad.diagnostics import (Diagnostic, ResultContractError, FailPolicy, assess_diagnostics,
                                  from_model_error, code_metadata, diagnostic_schema, known_codes)
from specroad.model.errors import ModelError
from specroad.model._schema import validate_builtin
from specroad.storage.json_syntax import parse_json_object
from test_diagnostics import finding


class DiagnosticRightTests(unittest.TestCase):
    def test_numeric_coordinate_tie_break_is_not_lexical(self):
        a,b=finding(location={"line":10}),finding(location={"line":2})
        self.assertEqual(assess_diagnostics([a,b]).diagnostics,(b,a))

    def test_line_range_is_rejected_even_when_columns_are_unknown(self):
        with self.assertRaises(ResultContractError):finding(location={"line":4,"end_line":2})

    def test_origin_and_rule_ties_are_deterministic(self):
        a=finding(origin="profile_rule",rule_id="z");b=finding(origin="core_rule",rule_id="a")
        self.assertEqual(assess_diagnostics([a,b]).diagnostics,(b,a))

    def test_distinct_unicode_forms_are_not_normalized(self):
        a,b=finding(path="e\u0301.json"),finding(path="é.json")
        result=assess_diagnostics([a,b]);self.assertEqual({x.path for x in result.diagnostics},{a.path,b.path})
        self.assertEqual(result.summary["diagnostic_count"],2)

    def test_complete_diagnostic_count_exceeds_display_limits(self):
        values=[finding("VENDOR:"+str(i),artifact_id="A") for i in range(1501)]
        result=assess_diagnostics(values,checked_ids=["A"])
        self.assertEqual(len(result.diagnostics),1501);self.assertEqual(result.summary["diagnostic_count"],1501)
        self.assertEqual(result.summary["checked_artifacts"],1)

    def test_all_severity_sequences_obey_only_explicit_threshold(self):
        for size in range(5):
            for sequence in product(("error","warning","info"),repeat=size):
                values=[finding("VENDOR:"+str(i),severity=s) for i,s in enumerate(sequence)]
                for threshold in ("error","warning"):
                    result=assess_diagnostics(values,fail_on=threshold)
                    expected="error" in sequence or (threshold=="warning" and "warning" in sequence)
                    self.assertEqual(result.exit_code,1 if expected else 0)
                    self.assertEqual(sum(result.summary["diagnostics_by_severity"].values()),size)

    def test_strict_never_weakens_explicit_threshold(self):
        for threshold in ("error","warning"):
            result=assess_diagnostics([finding()],fail_on=threshold,strict=True)
            self.assertEqual(result.exit_code,1);self.assertEqual(result.diagnostics[0].severity,"warning")

    def test_policy_validates_all_items_before_short_circuit(self):
        class Foreign:
            @property
            def severity(self): raise AssertionError("foreign execution")
        with self.assertRaises(ResultContractError):FailPolicy().reached([finding(severity="error"),Foreign()])

    def test_foreign_location_is_not_converted(self):
        class Foreign:
            def __iter__(self):raise AssertionError("foreign execution")
        with self.assertRaises(ResultContractError):finding(location=Foreign())

    def test_foreign_string_is_not_converted(self):
        class Foreign:
            def __str__(self):raise AssertionError("foreign execution")
        with self.assertRaises(ResultContractError):finding(code=Foreign())

    def test_from_dict_requires_exact_known_fields(self):
        data=finding().as_dict();del data["origin"]
        with self.assertRaises(ResultContractError):Diagnostic.from_dict(data)
        with self.assertRaises(ResultContractError):Diagnostic.from_dict({**finding().as_dict(),"ignored":True})

    def test_schema_copies_do_not_change_other_calls(self):
        schema=diagnostic_schema();schema["properties"]["origin"]["enum"].append("false_origin")
        with self.assertRaises(ModelError):validate_builtin({**finding().as_dict(),"origin":"false_origin"},diagnostic_schema())

    def test_catalog_defaults_never_overwrite_observed_severity(self):
        self.assertEqual(code_metadata("SRV053")["default_severity"],"warning")
        self.assertEqual(finding("SRV053","error").severity,"error")

    def test_catalog_minimum_known_codes_have_stable_severity(self):
        expected={"SRV001":"error","SRV025":"warning","SRV165":"info","SRV197":"error"}
        for key,value in expected.items(): self.assertEqual(code_metadata(key)["default_severity"],value)
        self.assertEqual(len(known_codes()),len(set(known_codes())))

    def test_source_offset_cannot_exceed_supplied_bytes(self):
        with self.assertRaises(ResultContractError):from_model_error(ModelError("invalid_utf8",position=50),source=b'bad')

    def test_source_offset_cannot_contradict_line_or_column(self):
        with self.assertRaises(ResultContractError):
            from_model_error(ModelError("invalid_json",position=1,line=8,column=2),source=b'{]')

    def test_utf8_coordinates_count_characters_not_bytes(self):
        raw='{"é": "'.encode()+b'\xff"}'
        try:parse_json_object(raw)
        except ModelError as error:d=from_model_error(error,source=raw)
        self.assertEqual(d.location["byte_offset"],8);self.assertEqual(d.location["character_offset"],7)
        self.assertEqual(d.location["column"],8)

    def test_partial_coordinate_observation_does_not_invent_end_positions(self):
        d=from_model_error(ModelError("invalid_json",position=1,line=1,column=2),source=b'{]')
        self.assertNotIn("end_line",d.location);self.assertNotIn("end_column",d.location)

    def test_schema_shape_and_constructor_agree_on_origins(self):
        for origin in ("core_rule","profile_rule","import_rule","migration_rule","merge_rule","analyzer_observation","ai_suggestion"):
            d=finding(origin=origin);validate_builtin(d.as_dict(),diagnostic_schema())

    def test_both_source_and_observations_remain_unchanged(self):
        raw=b'{"a":]}'
        try:parse_json_object(raw,path="a.json")
        except ModelError as error:
            before=error.diagnostic();from_model_error(error,source=raw);self.assertEqual(error.diagnostic(),before)
        self.assertEqual(raw,b'{"a":]}')

    def test_no_import_file_or_process_request_is_executed_from_findings(self):
        value=finding(code="__import__('os')",path="https://example.invalid/side-effect",remediation="run a command")
        with patch("builtins.open",side_effect=AssertionError("file opened")):
            result=assess_diagnostics([value],strict=True)
        self.assertEqual(result.diagnostics,(value,));self.assertFalse(result.as_dict()["write_authorized"])

    def test_empty_completed_result_is_not_a_release_claim(self):
        value=assess_diagnostics([],checked_ids=[]).as_dict()
        self.assertEqual(value["exit_code"],0);self.assertFalse(value["approval_granted"])
        self.assertFalse(value["write_authorized"])

    def test_boolean_and_float_counts_are_not_accepted_as_coordinates(self):
        for field in ("line","column","character_offset","byte_offset"):
            for v in (True,1.0,"1"):
                with self.subTest(field=field,value=v),self.assertRaises(ResultContractError):finding(location={field:v})

    def test_returned_lists_do_not_mutate_assessment(self):
        a=assess_diagnostics([finding()],checked_ids=["A"]);b=a.as_dict();b["diagnostics"].clear();b["checked_ids"].clear()
        self.assertEqual(len(a.diagnostics),1);self.assertEqual(a.checked_ids,("A",))
