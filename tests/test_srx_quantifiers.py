"""Ordered quantifiers over explicit, owned SRX data (Annex B.4)."""
import copy
import itertools
import json
from pathlib import Path
import unittest

from specroad.srx import (EvaluationContext, SrxError, SrxProgram, evaluate,
                          parse_program, read_field)
from support.srx import binary, expression_document, field, literal, quantifier, roots, run


def item(pointer=""):
    return field(pointer, context="item")


class SrxQuantifierTests(unittest.TestCase):
    def test_any_finds_matching_element(self):
        self.assertIs(run(quantifier("any", literal([1, 2, 3]), binary("eq", item(), literal(2)))), True)

    def test_any_without_match(self):
        self.assertIs(run(quantifier("any", literal([1, 2]), binary("eq", item(), literal(3)))), False)

    def test_all_requires_every_element(self):
        self.assertIs(run(quantifier("all", literal([1, 2]), binary("gt", item(), literal(0)))), True)
        self.assertIs(run(quantifier("all", literal([1, -1]), binary("gt", item(), literal(0)))), False)

    def test_none_is_negated_any(self):
        predicate = binary("eq", item(), literal(2))
        for values in ([], [1], [1, 2], [2, 2]):
            self.assertIs(run(quantifier("none", literal(values), predicate)),
                          not run(quantifier("any", literal(values), predicate)))

    def test_empty_arrays_have_normative_results(self):
        for op, expected in (("any", False), ("all", True), ("none", True)):
            self.assertIs(run(quantifier(op, literal([]), literal(True))), expected)

    def test_empty_array_does_not_evaluate_predicate(self):
        bad = {"op": "count", "arg": literal(1)}
        for op, expected in (("any", False), ("all", True), ("none", True)):
            self.assertIs(run(quantifier(op, literal([]), bad)), expected)

    def test_empty_array_still_validates_predicate_ast(self):
        for op in ("any", "all", "none"):
            with self.assertRaises(SrxError):
                run(quantifier(op, literal([]), {"op": "not-yet-supported"}))

    def test_empty_array_still_validates_predicate_pointer(self):
        with self.assertRaises(SrxError):
            run(quantifier("all", literal([]), field("/~2", "item")))

    def test_scalar_predicates_must_be_boolean(self):
        for value in (None, 0, 1, 0.0, "", "true", [], {}, [True]):
            for op in ("any", "all", "none"):
                with self.subTest(op=op, kind=type(value).__name__), self.assertRaises(SrxError) as error:
                    run(quantifier(op, literal([0]), literal(value)))
                self.assertEqual(error.exception.pointer, "/expression/where")
                self.assertEqual(error.exception.expected, "boolean")

    def test_missing_predicate_is_type_error(self):
        with self.assertRaises(SrxError) as error:
            run(quantifier("any", literal([{}]), item("/absent")))
        self.assertEqual(error.exception.actual, "missing")

    def test_null_element_is_present_not_unbound(self):
        self.assertIs(run(quantifier("all", literal([None]), {"op": "exists", "arg": item()})), True)

    def test_false_and_zero_elements_are_present(self):
        self.assertIs(run(quantifier("all", literal([False, 0, "", [], {}]),
                                     {"op": "exists", "arg": item()})), True)

    def test_missing_item_field_follows_existing_semantics(self):
        self.assertIs(run(quantifier("none", literal([{}, {}]),
                                     {"op": "exists", "arg": item("/absent")})), True)

    def test_array_expression_can_use_artifact_fields(self):
        self.assertIs(run(quantifier("any", field("/values"), item()), {"values": [False, True]}), True)

    def test_non_array_inputs_are_not_coerced(self):
        for value in (None, True, 1, 1.0, "abc", {"0": True}):
            with self.subTest(kind=type(value).__name__), self.assertRaises(SrxError) as error:
                run(quantifier("any", literal(value), literal(True)))
            self.assertEqual(error.exception.pointer, "/expression/array")
            self.assertEqual(error.exception.expected, "array")

    def test_missing_array_is_error_not_empty(self):
        with self.assertRaises(SrxError) as error:
            run(quantifier("none", field("/missing"), literal(True)))
        self.assertEqual(error.exception.actual, "missing")

    def test_item_is_not_a_global_program_root(self):
        with self.assertRaises(SrxError):
            run(item())

    def test_item_cannot_be_supplied_in_public_context(self):
        data = roots(); data["item"] = True
        with self.assertRaises(SrxError):
            EvaluationContext(data, rule_id="scope")

    def test_item_cannot_be_read_outside_evaluation(self):
        context = EvaluationContext(roots(), rule_id="scope")
        with self.assertRaises(SrxError):
            read_field(context, "item", "", rule_id="scope")

    def test_top_level_array_expression_has_no_item_binding(self):
        with self.assertRaises(SrxError):
            run(quantifier("any", item(), literal(True)))

    def test_sibling_expression_cannot_see_quantifier_item(self):
        with self.assertRaises(SrxError):
            run(binary("or", quantifier("any", literal([True]), item()), item()))

    def test_all_explicit_roots_remain_available_in_predicate(self):
        data = roots({"want": 3}); data["relations"] = [1, 2, 3]
        data["configuration"] = {"configuration_id": "cfg", "effective_values": {"want": 3}}
        data["project"] = {"want": 3}
        predicate = {"op": "and", "args": [binary("eq", item(), field(p, c)) for c, p in (
            ("artifact", "/want"), ("project", "/want"), ("configuration", "/effective_values/want"))]}
        self.assertIs(run(quantifier("any", field("", "relations"), predicate), context=data), True)

    def test_escaped_item_pointer(self):
        self.assertIs(run(quantifier("all", literal([{"a/b": {"~": True}}]), item("/a~1b/~0"))), True)

    def test_array_element_pointer(self):
        self.assertIs(run(quantifier("all", literal([[True], [True]]), item("/0"))), True)

    def test_invalid_array_index_retains_error(self):
        with self.assertRaises(SrxError) as error:
            run(quantifier("any", literal([[True]]), item("/01")))
        self.assertEqual(error.exception.reason, "invalid_array_index")

    def test_unknown_quantifier_fields_rejected(self):
        for key, value in (("args", []), ("limit", 1), ("context", "item"), ("short_circuit", True)):
            node = quantifier("any", literal([True]), item()); node[key] = value
            with self.assertRaises(SrxError): run(node)

    def test_required_quantifier_fields(self):
        for key in ("array", "where"):
            node = quantifier("any", literal([True]), item()); del node[key]
            with self.assertRaises(SrxError): run(node)

    def test_array_and_predicate_require_expressions(self):
        for key in ("array", "where"):
            for value in (None, True, 1, "item", []):
                node = quantifier("all", literal([]), literal(True)); node[key] = value
                with self.assertRaises(SrxError): run(node)

    def test_quantifier_shaped_literals_remain_data(self):
        data = {"op": "any", "array": "not AST", "where": {"context": "item"}}
        self.assertIs(run(quantifier("all", literal([data]), binary("eq", item(), literal(data)))), True)

    def test_owned_input_and_context_unchanged(self):
        node = quantifier("all", field("/rows"), item("/ok")); data = roots({"rows": [{"ok": True}]})
        original = copy.deepcopy((node, data))
        program = SrxProgram(expression_document(node), rule_id="owned")
        context = EvaluationContext(data, rule_id="owned")
        self.assertIs(evaluate(program, context), True)
        self.assertEqual((node, data), original)
        data["artifact"]["rows"][0]["ok"] = False; node["where"] = literal(False)
        self.assertIs(evaluate(program, context), True)

    def test_same_program_reused_without_leaking_elements(self):
        program = SrxProgram(expression_document(quantifier("all", field("/xs"), item())), rule_id="repeat")
        for values, expected in (([True], True), ([False], False), ([], True), ([True, True], True)):
            self.assertIs(evaluate(program, EvaluationContext(roots({"xs": values}), rule_id="repeat")), expected)

    def test_boolean_truth_tables_up_to_six_elements(self):
        for size in range(7):
            for values in itertools.product((False, True), repeat=size):
                for op, expected in (("any", any(values)), ("all", all(values)), ("none", not any(values))):
                    self.assertIs(run(quantifier(op, literal(list(values)), item())), expected)

    def test_versioned_positive_negative_and_empty_vectors(self):
        path = Path(__file__).resolve().parent / "vectors/srx_quantifiers_v1.json"
        vectors = json.loads(path.read_bytes())
        self.assertEqual(vectors["format_version"], 1)
        for vector in vectors["cases"]:
            with self.subTest(vector=vector["id"]):
                if "expected" in vector:
                    self.assertIs(run(vector["expression"], context=vector["context"]), vector["expected"])
                else:
                    with self.assertRaises(SrxError) as error:
                        run(vector["expression"], context=vector["context"])
                    self.assertEqual(error.exception.reason, vector["reason"])

    def test_utf8_byte_program_is_supported(self):
        document = expression_document(quantifier("all", literal(["日本語", "Deutsch"]),
                                                  binary("gt", {"op": "length", "arg": item()}, literal(0))))
        raw = json.dumps(document, ensure_ascii=False).encode()
        program = parse_program(raw, rule_id="bytes")
        self.assertEqual(program.source_bytes, raw)
        self.assertIs(evaluate(program, EvaluationContext(roots(), rule_id="bytes")), True)
