"""Feldwerte, RFC-6901-Adressen und Missing sind fachliche Datenverträge."""
import copy
import json
import unittest
from specroad.srx import MISSING, SrxError, SrxProgram, EvaluationContext, evaluate, value_type
from support.srx import field, literal, roots, run, expression_document


class SrxFieldTests(unittest.TestCase):
    def test_object_field(self):
        self.assertEqual(run(field("/name"), {"name": "value"}), "value")

    def test_root_pointer(self):
        self.assertEqual(run(field(), {"k": [1]}), {"k": [1]})

    def test_empty_member_name(self):
        self.assertEqual(run(field("/"), {"": 7}), 7)

    def test_nested_object(self):
        self.assertEqual(run(field("/a/b"), {"a": {"b": False}}), False)

    def test_array_index(self):
        self.assertEqual(run(field("/a/1"), {"a": [10, 20]}), 20)

    def test_object_numeric_key_is_not_array_index(self):
        self.assertEqual(run(field("/01"), {"01": 6}), 6)

    def test_slash_and_tilde_escaping(self):
        self.assertEqual(run(field("/a~1b/~0name"), {"a/b": {"~name": 2}}), 2)

    def test_escape_decoding_is_single_pass(self):
        self.assertEqual(run(field("/~01"), {"~1": 3, "/": 4}), 3)

    def test_percent_is_literal(self):
        self.assertEqual(run(field("/a%2Fb"), {"a%2Fb": 5, "a/b": 8}), 5)

    def test_unicode_is_not_normalized(self):
        self.assertEqual(run(field("/e\u0301"), {"e\u0301": 1, "é": 2}), 1)

    def test_absent_member_is_missing(self):
        self.assertIs(run(field("/absent")), MISSING)

    def test_missing_intermediate(self):
        self.assertIs(run(field("/a/b")), MISSING)

    def test_null_is_not_missing(self):
        self.assertIsNone(run(field("/a"), {"a": None}))

    def test_scalar_has_no_children(self):
        for value in (None, False, 0, "text"):
            self.assertIs(run(field("/a/x"), {"a": value}), MISSING)

    def test_empty_array_has_no_element(self):
        self.assertIs(run(field("/a/0"), {"a": []}), MISSING)

    def test_out_of_range(self):
        self.assertIs(run(field("/a/2"), {"a": [0, 1]}), MISSING)

    def test_dash_is_nonexistent_not_append(self):
        data = {"a": [1]}
        self.assertIs(run(field("/a/-"), data), MISSING)
        self.assertEqual(data, {"a": [1]})

    def test_exists_missing_is_false(self):
        self.assertIs(run({"op": "exists", "arg": field("/absent")}), False)

    def test_exists_null_is_true(self):
        self.assertIs(run({"op": "exists", "arg": literal(None)}), True)

    def test_exists_false_zero_and_empty_values(self):
        for value in (False, 0, "", [], {}):
            self.assertIs(run({"op": "exists", "arg": literal(value)}), True)

    def test_nested_exists_keeps_boolean(self):
        self.assertIs(run({"op": "exists", "arg": {"op": "exists", "arg": field("/absent")}}), True)

    def test_project_root(self):
        data = roots(); data["project"] = {"statistics": {"count": 7}}
        self.assertEqual(run(field("/statistics/count", "project"), context=data), 7)

    def test_configuration_root_can_be_null(self):
        self.assertIsNone(run(field("", "configuration")))
        self.assertIs(run(field("/effective_values", "configuration")), MISSING)

    def test_configuration_values(self):
        data = roots(); data["configuration"] = {"configuration_id": "cfg", "effective_values": {"p": 3}}
        self.assertEqual(run(field("/effective_values/p", "configuration"), context=data), 3)

    def test_relations_are_supplied_data(self):
        data = roots(); data["relations"] = [{"type": "depends_on"}]
        self.assertEqual(run(field("/0/type", "relations"), context=data), "depends_on")

    def test_result_is_independent_of_context(self):
        ctx = EvaluationContext(roots({"a": [1]}), rule_id="r")
        program = SrxProgram(expression_document(field("/a")), rule_id="r")
        evaluate(program, ctx).append(2)
        self.assertEqual(evaluate(program, ctx), [1])

    def test_input_ast_is_unmodified(self):
        node = {"op": "exists", "arg": field("/a")}; before = copy.deepcopy(node)
        run(node, {"a": False})
        self.assertEqual(node, before)

    def test_all_value_kinds(self):
        for value, expected in ((MISSING,"missing"), (None,"null"), (False,"boolean"),
                (1,"number"), (1.0,"number"), ("1","string"), ([],"array"), ({},"object")):
            self.assertEqual(value_type(value), expected)

    def test_missing_cannot_be_serialized_as_null(self):
        with self.assertRaises(TypeError):
            json.dumps({"value": MISSING})

    def test_missing_has_no_truth_coercion(self):
        with self.assertRaises(TypeError):
            bool(MISSING)

    def test_missing_cannot_be_a_literal(self):
        with self.assertRaises(SrxError):
            run(literal(MISSING))

    def test_dynamic_pointer_rejected(self):
        with self.assertRaises(SrxError):
            run(field(literal("/name")))

    def test_unknown_named_context_rejected(self):
        with self.assertRaises(SrxError):
            run(field("", "environment"))

    def test_bad_pointer_escape_rejected(self):
        with self.assertRaises(SrxError):
            run(field("/bad~2"))

    def test_relative_pointer_rejected(self):
        for pointer in ("a/b", "../b", "/a/../b"):
            with self.assertRaises(SrxError):
                run(field(pointer))

    def test_exists_requires_expression_argument(self):
        with self.assertRaises(SrxError):
            run({"op": "exists", "arg": None})

    def test_field_value_property_requires_evaluation(self):
        p = SrxProgram(expression_document(field("/a")), rule_id="r")
        with self.assertRaises(SrxError):
            _ = p.value
