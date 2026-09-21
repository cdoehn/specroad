"""Evaluation ordering, exhaustive type boundaries and failure isolation."""
import copy
import itertools
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from specroad.srx import (MISSING,SrxError,SrxProgram,EvaluationContext,evaluate,
                         compare,parse_program)
from specroad.srx import fields
from support.srx import literal,field,binary,roots,run,expression_document
from support.portable import build_distribution,files_under
from support.processes import run_python


def traced(node, data):
    calls=[]; original=fields.resolve_tokens
    def observe(root,tokens,**kwargs):
        calls.append(tokens)
        return original(root,tokens,**kwargs)
    with patch.object(fields,"resolve_tokens",side_effect=observe):
        result=run(node,data)
    return result,calls


class SrxLogicRightTests(unittest.TestCase):
    def test_and_stops_before_bad_field(self):
        node=binary("and",literal(False),field("/a/01"))
        result,calls=traced(node,{"a":[]})
        self.assertIs(result,False);self.assertEqual(calls,[])

    def test_or_stops_before_bad_field(self):
        result,calls=traced(binary("or",literal(True),field("/a/01")),{"a":[]})
        self.assertIs(result,True);self.assertEqual(calls,[])

    def test_and_evaluates_fields_left_to_right(self):
        node={"op":"and","args":[field("/a"),field("/b"),field("/c")]}
        result,calls=traced(node,{"a":True,"b":False,"c":True})
        self.assertIs(result,False);self.assertEqual(calls,[("a",),("b",)])

    def test_or_evaluates_fields_left_to_right(self):
        node={"op":"or","args":[field("/a"),field("/b"),field("/c")]}
        result,calls=traced(node,{"a":False,"b":True,"c":False})
        self.assertIs(result,True);self.assertEqual(calls,[("a",),("b",)])

    def test_binary_comparisons_evaluate_both_left_to_right(self):
        for op in ("eq","ne","lt","lte","gt","gte"):
            result,calls=traced(binary(op,field("/a"),field("/b")),{"a":1,"b":2})
            self.assertEqual(calls,[("a",),("b",)])
            self.assertIs(type(result),bool)

    def test_missing_left_does_not_skip_valid_right(self):
        result,calls=traced(binary("eq",field("/absent"),field("/b")),{"b":1})
        self.assertIs(result,False);self.assertEqual(calls,[("absent",),("b",)])

    def test_missing_left_does_not_hide_right_evaluation_error(self):
        for op in ("eq","ne","lt","lte","gt","gte"):
            with self.assertRaises(SrxError) as err:
                run(binary(op,field("/absent"),field("/a/01")),{"a":[]})
            self.assertEqual(err.exception.pointer,"/expression/args/1/pointer")

    def test_first_runtime_error_stops_remaining_operands(self):
        calls=[];original=fields.resolve_tokens
        def observe(root,tokens,**kw):calls.append(tokens);return original(root,tokens,**kw)
        with patch.object(fields,"resolve_tokens",side_effect=observe), self.assertRaises(SrxError):
            run(binary("eq",field("/a/01"),field("/b/01")),{"a":[],"b":[]})
        self.assertEqual(calls,[("a","01")])

    def test_exists_does_not_swallow_child_error(self):
        with self.assertRaises(SrxError):run({"op":"exists","arg":binary("lt",literal(False),literal(False))})

    def test_not_does_not_swallow_child_error(self):
        with self.assertRaises(SrxError):run({"op":"not","arg":binary("lt",literal(False),literal(False))})

    def test_nested_short_circuit_keeps_outer_value(self):
        node=binary("and",binary("or",literal(True),field("/bad/01")),literal(True))
        self.assertIs(run(node,{"bad":[]}),True)

    def test_skipped_branch_ast_is_still_validated(self):
        with self.assertRaises(SrxError) as err:
            run(binary("or",literal(True),{"op":"not","arg":literal(False),"exec":"bad"}))
        self.assertEqual(err.exception.pointer,"/expression/args/1")

    def test_skipped_branch_pointer_syntax_still_validated(self):
        with self.assertRaises(SrxError):run(binary("or",literal(True),field("/bad~2")))

    def test_skipped_branch_nonfinite_literal_still_rejected(self):
        with self.assertRaises(SrxError):run(binary("or",literal(True),literal(float("nan"))))

    def test_missing_matrix_for_all_comparisons(self):
        for op in ("eq","ne","lt","lte","gt","gte"):
            for value in (MISSING,None,False,0,"",[],{}):
                for a,b in ((MISSING,value),(value,MISSING)):
                    self.assertIs(compare(op,a,b,rule_id="r"),op=="ne")

    def test_top_level_type_pairs_never_coerce(self):
        values=[None,True,1,"1",[1],{"x":1}]
        for op in ("eq","ne","lt","lte","gt","gte"):
            for i,a in enumerate(values):
                for j,b in enumerate(values):
                    if i!=j:
                        with self.subTest(op=op,i=i,j=j),self.assertRaises(SrxError):compare(op,a,b,rule_id="r")

    def test_boolean_consumers_reject_every_other_kind(self):
        for node in (lambda a:{"op":"not","arg":a},lambda a:{"op":"and","args":[a]},lambda a:{"op":"or","args":[a]}):
            for value in (None,0,1,0.0,"",[],{}):
                with self.assertRaises(SrxError):run(node(literal(value)))
            with self.assertRaises(SrxError):run(node(field("/absent")))

    def test_equality_all_json_leaf_values(self):
        for value in (None,True,False,0,-1,0.25,"text",[],{}):
            self.assertIs(compare("eq",value,value,rule_id="r"),True)
            self.assertIs(compare("ne",value,value,rule_id="r"),False)

    def test_all_three_input_boolean_combinations(self):
        for values in itertools.product((False,True),repeat=3):
            args=[literal(x) for x in values]
            self.assertIs(run({"op":"and","args":args}),all(values))
            self.assertIs(run({"op":"or","args":args}),any(values))

    def test_object_key_permutations_do_not_affect_equality(self):
        data={"z":[False],"a":None,"日本語":1}
        for keys in itertools.permutations(data):
            self.assertIs(compare("eq",data,{k:data[k] for k in keys},rule_id="r"),True)

    def test_nested_kind_changes_are_unequal(self):
        for a,b in ((False,0),(True,1),(1,"1"),([],{}),(None,False)):
            self.assertIs(compare("eq",{"x":[a]},{"x":[b]},rule_id="r"),False)
            self.assertIs(compare("ne",{"x":[a]},{"x":[b]},rule_id="r"),True)

    def test_numeric_nested_kinds_are_one_number_kind(self):
        self.assertIs(compare("eq",{"x":[1,-0.0]},{"x":[1.0,0]},rule_id="r"),True)

    def test_missing_in_nested_json_is_rejected(self):
        for op in ("eq","ne","lt"):
            with self.assertRaises(SrxError):compare(op,[MISSING],[None],rule_id="r")

    def test_empty_object_differs_from_null_member(self):
        self.assertIs(compare("ne",{"a":{}},{"a":{"x":None}},rule_id="r"),True)

    def test_array_length_difference(self):
        self.assertIs(compare("eq",[1],[1,2],rule_id="r"),False)

    def test_deep_equality_is_iterative(self):
        a=1;b=1.0
        for _ in range(1600):a={"x":[a]};b={"x":[b]}
        self.assertIs(compare("eq",a,b,rule_id="r"),True)

    def test_deep_inequality_is_iterative(self):
        a=False;b=0
        for _ in range(1600):a=[a];b=[b]
        self.assertIs(compare("eq",a,b,rule_id="r"),False)
        self.assertIs(compare("ne",a,b,rule_id="r"),True)

    def test_deep_logic_without_recursion(self):
        node=literal(True)
        for _ in range(1600):node={"op":"not","arg":node}
        self.assertIs(run(node),True)

    def test_wide_logic_has_no_display_limit(self):
        node={"op":"and","args":[literal(True)]*600+[literal(False)]}
        self.assertIs(run(node),False)

    def test_large_integer_not_rounded_to_float(self):
        value=2**2000+1
        self.assertIs(compare("gt",value,2**2000,rule_id="r"),True)
        self.assertIs(compare("eq",9007199254740993,9007199254740992.0,rule_id="r"),False)

    def test_negative_zero_and_finite_float_boundaries(self):
        self.assertIs(compare("eq",-0.0,0,rule_id="r"),True)
        self.assertIs(compare("gt",5e-324,0,rule_id="r"),True)
        self.assertIs(compare("lt",-1.7976931348623157e308,1.7976931348623157e308,rule_id="r"),True)

    def test_surrogate_input_rejected_before_string_ordering(self):
        with self.assertRaises(SrxError):compare("lt","\ud800","a",rule_id="r")

    def test_no_unicode_normalization_in_object_keys(self):
        self.assertIs(compare("eq",{"é":1},{"e\u0301":1},rule_id="r"),False)

    def test_ordering_independent_of_locale_environment(self):
        results=[]
        for loc in ("C","de_DE.UTF-8","tr_TR.UTF-8"):
            with patch.dict(os.environ,{"LANG":loc,"LC_ALL":loc}):
                results.append(run(binary("lt",literal("Z"),literal("a"))))
        self.assertEqual(results,[True]*3)

    def test_raw_arguments_are_not_reordered(self):
        node=binary("lt",literal(1),literal(2));raw=json.dumps(expression_document(node)).encode()
        p=parse_program(raw,rule_id="r")
        self.assertIs(evaluate(p,EvaluationContext(roots(),rule_id="r")),True)
        self.assertEqual(p.source_bytes,raw)

    def test_raw_duplicate_argument_key_rejected(self):
        raw=b'{"language":"srx","version":"1.0","expression":{"op":"eq","args":[],"args":[]}}'
        with self.assertRaises(SrxError) as err:parse_program(raw,rule_id="r")
        self.assertEqual(err.exception.reason,"duplicate_key")

    def test_arguments_cannot_be_implicit_literal_values(self):
        with self.assertRaises(SrxError):run({"op":"eq","args":[1,1]})

    def test_extra_comparison_fields_rejected(self):
        node=binary("eq",literal(1),literal(1));node["coerce"]=True
        with self.assertRaises(SrxError):run(node)

    def test_missing_required_argument_rejected(self):
        for node in ({"op":"not"},{"op":"and"},{"op":"eq"}):
            with self.assertRaises(SrxError):run(node)

    def test_code_shaped_literals_remain_data(self):
        value={"op":"execute","value":"__import__('os').system('bad')"}
        with patch('os.system',side_effect=AssertionError('shell')):
            self.assertIs(run(binary("eq",literal(value),literal(value))),True)

    def test_foreign_comparison_hook_not_executed(self):
        calls=[]
        class Foreign:
            def __eq__(self,other):calls.append("eq");return True
            def __lt__(self,other):calls.append("lt");return True
            def __str__(self):calls.append("str");return "secret"
        with self.assertRaises(SrxError):compare("eq",Foreign(),1,rule_id="r")
        self.assertEqual(calls,[])

    def test_bool_subclass_shortcuts_not_used_for_integers(self):
        calls=[]
        class Number(int):
            def __bool__(self):calls.append("bool");return True
            def __eq__(self,other):calls.append("eq");return True
        with self.assertRaises(SrxError):compare("eq",Number(1),1,rule_id="r")
        self.assertEqual(calls,[])

    def test_original_inputs_and_context_do_not_change(self):
        data=roots({"a":1});ctx=EvaluationContext(data,rule_id="r")
        node=binary("eq",field("/a"),literal(1));program=SrxProgram(expression_document(node),rule_id="r")
        before=copy.deepcopy(data)
        self.assertIs(evaluate(program,ctx),True)
        self.assertEqual(data,before);self.assertEqual(ctx.data,before)

    def test_diagnostics_report_actual_operand_not_its_value(self):
        with self.assertRaises(SrxError) as err:run(binary("eq",literal(1),literal("private")))
        d=err.exception.diagnostic();self.assertEqual(d["expression_pointer"],"/expression/args/1")
        self.assertEqual(d["expected_type"],"number");self.assertEqual(d["actual_type"],"string")
        self.assertNotIn("private",json.dumps(d))

    def test_first_structural_error_is_leftmost(self):
        with self.assertRaises(SrxError) as err:run({"op":"and","args":[{"op":"unknown-a"},{"op":"unknown-b"}]})
        self.assertEqual(err.exception.pointer,"/expression/args/0/op")

    def test_portable_logic_and_missing_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/"build";build_distribution(target)
            moved=root/"moved";target.rename(moved);before=files_under(moved)
            node=binary("or",literal(True),binary("lt",literal(None),literal(None)))
            code=("from specroad.srx import *\n"
                  f"p=SrxProgram({expression_document(node)!r},rule_id='r')\n"
                  f"c=EvaluationContext({roots()!r},rule_id='r')\n"
                  "assert evaluate(p,c) is True\n"
                  "assert compare('eq',[True],[1],rule_id='r') is False\n"
                  "assert compare('ne',MISSING,None,rule_id='r') is True\n")
            for location in (moved/"module",moved/"specroad.pyz"):
                result=run_python(['-I','-S','-B','-c','import sys;sys.path.insert(0,'+repr(str(location))+');\n'+code],root)
                self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(files_under(moved),before)
