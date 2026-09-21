"""Unicode, type matrices, expression ordering and owned-input regressions."""
import copy
import json
import locale
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from specroad.srx import SrxError, SrxProgram, EvaluationContext, evaluate, parse_program
from specroad.srx import fields
from support.srx import binary, field, literal, roots, run, expression_document
from support.portable import build_distribution, files_under
from support.processes import run_python


def unary(op, value): return {"op":op,"arg":value}


class SrxCollectionsRightTests(unittest.TestCase):
    def test_string_signatures_reject_every_other_type(self):
        for op in ("starts_with","ends_with"):
            for value in (None,False,0,[],{}):
                for a,b in ((value,"x"),("x",value)):
                    with self.subTest(op=op,t=type(value).__name__), self.assertRaises(SrxError):
                        run(binary(op,literal(a),literal(b)))

    def test_length_and_count_have_distinct_type_signatures(self):
        for op,values in (("length",(None,False,0,1.0)),("count",(None,False,0,"",{}))):
            for value in values:
                with self.subTest(op=op,t=type(value).__name__), self.assertRaises(SrxError):
                    run(unary(op,literal(value)))

    def test_membership_requires_array_not_string_or_keys(self):
        for value in (None,False,1,"abc",{"a":1}):
            with self.assertRaises(SrxError):run(binary("in",literal("a"),literal(value)))

    def test_contains_does_not_search_object_keys(self):
        with self.assertRaises(SrxError):run(binary("contains",literal({"a":1}),literal("a")))

    def test_string_contains_has_no_numeric_cast(self):
        for value in (None,False,1,[],{}):
            with self.assertRaises(SrxError):run(binary("contains",literal("123"),literal(value)))

    def test_mixed_element_types_follow_strict_eq_error(self):
        for node in (binary("in",literal(2),literal([1,"2",2])),binary("contains",literal([1,"2",2]),literal(2))):
            with self.assertRaises(SrxError):run(node)

    def test_membership_stops_when_equal_element_is_found(self):
        self.assertIs(run(binary("in",literal(1),literal([1,"later"]))),True)
        self.assertIs(run(binary("contains",literal([1,"later"]),literal(1))),True)

    def test_all_same_type_json_values_follow_deep_equality(self):
        values=[None,True,False,0,1,1.0,"", "text", [], [None], {}, {"a":[1,False]}]
        for value in values:
            with self.subTest(t=type(value).__name__):
                self.assertIs(run(binary("in",literal(value),literal([copy.deepcopy(value)]))),True)
                self.assertIs(run(binary("contains",literal([value]),literal(copy.deepcopy(value)))),True)

    def test_missing_search_matches_no_json_value(self):
        values=[None,False,0,"",[],{}]
        self.assertIs(run(binary("in",field("/absent"),literal(values))),False)
        self.assertIs(run(binary("contains",literal(values),field("/absent"))),False)

    def test_missing_string_operand_is_not_empty_string(self):
        for op in ("contains","starts_with","ends_with"):
            with self.assertRaises(SrxError):run(binary(op,literal(""),field("/absent")))

    def test_codepoint_lengths_not_bytes_or_graphemes(self):
        for value,count in (("\0",1),("😀",1),("e\u0301",2),("👩\u200d💻",3),("🇩🇪",2),("日本語",3)):
            self.assertEqual(run(unary("length",literal(value))),count)

    def test_combining_mark_can_be_its_own_substring(self):
        self.assertIs(run(binary("contains",literal("e\u0301"),literal("\u0301"))),True)
        self.assertIs(run(binary("ends_with",literal("e\u0301"),literal("\u0301"))),True)

    def test_nul_is_an_ordinary_codepoint(self):
        self.assertIs(run(binary("contains",literal("a\0b"),literal("\0"))),True)
        self.assertIs(run(binary("starts_with",literal("\0x"),literal("\0"))),True)

    def test_overlapping_substrings_do_not_change_membership(self):
        self.assertIs(run(binary("contains",literal("aaaa"),literal("aaa"))),True)
        self.assertIs(run(binary("contains",literal("aaaa"),literal("aaaaa"))),False)

    def test_prefix_and_suffix_longer_than_subject_are_false(self):
        for op in ("starts_with","ends_with"):
            self.assertIs(run(binary(op,literal("a"),literal("aa"))),False)

    def test_environment_and_locale_do_not_supply_semantics(self):
        with patch.dict(os.environ,{"LANG":"tr_TR.UTF-8","LC_ALL":"invalid","TZ":"Pacific/Honolulu"}), \
             patch.object(locale,"strcoll",side_effect=AssertionError("locale read")), \
             patch.object(locale,"strxfrm",side_effect=AssertionError("locale read")):
            self.assertIs(run(binary("contains",literal("Istanbul"),literal("ı"))),False)
            self.assertEqual(run(unary("length",literal("é"))),1)

    def test_binary_children_are_evaluated_left_to_right(self):
        calls=[];original=fields.resolve_tokens
        def observe(root,tokens,**kw):calls.append(tokens);return original(root,tokens,**kw)
        for op,data in (("in",{"a":1,"b":[1]}),("contains",{"a":[1],"b":1}),
                        ("starts_with",{"a":"ab","b":"a"}),("ends_with",{"a":"ab","b":"b"})):
            calls.clear()
            with patch.object(fields,"resolve_tokens",side_effect=observe):
                self.assertIs(run(binary(op,field("/a"),field("/b")),data),True)
            self.assertEqual(calls,[("a",),("b",)])

    def test_first_child_error_stops_remaining_field_read(self):
        calls=[];original=fields.resolve_tokens
        def observe(root,tokens,**kw):calls.append(tokens);return original(root,tokens,**kw)
        with patch.object(fields,"resolve_tokens",side_effect=observe),self.assertRaises(SrxError):
            run(binary("in",field("/a/01"),field("/b")),{"a":[],"b":[]})
        self.assertEqual(calls,[("a","01")])

    def test_missing_needle_does_not_skip_haystack_expression_errors(self):
        with self.assertRaises(SrxError):run(binary("in",field("/absent"),field("/a/01")),{"a":[]})

    def test_outer_short_circuit_skips_runtime_sequence_error(self):
        bad=unary("count",literal("not-an-array"))
        self.assertIs(run(binary("or",literal(True),bad)),True)
        self.assertIs(run(binary("and",literal(False),bad)),False)

    def test_skipped_branch_still_requires_well_formed_sequence_ast(self):
        for bad in ({"op":"length","arg":literal([]),"extra":0},{"op":"in","args":[]}):
            with self.assertRaises(SrxError):run(binary("or",literal(True),bad))

    def test_literal_operator_shaped_objects_remain_data(self):
        data={"op":"count","arg":{"op":"unknown"}}
        self.assertIs(run(binary("contains",literal([data]),literal(data))),True)
        self.assertEqual(run(unary("length",literal(data))),2)

    def test_code_shaped_strings_do_not_execute(self):
        text="__import__('os').system('not-a-command')"
        with patch("os.system",side_effect=AssertionError("execution")):
            self.assertIs(run(binary("contains",literal(text),literal("__import__"))),True)

    def test_foreign_container_and_string_hooks_never_run(self):
        calls=[]
        class Text(str):
            def __len__(self):calls.append("len");return 0
            def __contains__(self,x):calls.append("contains");return True
        class Array(list):
            def __iter__(self):calls.append("iter");return iter([])
        for value in (Text("abc"),Array([1])):
            with self.assertRaises(SrxError):run(unary("length",literal(value)))
        self.assertEqual(calls,[])

    def test_invalid_unicode_is_rejected_even_when_empty_container(self):
        with self.assertRaises(SrxError):run(binary("in",literal("\ud800"),literal([])))

    def test_nonfinite_nested_values_are_not_hidden_by_count(self):
        for value in (float("inf"),float("-inf"),float("nan")):
            with self.assertRaises(SrxError):run(unary("count",literal([value])))

    def test_result_counts_are_integers_not_booleans(self):
        for op in ("length","count"):
            self.assertIs(type(run(unary(op,literal([1])))),int)

    def test_full_arrays_are_not_truncated_by_display_limits(self):
        data=list(range(1501))
        self.assertIs(run(binary("in",literal(1500),literal(data))),True)
        self.assertEqual(run(unary("count",literal(data))),1501)

    def test_deep_object_membership_avoids_recursive_equality(self):
        value=1
        for _ in range(1200):value={"child":value}
        self.assertIs(run(binary("in",literal(value),literal([value]))),True)

    def test_deep_unary_expression_avoids_recursive_evaluation(self):
        node=literal("abc")
        # eq wraps the previous Boolean value; length is evaluated at the leaf.
        node=unary("length",node)
        node=binary("eq",node,literal(3))
        for _ in range(1200):node=binary("eq",node,literal(True))
        self.assertIs(run(node),True)

    def test_diagnostics_bind_operand_location_without_exposing_value(self):
        with self.assertRaises(SrxError) as caught:run(binary("starts_with",literal("secret"),literal(123)))
        data=caught.exception.diagnostic()
        self.assertEqual(data["expression_pointer"],"/expression/args/1")
        self.assertEqual(data["actual_type"],"number")
        self.assertEqual(data["expected_type"],"string")
        self.assertNotIn("secret",json.dumps(data))

    def test_repeated_evaluation_owns_its_context_values(self):
        data=roots({"items":[1,2]});context=EvaluationContext(data,rule_id="r")
        program=SrxProgram(expression_document(unary("count",field("/items"))),rule_id="r")
        data["artifact"]["items"].append(3)
        self.assertEqual(evaluate(program,context),2)
        self.assertEqual(evaluate(program,context),2)

    def test_portable_distribution_has_same_sequence_behavior(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/"built";build_distribution(target)
            moved=root/"moved";target.rename(moved);before=files_under(moved)
            node=binary("eq",unary("length",literal("😀e\u0301")),literal(3))
            code=("from specroad.srx import *\n"+
                  f"p=SrxProgram({expression_document(node)!r},rule_id='r')\n"+
                  f"c=EvaluationContext({roots()!r},rule_id='r')\n"+
                  "assert evaluate(p,c) is True\n")
            for location in (moved/"module",moved/"specroad.pyz"):
                result=run_python(['-I','-S','-B','-c','import sys;sys.path.insert(0,'+repr(str(location))+');\n'+code],root)
                self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(files_under(moved),before)
