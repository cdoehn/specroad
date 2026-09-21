"""Adversarial field/typing regression cases; no human-output assertions."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from specroad.srx import (MISSING, SrxError, SrxProgram, EvaluationContext, evaluate,
                         value_type, require_type, read_field, parse_program)
from support.srx import field, literal, roots, run, expression_document
from support.portable import build_distribution, files_under
from support.processes import run_python


class SrxFieldRightTests(unittest.TestCase):
    def test_rfc6901_string_examples(self):
        data = {"foo":["bar","baz"],"":0,"a/b":1,"c%d":2,"e^f":3,
                "g|h":4,"i\\j":5,'k"l':6," ":7,"m~n":8}
        cases = [("",data),("/foo",["bar","baz"]),("/foo/0","bar"),("/",0),
                 ("/a~1b",1),("/c%d",2),("/e^f",3),("/g|h",4),("/i\\j",5),
                 ('/k"l',6),("/ ",7),("/m~0n",8)]
        for pointer,expected in cases:
            self.assertEqual(run(field(pointer),data),expected)

    def test_malformed_escapes_rejected_before_lookup(self):
        for ptr in ("/absent/~", "/absent/~3", "/~00~2", "/~~0"):
            with self.assertRaises(SrxError) as error: run(field(ptr))
            self.assertEqual(error.exception.reason,"invalid_pointer_escape")

    def test_uri_fragment_not_implicitly_decoded(self):
        for ptr in ("#", "#/a", "file:///tmp/a", "0/a", "1#"):
            with self.assertRaises(SrxError): run(field(ptr))

    def test_percent_keys_and_slash_keys_stay_different(self):
        self.assertEqual(run(field("/%7E1"),{"%7E1":1,"/":2}),1)

    def test_control_character_key_is_data(self):
        self.assertEqual(run(field("/a\x00b"),{"a\x00b":4}),4)

    def test_object_dash_key_is_real(self):
        self.assertEqual(run(field("/-"),{"-":False}),False)

    def test_empty_nested_object_keys(self):
        self.assertEqual(run(field("//"),{"":{"":7}}),7)

    def test_reached_array_rejects_invalid_indices(self):
        for token in ("", "01", "00", "+1", "-1", "1.0", "1e0", " 1", "١", "１", "x"):
            with self.subTest(token=token), self.assertRaises(SrxError) as err:
                run(field("/a/"+token),{"a":[1,2]})
            self.assertEqual(err.exception.reason,"invalid_array_index")

    def test_invalid_index_is_not_checked_against_absent_container(self):
        self.assertIs(run(field("/absent/01")),MISSING)

    def test_very_large_array_index_returns_missing(self):
        self.assertIs(run(field("/a/"+"9"*10000),{"a":[1]}),MISSING)

    def test_path_past_string_does_not_index_characters(self):
        self.assertIs(run(field("/a/0"),{"a":"hello"}),MISSING)

    def test_path_past_array_null(self):
        self.assertIs(run(field("/a/0/child"),{"a":[None]}),MISSING)

    def test_item_is_not_a_global_field_root(self):
        with self.assertRaises(SrxError): run(field("", "item"))

    def test_dynamic_context_is_rejected(self):
        with self.assertRaises(SrxError): run(field("",literal("artifact")))

    def test_boolean_pointer_is_not_coerced(self):
        with self.assertRaises(SrxError) as err: run(field(False))
        self.assertEqual(err.exception.actual,"boolean")

    def test_number_pointer_is_not_coerced(self):
        with self.assertRaises(SrxError) as err: run(field(0))
        self.assertEqual(err.exception.actual,"number")

    def test_null_pointer_is_not_empty_root(self):
        with self.assertRaises(SrxError): run(field(None))

    def test_field_unknown_members_are_rejected(self):
        node=field("/a");node["default"]=0
        with self.assertRaises(SrxError): run(node)

    def test_nested_unknown_operator_is_rejected(self):
        with self.assertRaises(SrxError) as err:
            run({"op":"exists","arg":{"op":"eval","value":"secret"}})
        self.assertEqual(err.exception.pointer,"/expression/arg/op")

    def test_nested_index_failure_has_precise_expression_pointer(self):
        with self.assertRaises(SrxError) as err:
            run({"op":"exists","arg":field("/a/01")},{"a":[]})
        d=err.exception.diagnostic()
        self.assertEqual(d["code"],"SRV110")
        self.assertEqual(d["expression_pointer"],"/expression/arg/pointer")
        self.assertEqual(d["rule_id"],"rule-test")

    def test_duplicate_pointer_key_in_bytes_is_rejected(self):
        raw=b'{"language":"srx","version":"1.0","expression":{"op":"field","context":"artifact","pointer":"/a","pointer":"/b"}}'
        with self.assertRaises(SrxError) as err: parse_program(raw,rule_id="r")
        self.assertEqual(err.exception.reason,"duplicate_key")

    def test_raw_pointer_unicode_preserved(self):
        node=field("/日本語");raw=json.dumps(expression_document(node),ensure_ascii=False).encode()
        program=parse_program(raw,rule_id="r")
        self.assertEqual(program.source_bytes,raw)
        self.assertEqual(evaluate(program,EvaluationContext(roots({"日本語":3}),rule_id="r")),3)

    def test_deep_field_is_iterative(self):
        value=9
        for _ in range(1400):value={"a":value}
        self.assertEqual(run(field("/a"*1400),value),9)

    def test_deep_exists_is_iterative(self):
        node=field("/none")
        for _ in range(1400):node={"op":"exists","arg":node}
        self.assertIs(run(node),True)

    def test_read_field_uses_immutable_snapshot(self):
        ctx=EvaluationContext(roots({"x":[1]}),rule_id="r")
        read_field(ctx,"artifact","/x",rule_id="r").append(2)
        self.assertEqual(read_field(ctx,"artifact","/x",rule_id="r"),[1])

    def test_read_field_rejects_fake_context_without_hooks(self):
        calls=[]
        class Fake:
            @property
            def data(self):calls.append(1);return roots()
        with self.assertRaises(SrxError):read_field(Fake(),"artifact","",rule_id="r")
        self.assertEqual(calls,[])

    def test_read_field_rejects_context_subclass(self):
        calls=[]
        class Sub(EvaluationContext):
            @property
            def data(self):calls.append(1);return roots()
        with self.assertRaises(SrxError):read_field(Sub(roots(),rule_id="r"),"artifact","",rule_id="r")
        self.assertEqual(calls,[])

    def test_boolean_is_not_numeric_operand(self):
        with self.assertRaises(SrxError) as err:require_type(True,("number",),rule_id="r")
        self.assertEqual(err.exception.actual,"boolean")

    def test_number_is_not_boolean_operand(self):
        with self.assertRaises(SrxError):require_type(1,("boolean",),rule_id="r")

    def test_string_number_is_not_numeric_operand(self):
        with self.assertRaises(SrxError):require_type("1",("number",),rule_id="r")

    def test_missing_is_not_null_operand(self):
        with self.assertRaises(SrxError) as err:require_type(MISSING,("null",),rule_id="r")
        self.assertEqual(err.exception.actual,"missing")

    def test_null_is_not_missing_operand(self):
        with self.assertRaises(SrxError):require_type(None,("missing",),rule_id="r")

    def test_nested_missing_not_accepted_as_json(self):
        with self.assertRaises(SrxError):value_type([MISSING])

    def test_type_signature_itself_is_validated(self):
        for kinds in ((), ["number"], ("float",), (None,)):
            with self.assertRaises(SrxError):require_type(1,kinds,rule_id="r")

    def test_type_boundary_does_not_convert_foreign_object(self):
        calls=[]
        class Foreign:
            def __bool__(self):calls.append(1);return True
            def __str__(self):calls.append(2);return "secret"
        with self.assertRaises(SrxError):require_type(Foreign(),("boolean",),rule_id="r")
        self.assertEqual(calls,[])

    def test_missing_keeps_identity_under_copy(self):
        self.assertIs(copy.copy(MISSING),MISSING)
        self.assertIs(copy.deepcopy(MISSING),MISSING)

    def test_field_never_opens_paths(self):
        ctx=EvaluationContext(roots({"etc":{"passwd":"passive"}}),rule_id="r")
        with patch("builtins.open",side_effect=AssertionError("I/O")),patch("os.getenv",side_effect=AssertionError("env")):
            self.assertEqual(read_field(ctx,"artifact","/etc/passwd",rule_id="r"),"passive")

    def test_relative_tokens_do_not_navigate(self):
        for ptr in ("/.", "/..", "/a/."):
            with self.assertRaises(SrxError):run(field(ptr),{".":1,"..":2})
        self.assertEqual(run(field("/a.b"),{"a.b":3}),3)

    def test_failure_does_not_modify_inputs(self):
        data={"a":[1]};before=copy.deepcopy(data)
        with self.assertRaises(SrxError):run(field("/a/01"),data)
        self.assertEqual(data,before)

    def test_error_is_repeatable_and_does_not_include_value(self):
        ds=[]
        for _ in range(2):
            try:require_type("private-value",("number",),rule_id="r",pointer="/expression/arg")
            except SrxError as error:ds.append(error.diagnostic())
        self.assertEqual(ds[0],ds[1]);self.assertNotIn("private-value",json.dumps(ds))

    def test_portable_field_and_exists_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/"build";build_distribution(target)
            moved=root/"moved";target.rename(moved);before=files_under(moved)
            code=("from specroad.srx import *\n"
                  "c=EvaluationContext({'artifact':{'a':None},'project':{},'configuration':None,'relations':[]},rule_id='r')\n"
                  "assert read_field(c,'artifact','/a',rule_id='r') is None\n"
                  "assert read_field(c,'artifact','/b',rule_id='r') is MISSING\n")
            for location in (moved/"module",moved/"specroad.pyz"):
                result=run_python(['-I','-S','-B','-c','import sys;sys.path.insert(0,'+repr(str(location))+');\n'+code],root)
                self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(files_under(moved),before)
