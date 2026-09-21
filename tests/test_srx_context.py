"""Behavior of versioned literal expressions and explicit frozen contexts."""

from dataclasses import FrozenInstanceError
import math
import unittest
from specroad.srx import EvaluationContext, SrxProgram, SrxError, evaluate


def context_data():
    return {"artifact": {"statement": "Original", "tags": ["x"]},
            "configuration": {"configuration_id": "cfg", "effective_values": {"platform": "linux"}},
            "project": {"active_profiles": [{"id": "core", "version": "1"}],
                        "statistics": {"artifacts": 1}},
            "relations": {"incoming": [], "outgoing": []}}


def program_data(value):
    return {"language": "srx", "version": "1.0", "expression": {"op": "literal", "value": value}}


def run_value(value):
    return evaluate(SrxProgram(program_data(value), rule_id="rule-1"),
                    EvaluationContext(context_data(), rule_id="rule-1"))


class SrxContextWorkTests(unittest.TestCase):
    def test_literal_null(self):
        self.assertIsNone(run_value(None))

    def test_literal_true(self):
        self.assertIs(run_value(True), True)

    def test_literal_false(self):
        self.assertIs(run_value(False), False)

    def test_literal_integer(self):
        self.assertEqual(run_value(123), 123)
        self.assertIs(type(run_value(123)), int)

    def test_literal_float(self):
        self.assertEqual(run_value(0.125), 0.125)
        self.assertIs(type(run_value(0.125)), float)

    def test_negative_zero_is_not_rewritten(self):
        self.assertEqual(math.copysign(1, run_value(-0.0)), -1)

    def test_literal_string_keeps_unicode(self):
        self.assertEqual(run_value("e\u0301 / 日本語"), "e\u0301 / 日本語")

    def test_literal_array_preserves_order_and_types(self):
        result = run_value([None, False, 0, "0", {"a": 1}])
        self.assertEqual(result, [None, False, 0, "0", {"a": 1}])
        self.assertIs(result[1], False)
        self.assertIs(type(result[2]), int)

    def test_literal_object_preserves_nested_values(self):
        value = {"z": [1, {"b": 2}], "a": None}
        self.assertEqual(run_value(value), value)

    def test_literal_empty_containers(self):
        self.assertEqual(run_value({}), {})
        self.assertEqual(run_value([]), [])

    def test_program_copies_input(self):
        source = program_data({"a": [1]})
        program = SrxProgram(source, rule_id="r")
        source["expression"]["value"]["a"].append(2)
        self.assertEqual(program.value, {"a": [1]})

    def test_result_changes_cannot_change_next_result(self):
        program = SrxProgram(program_data({"a": [1]}), rule_id="r")
        context = EvaluationContext(context_data(), rule_id="r")
        evaluate(program, context)["a"].append(2)
        self.assertEqual(evaluate(program, context), {"a": [1]})

    def test_program_document_is_independent(self):
        program = SrxProgram(program_data([1]), rule_id="r")
        program.document["expression"]["value"].append(2)
        self.assertEqual(program.document, program_data([1]))

    def test_context_copies_each_root(self):
        source = context_data()
        context = EvaluationContext(source, rule_id="r")
        source["artifact"]["tags"].append("later")
        source["configuration"]["effective_values"].clear()
        source["project"]["active_profiles"].clear()
        source["relations"]["incoming"].append({"id": "later"})
        self.assertEqual(context.data, context_data())

    def test_context_access_is_independent(self):
        context = EvaluationContext(context_data(), rule_id="r")
        context.data["project"]["statistics"]["artifacts"] = 99
        self.assertEqual(context.data["project"]["statistics"]["artifacts"], 1)

    def test_context_is_frozen(self):
        context = EvaluationContext(context_data(), rule_id="r")
        with self.assertRaises(FrozenInstanceError):
            context._snapshot = None

    def test_program_is_frozen(self):
        program = SrxProgram(program_data(True), rule_id="r")
        with self.assertRaises(FrozenInstanceError):
            program.rule_id = "different"

    def test_explicit_no_configuration(self):
        data = context_data()
        data["configuration"] = None
        self.assertIsNone(EvaluationContext(data, rule_id="r").data["configuration"])

    def test_missing_root_is_rejected(self):
        for name in context_data():
            data = context_data()
            del data[name]
            with self.assertRaises(SrxError):
                EvaluationContext(data, rule_id="r")

    def test_external_item_context_is_rejected(self):
        data = context_data(); data["item"] = {"x": 1}
        with self.assertRaises(SrxError):
            EvaluationContext(data, rule_id="r")

    def test_foreign_root_is_rejected(self):
        data = context_data(); data["environment"] = {}
        with self.assertRaises(SrxError):
            EvaluationContext(data, rule_id="r")

    def test_unknown_version_is_rejected(self):
        data = program_data(True); data["version"] = "2.0"
        with self.assertRaises(SrxError) as caught:
            SrxProgram(data, rule_id="r")
        self.assertEqual(caught.exception.reason, "unsupported_version")

    def test_textual_expression_is_rejected(self):
        with self.assertRaises(SrxError):
            SrxProgram("1+1", rule_id="r")

    def test_unsupported_operator_is_not_false(self):
        data = program_data(True); data["expression"] = {"op": "any", "array": {"op": "literal", "value": []}, "where": {"op": "literal", "value": True}}
        with self.assertRaises(SrxError) as caught:
            SrxProgram(data, rule_id="r")
        self.assertEqual(caught.exception.reason, "unsupported_operator")

    def test_unknown_expression_fields_rejected(self):
        data = program_data(True); data["expression"]["eval"] = "print(1)"
        with self.assertRaises(SrxError):
            SrxProgram(data, rule_id="r")

    def test_expression_shaped_literal_remains_data(self):
        value = {"op": "shell", "args": ["not-a-command"], "__class__": "module"}
        self.assertEqual(run_value(value), value)

    def test_literal_still_requires_explicit_context(self):
        with self.assertRaises(SrxError) as caught:
            evaluate(SrxProgram(program_data(True), rule_id="r"), None)
        self.assertEqual(caught.exception.reason, "context_required")

    def test_error_keeps_machine_context(self):
        data = program_data(True); data["expression"]["op"] = 42
        with self.assertRaises(SrxError) as caught:
            SrxProgram(data, rule_id="RULE-42")
        diagnostic = caught.exception.diagnostic()
        self.assertEqual(diagnostic["code"], "SRV110")
        self.assertEqual(diagnostic["rule_id"], "RULE-42")
        self.assertEqual(diagnostic["expression_pointer"], "/expression/op")
        self.assertEqual(diagnostic["actual_type"], "number")

    def test_cycle_is_rejected_without_recursion(self):
        value = []; value.append(value)
        with self.assertRaises(SrxError) as caught:
            run_value(value)
        self.assertEqual(caught.exception.reason, "cyclic_json_value")

    def test_nonfinite_literal_rejected(self):
        for value in (float("inf"), float("-inf"), float("nan")):
            with self.assertRaises(SrxError):
                run_value(value)
