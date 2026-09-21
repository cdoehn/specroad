"""Observable SRX sequence behavior, not human-readable output."""
import copy
import unittest
from specroad.srx import SrxError
from support.srx import binary, field, literal, run


def unary(op, value):
    return {"op": op, "arg": value}


class SrxCollectionsTests(unittest.TestCase):
    def test_in_scalar_array(self):
        self.assertIs(run(binary("in",literal(2),literal([1,2,3]))),True)

    def test_in_absent(self):
        self.assertIs(run(binary("in",literal(4),literal([1,2,3]))),False)

    def test_in_null(self):
        self.assertIs(run(binary("in",literal(None),literal([None]))),True)

    def test_in_deep_objects(self):
        self.assertIs(run(binary("in",literal({"x":[1,None],"y":False}),literal([{"y":False,"x":[1,None]}]))),True)

    def test_in_array_order_is_significant(self):
        self.assertIs(run(binary("in",literal([1,2]),literal([[2,1]]))),False)

    def test_contains_string(self):
        self.assertIs(run(binary("contains",literal("übermorgen"),literal("morgen"))),True)

    def test_contains_string_absent(self):
        self.assertIs(run(binary("contains",literal("abcdef"),literal("cdg"))),False)

    def test_contains_array(self):
        self.assertIs(run(binary("contains",literal([1,2,3]),literal(2))),True)

    def test_contains_array_absent(self):
        self.assertIs(run(binary("contains",literal([1,2,3]),literal(4))),False)

    def test_contains_deep_object(self):
        self.assertIs(run(binary("contains",literal([{"a":[False]}]),literal({"a":[False]}))),True)

    def test_starts_with(self):
        self.assertIs(run(binary("starts_with",literal("SpecRoad"),literal("Spec"))),True)

    def test_starts_with_not_anywhere(self):
        self.assertIs(run(binary("starts_with",literal("SpecRoad"),literal("Road"))),False)

    def test_ends_with(self):
        self.assertIs(run(binary("ends_with",literal("SpecRoad"),literal("Road"))),True)

    def test_ends_with_not_anywhere(self):
        self.assertIs(run(binary("ends_with",literal("SpecRoad"),literal("Spec"))),False)

    def test_length_string(self):
        self.assertEqual(run(unary("length",literal("abc"))),3)

    def test_length_codepoints(self):
        self.assertEqual(run(unary("length",literal("😀e\u0301"))),3)

    def test_length_array(self):
        self.assertEqual(run(unary("length",literal([1,None,False,{"x":1}]))),4)

    def test_length_object(self):
        self.assertEqual(run(unary("length",literal({"nested":{"x":1},"b":[]}))),2)

    def test_count_array(self):
        self.assertEqual(run(unary("count",literal([1,1,None,False]))),4)

    def test_count_rejects_string(self):
        with self.assertRaises(SrxError):run(unary("count",literal("abc")))

    def test_count_does_not_deduplicate(self):
        self.assertEqual(run(unary("count",literal([1,1,1]))),3)

    def test_empty_lengths(self):
        for value in ("",[],{}):self.assertEqual(run(unary("length",literal(value))),0)

    def test_empty_membership(self):
        self.assertIs(run(binary("in",literal(1),literal([]))),False)
        self.assertIs(run(binary("contains",literal([]),literal(1))),False)

    def test_empty_string_needles(self):
        for op in ("contains","starts_with","ends_with"):
            self.assertIs(run(binary(op,literal(""),literal(""))),True)
            self.assertIs(run(binary(op,literal("abc"),literal(""))),True)

    def test_no_unicode_normalization(self):
        for op in ("contains","starts_with","ends_with"):
            self.assertIs(run(binary(op,literal("é"),literal("e\u0301"))),False)

    def test_no_case_folding(self):
        for op in ("contains","starts_with","ends_with"):
            self.assertIs(run(binary(op,literal("Straße"),literal("STRASSE"))),False)

    def test_no_boolean_number_coercion(self):
        with self.assertRaises(SrxError):run(binary("in",literal(True),literal([1])))
        with self.assertRaises(SrxError):run(binary("contains",literal([1]),literal(True)))

    def test_nested_boolean_difference_is_unequal(self):
        self.assertIs(run(binary("in",literal([True]),literal([[1]]))),False)

    def test_missing_search_is_no_match(self):
        self.assertIs(run(binary("in",field("/absent"),literal([1]))),False)
        self.assertIs(run(binary("contains",literal([1]),field("/absent"))),False)

    def test_missing_container_is_an_error(self):
        with self.assertRaises(SrxError):run(binary("in",literal(1),field("/absent")))
        with self.assertRaises(SrxError):run(unary("count",field("/absent")))

    def test_composed_field_rule(self):
        node=binary("and",binary("starts_with",field("/name"),literal("SR-")),
                    binary("gte",unary("count",field("/items")),literal(2)))
        self.assertIs(run(node,{"name":"SR-REQ","items":[1,2]}),True)

    def test_arrays_are_not_mutated(self):
        value={"items":[[1,2],[3]]};before=copy.deepcopy(value)
        self.assertIs(run(binary("contains",field("/items"),literal([1,2])),value),True)
        self.assertEqual(value,before)

    def test_binary_arity_remains_strict(self):
        for op in ("in","contains","starts_with","ends_with"):
            for args in ([],[literal(1)],[literal(1)]*3):
                with self.assertRaises(SrxError):run({"op":op,"args":args})

    def test_unary_operator_rejects_extra_fields(self):
        for op in ("length","count"):
            with self.assertRaises(SrxError):run({"op":op,"arg":literal([]),"args":[]})

    def test_utf8_program_parsing_remains_available(self):
        import json
        from specroad.srx import parse_program, EvaluationContext, evaluate
        from support.srx import roots, expression_document
        document=expression_document(binary("contains",literal("日本語"),literal("本")))
        program=parse_program(json.dumps(document,ensure_ascii=False).encode(),rule_id="unicode")
        self.assertIs(evaluate(program,EvaluationContext(roots(),rule_id="unicode")),True)
