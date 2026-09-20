"""Strict SRX/context input boundaries and process-independent behavior."""

import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from decimal import Decimal
from specroad.srx import SrxProgram, EvaluationContext, SrxError, evaluate, parse_program, parse_context
from test_srx_context import context_data, program_data, run_value
from support.portable import build_distribution, files_under
from support.processes import run_python


class SrxContextRightTests(unittest.TestCase):
    def test_raw_program_preserves_original_bytes(self):
        raw = b'{ "language":"srx", "version":"1.0", "expression":{"op":"literal","value": [1,null]} }\n'
        result = parse_program(raw, rule_id="r")
        self.assertEqual(result.source_bytes, raw)
        self.assertEqual(result.value, [1, None])

    def test_raw_context_has_same_values(self):
        data = context_data()
        result = parse_context(json.dumps(data).encode(), rule_id="r")
        self.assertEqual(result.data, data)

    def test_programmatic_program_has_no_invented_bytes(self):
        self.assertIsNone(SrxProgram(program_data(True), rule_id="r").source_bytes)

    def test_duplicate_envelope_key_rejected(self):
        raw = b'{"language":"srx","version":"1.0","version":"1.0","expression":{"op":"literal","value":1}}'
        with self.assertRaises(SrxError) as caught: parse_program(raw, rule_id="r")
        self.assertEqual(caught.exception.reason, "duplicate_key")
        self.assertEqual(caught.exception.pointer, "/version")

    def test_duplicate_literal_key_rejected(self):
        raw = b'{"language":"srx","version":"1.0","expression":{"op":"literal","value":{"a":1,"a":2}}}'
        with self.assertRaises(SrxError) as caught: parse_program(raw, rule_id="r")
        self.assertEqual(caught.exception.pointer, "/expression/value/a")

    def test_duplicate_context_key_rejected(self):
        raw = b'{"artifact":{},"artifact":{},"configuration":null,"project":{},"relations":[]}'
        with self.assertRaises(SrxError) as caught: parse_context(raw, rule_id="r")
        self.assertEqual(caught.exception.reason, "duplicate_key")
        self.assertEqual(caught.exception.subject, "context")

    def test_invalid_utf8_rejected(self):
        with self.assertRaises(SrxError) as caught: parse_program(b'\xff', rule_id="r")
        self.assertEqual(caught.exception.reason, "invalid_utf8")
        self.assertEqual(caught.exception.position, 0)

    def test_trailing_data_is_not_ignored(self):
        raw = json.dumps(program_data(True)).encode()+b' {}'
        with self.assertRaises(SrxError): parse_program(raw, rule_id="r")

    def test_raw_nonfinite_number_is_rejected(self):
        raw = b'{"language":"srx","version":"1.0","expression":{"op":"literal","value":NaN}}'
        with self.assertRaises(SrxError): parse_program(raw, rule_id="r")

    def test_raw_lone_surrogate_is_rejected(self):
        raw = json.dumps(program_data("\ud800")).encode()
        with self.assertRaises(SrxError): parse_program(raw, rule_id="r")

    def test_text_path_is_not_read(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"condition.json"
            raw = json.dumps(program_data(True)).encode(); path.write_bytes(raw)
            with self.assertRaises(SrxError): parse_program(str(path), rule_id="r")
            self.assertEqual(path.read_bytes(), raw)

    def test_file_object_is_not_read(self):
        calls = []
        class Reader:
            def read(self): calls.append("read"); return b'{}'
        with self.assertRaises(SrxError): parse_program(Reader(), rule_id="r")
        self.assertEqual(calls, [])

    def test_non_object_raw_input_is_rejected(self):
        for raw in (b'null', b'[]', b'true', b'12', b'"code"'):
            with self.subTest(raw=raw.hex()), self.assertRaises(SrxError): parse_program(raw, rule_id="r")

    def test_unknown_language_or_numeric_version_no_fallback(self):
        for field,value in (("language","python"),("language","SRX"),("version",1.0),("version","1.1"),("version",None)):
            data = program_data(True); data[field] = value
            with self.subTest(field=field,value=value), self.assertRaises(SrxError): SrxProgram(data, rule_id="r")

    def test_missing_or_extra_envelope_fields_rejected(self):
        for field in ("language","version","expression"):
            data = program_data(True); del data[field]
            with self.assertRaises(SrxError): SrxProgram(data, rule_id="r")
        data = program_data(True); data["import"] = "os"
        with self.assertRaises(SrxError): SrxProgram(data, rule_id="r")

    def test_rule_id_must_be_explicit_string(self):
        for value in (None,False,1,""," "):
            with self.assertRaises(SrxError): SrxProgram(program_data(True), rule_id=value)

    def test_invalid_configuration_projection_rejected(self):
        for value in ({}, {"configuration_id":"cfg","effective_values":[],},
                      {"configuration_id":"","effective_values":{}},
                      {"configuration_id":"cfg","effective_values":{},"parent":"x"}):
            data = context_data(); data["configuration"] = value
            with self.assertRaises(SrxError): EvaluationContext(data, rule_id="r")

    def test_artifact_and_project_must_be_objects(self):
        for key in ("artifact","project"):
            data=context_data(); data[key]=[]
            with self.assertRaises(SrxError): EvaluationContext(data, rule_id="r")

    def test_relation_callback_is_never_called(self):
        calls=[]
        def resolve(): calls.append(1); return {}
        data=context_data(); data["relations"]=resolve
        with self.assertRaises(SrxError): EvaluationContext(data, rule_id="r")
        self.assertEqual(calls,[])

    def test_relations_array_is_an_owned_view(self):
        data=context_data(); data["relations"]=[{"type":"depends_on","target":"B"}]
        result=EvaluationContext(data,rule_id="r")
        data["relations"][0]["target"]="C"
        self.assertEqual(result.data["relations"][0]["target"],"B")

    def test_forbidden_context_roots_never_resolve(self):
        for name in ("item","environment","filesystem","network","clock","random","profiles","graph"):
            data=context_data();data[name]={}
            with self.subTest(root=name),self.assertRaises(SrxError):EvaluationContext(data,rule_id="r")

    def test_foreign_object_conversion_hooks_are_not_run(self):
        calls=[]
        class Foreign:
            def __repr__(self): calls.append("repr");return "secret"
            def __str__(self): calls.append("str");return "secret"
            def __iter__(self): calls.append("iter");return iter(())
            def __deepcopy__(self,memo): calls.append("copy");return {}
        with self.assertRaises(SrxError):run_value(Foreign())
        self.assertEqual(calls,[])

    def test_mapping_subclass_is_not_iterated(self):
        calls=[]
        class Foreign(dict):
            def __iter__(self):calls.append("iter");raise RuntimeError()
            def items(self):calls.append("items");raise RuntimeError()
        with self.assertRaises(SrxError):run_value(Foreign(a=1))
        self.assertEqual(calls,[])

    def test_string_subclass_is_not_encoded(self):
        calls=[]
        class Foreign(str):
            def encode(self,*a,**k):calls.append("encode");raise RuntimeError()
        with self.assertRaises(SrxError):run_value(Foreign("secret"))
        self.assertEqual(calls,[])

    def test_non_json_types_are_not_coerced(self):
        for value in ((1,2),{1,2},b"text",Decimal("1.2"),Path("a")):
            with self.subTest(kind=type(value).__name__),self.assertRaises(SrxError):run_value(value)

    def test_non_string_object_keys_rejected(self):
        with self.assertRaises(SrxError):run_value({1:"one"})

    def test_nested_context_pointer_escapes(self):
        data=context_data();data["project"]["a/b~"]={"x":object()}
        with self.assertRaises(SrxError) as caught:EvaluationContext(data,rule_id="r")
        self.assertEqual(caught.exception.pointer,"/project/a~1b~0/x")

    def test_shared_acyclic_objects_allowed_and_copied(self):
        item={"x":[1]};result=run_value([item,item])
        result[0]["x"].append(2)
        self.assertEqual(result[1],{"x":[1]})
        self.assertEqual(item,{"x":[1]})

    def test_indirect_context_cycle_rejected(self):
        data=context_data();data["project"]["back"]=data
        with self.assertRaises(SrxError) as caught:EvaluationContext(data,rule_id="r")
        self.assertEqual(caught.exception.reason,"cyclic_json_value")

    def test_deep_literal_without_python_recursion(self):
        value=7
        for _ in range(1400):value=[value]
        result=run_value(value)
        for _ in range(1400):result=result[0]
        self.assertEqual(result,7)

    def test_deep_object_literal_without_python_recursion(self):
        value=True
        for _ in range(1100):value={"a":value}
        result=run_value(value)
        for _ in range(1100):result=result["a"]
        self.assertIs(result,True)

    def test_failed_parse_leaves_inputs_unchanged(self):
        data=program_data([1]);data["expression"]["extra"]="invalid";before=copy.deepcopy(data)
        with self.assertRaises(SrxError):SrxProgram(data,rule_id="r")
        self.assertEqual(data,before)

    def test_false_literal_is_real_value_not_failure(self):
        self.assertIs(run_value(False),False)
        with self.assertRaises(SrxError):parse_program(b'{}',rule_id="r")

    def test_host_locale_and_environment_do_not_supply_context(self):
        values=[]
        for locale_name in ("C","tr_TR.UTF-8","de_DE.UTF-8"):
            with patch.dict(os.environ,{"LANG":locale_name,"TZ":"Pacific/Auckland","SRX_VALUE":"injected"}):
                values.append(run_value("Iıiİ"))
        self.assertEqual(values,["Iıiİ"]*3)

    def test_no_clock_entropy_or_shell_access(self):
        with patch('time.time',side_effect=AssertionError('clock')), \
             patch('os.urandom',side_effect=AssertionError('random')), \
             patch('os.system',side_effect=AssertionError('shell')):
            self.assertEqual(run_value({"value":1}),{"value":1})

    def test_code_text_and_import_declarations_have_no_file_effect(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/"executed"
            text="__import__('pathlib').Path("+repr(str(target))+").write_text('bad')"
            self.assertEqual(run_value(text),text)
            data=program_data(True);data["expression"]={"op":"eval","value":text}
            with self.assertRaises(SrxError):SrxProgram(data,rule_id="r")
            self.assertFalse(target.exists())

    def test_diagnostics_are_repeatable_without_input_values(self):
        data=program_data(True);data["version"]="private-unsupported-version"
        results=[]
        for _ in range(2):
            try:SrxProgram(data,rule_id="r")
            except SrxError as error:results.append(error.diagnostic())
        self.assertEqual(results[0],results[1])
        self.assertNotIn(data["version"],json.dumps(results))
        results[0]["reason"]="edited"
        self.assertEqual(results[1]["reason"],"unsupported_version")

    def test_context_is_unmodified_by_multiple_evaluations(self):
        context=EvaluationContext(context_data(),rule_id="r");before=context.data
        for value in (None,False,[],{"x":2}):evaluate(SrxProgram(program_data(value),rule_id="r"),context)
        self.assertEqual(context.data,before)

    def test_context_subclass_cannot_run_evaluation_hooks(self):
        calls=[]
        class Context(EvaluationContext):
            @property
            def data(self):calls.append(1);return {}
        ctx=Context(context_data(),rule_id="r")
        with self.assertRaises(SrxError):evaluate(SrxProgram(program_data(True),rule_id="r"),ctx)
        self.assertEqual(calls,[])

    def test_portable_module_and_zipapp_keep_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/'built';build_distribution(target)
            moved=root/'moved';target.rename(moved);before=files_under(moved)
            body=("from specroad.srx import parse_program,EvaluationContext,evaluate\n"
                  f"p=parse_program({json.dumps(program_data([1,False,None])).encode()!r},rule_id='r')\n"
                  f"c=EvaluationContext({context_data()!r},rule_id='r')\n"
                  "assert evaluate(p,c)==[1,False,None]\n"
                  "assert type(evaluate(p,c)[1]) is bool\n")
            for location in (moved/'module',moved/'specroad.pyz'):
                result=run_python(['-I','-S','-B','-c','import sys;sys.path.insert(0,'+repr(str(location))+');\n'+body],root)
                self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(files_under(moved),before)
