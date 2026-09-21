"""Boolean and comparison behavior, not human-readable output."""
import copy
import unittest
from specroad.srx import SrxError, MISSING, compare
from support.srx import literal, field, binary, run


class SrxLogicTests(unittest.TestCase):
    def test_not_true(self):
        self.assertIs(run({"op":"not","arg":literal(True)}),False)

    def test_not_false(self):
        self.assertIs(run({"op":"not","arg":literal(False)}),True)

    def test_and_empty_identity(self):
        self.assertIs(run({"op":"and","args":[]}),True)

    def test_or_empty_identity(self):
        self.assertIs(run({"op":"or","args":[]}),False)

    def test_and_truth_table(self):
        for a in (False,True):
            for b in (False,True):
                self.assertIs(run(binary("and",literal(a),literal(b))), a and b)

    def test_or_truth_table(self):
        for a in (False,True):
            for b in (False,True):
                self.assertIs(run(binary("or",literal(a),literal(b))), a or b)

    def test_not_does_not_convert_numbers(self):
        with self.assertRaises(SrxError):run({"op":"not","arg":literal(0)})

    def test_and_does_not_convert_strings(self):
        with self.assertRaises(SrxError):run({"op":"and","args":[literal("false")]})

    def test_or_does_not_convert_null(self):
        with self.assertRaises(SrxError):run({"op":"or","args":[literal(None)]})

    def test_missing_is_not_boolean(self):
        with self.assertRaises(SrxError):run({"op":"not","arg":field("/absent")})

    def test_and_false_skips_bad_value(self):
        self.assertIs(run(binary("and",literal(False),literal(42))),False)

    def test_or_true_skips_bad_value(self):
        self.assertIs(run(binary("or",literal(True),literal(42))),True)

    def test_and_true_evaluates_bad_value(self):
        with self.assertRaises(SrxError):run(binary("and",literal(True),literal(42)))

    def test_or_false_evaluates_bad_value(self):
        with self.assertRaises(SrxError):run(binary("or",literal(False),literal(42)))

    def test_nested_logic(self):
        node=binary("and",literal(True),{"op":"not","arg":binary("or",literal(False),literal(False))})
        self.assertIs(run(node),True)

    def test_eq_null(self):
        self.assertIs(run(binary("eq",literal(None),literal(None))),True)

    def test_eq_numbers(self):
        self.assertIs(run(binary("eq",literal(1),literal(1.0))),True)
        self.assertIs(run(binary("eq",literal(1),literal(2))),False)

    def test_eq_boolean(self):
        self.assertIs(run(binary("eq",literal(True),literal(True))),True)
        self.assertIs(run(binary("eq",literal(True),literal(False))),False)

    def test_eq_string_has_no_normalization(self):
        self.assertIs(run(binary("eq",literal("é"),literal("e\u0301"))),False)

    def test_ne_same_kind(self):
        self.assertIs(run(binary("ne",literal(1),literal(2))),True)
        self.assertIs(run(binary("ne",literal("a"),literal("a"))),False)

    def test_incompatible_scalar_comparison_is_error(self):
        for a,b in ((True,1),(1,"1"),(None,False),([],{})):
            with self.assertRaises(SrxError):run(binary("eq",literal(a),literal(b)))

    def test_eq_missing_is_false(self):
        for a,b in ((MISSING,MISSING),(MISSING,None),(None,MISSING)):
            self.assertIs(compare("eq",a,b,rule_id="r"),False)

    def test_ne_missing_is_true(self):
        for a,b in ((MISSING,MISSING),(MISSING,None),(None,MISSING)):
            self.assertIs(compare("ne",a,b,rule_id="r"),True)

    def test_ordered_missing_is_false(self):
        for op in ("lt","lte","gt","gte"):
            self.assertIs(run(binary(op,field("/absent"),literal(1))),False)
            self.assertIs(run(binary(op,literal(1),field("/absent"))),False)

    def test_deep_objects_ignore_key_order(self):
        self.assertIs(run(binary("eq",literal({"b":[1,None],"a":False}),literal({"a":False,"b":[1,None]}))),True)

    def test_arrays_preserve_order(self):
        self.assertIs(run(binary("eq",literal([1,2]),literal([2,1]))),False)

    def test_nested_boolean_is_not_number(self):
        self.assertIs(run(binary("eq",literal([True]),literal([1]))),False)
        self.assertIs(run(binary("eq",literal({"a":False}),literal({"a":0}))),False)

    def test_nested_missing_key_differs_from_null(self):
        self.assertIs(run(binary("eq",literal({}),literal({"a":None}))),False)

    def test_ordered_numeric_truth_table(self):
        for a,b in ((-2,1),(1,1),(3,2),(0.5,1),(-0.0,0)):
            for op,expected in (("lt",a<b),("lte",a<=b),("gt",a>b),("gte",a>=b)):
                self.assertIs(run(binary(op,literal(a),literal(b))),expected)

    def test_string_order_is_codepoint_order(self):
        self.assertIs(run(binary("lt",literal("Z"),literal("a"))),True)
        self.assertIs(run(binary("gt",literal("𐀀"),literal("\ue000"))),True)

    def test_ordering_rejects_array_and_object(self):
        for value in ([],{},None,False):
            with self.assertRaises(SrxError):run(binary("lt",literal(value),literal(value)))

    def test_comparison_arity(self):
        for args in ([],[literal(1)],[literal(1)]*3):
            with self.assertRaises(SrxError):run({"op":"eq","args":args})

    def test_arguments_must_be_array(self):
        with self.assertRaises(SrxError):run({"op":"and","args":{}})

    def test_syntax_errors_not_hidden_by_short_circuit(self):
        with self.assertRaises(SrxError):run(binary("and",literal(False),{"op":"execute"}))

    def test_field_based_rule(self):
        node=binary("and",{"op":"exists","arg":field("/revision")},binary("gte",field("/revision"),literal(1)))
        self.assertIs(run(node,{"revision":3}),True)
        self.assertIs(run(node,{}),False)

    def test_comparison_does_not_modify_inputs(self):
        left={"a":[1]};right={"a":[1]};before=copy.deepcopy([left,right])
        self.assertIs(compare("eq",left,right,rule_id="r"),True)
        self.assertEqual([left,right],before)

    def test_numeric_comparison_does_not_round_integer(self):
        self.assertIs(compare("gt",9007199254740993,9007199254740992.0,rule_id="r"),True)

    def test_unknown_comparison_name_is_rejected(self):
        with self.assertRaises(SrxError):compare("execute",1,1,rule_id="r")
