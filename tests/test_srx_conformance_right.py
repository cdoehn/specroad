"""Conformance under explicit process variations; no human-output assertions."""
import copy
from concurrent.futures import ThreadPoolExecutor
from decimal import (DefaultContext, Context, ROUND_FLOOR, ROUND_UP, Inexact,
                     getcontext, localcontext)
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

from specroad.srx import (SrxError, SrxNumericError, SrxProgram, EvaluationContext,
                          evaluate, MISSING)
from support.srx import roots, expression_document, literal, binary
from support.srx_vectors import (load_corpus, validate_corpus, assert_case, observe_case,
                                 numeric_case, semantic_observation, _object, _constant)
from support.srx_numeric import vectors
from support.processes import run_python
from support.portable import build_distribution
from support.srx_numeric import changed_defaults, context_state


def ordered_objects(value):
    if type(value) is dict:
        return {k:ordered_objects(value[k]) for k in reversed(list(value))}
    if type(value) is list:
        return [ordered_objects(v) for v in value]
    return value


class SrxConformanceRightTests(unittest.TestCase):
    def test_additional_regression_vectors(self):
        for case in load_corpus()['cases']:
            if case['category']=='regression':
                with self.subTest(case=case['id']):assert_case(case)

    def test_full_corpus_under_changed_decimal_defaults(self):
        cases=load_corpus()['cases']
        baseline={c['id']:semantic_observation(assert_case(c)) for c in cases}
        with changed_defaults() as current:
            before=context_state(current);default=context_state(DefaultContext)
            for c in reversed(cases):
                self.assertEqual(semantic_observation(assert_case(c)),baseline[c['id']])
                self.assertEqual(context_state(getcontext()),before)
                self.assertEqual(context_state(DefaultContext),default)

    def test_all_vectors_survive_reordered_execution_and_object_keys(self):
        cases=load_corpus()['cases']
        baseline={c['id']:semantic_observation(assert_case(c)) for c in cases}
        for c in reversed(cases):
            self.assertEqual(semantic_observation(assert_case(ordered_objects(c))),baseline[c['id']])

    def test_numeric_corpus_adapter_preserves_all_original_decisions(self):
        for i,vector in enumerate(vectors()):
            before=copy.deepcopy(vector)
            with self.subTest(case=i):assert_case(numeric_case(vector,i))
            self.assertEqual(vector,before)

    def test_annex_u_explicit_precision_and_expected_outcomes(self):
        # Independent normative numeric decisions; never parse documentation text.
        expected=[('divide',1,8,3,0.125),('divide',1,8,2,'precision_exceeded'),
                  ('divide',1,3,34,'non_terminating'),('divide',1,0,34,'division_by_zero'),
                  ('add',0.1,0.2,34,0.3),('add',1.20,0.30,2,1.5),('add',999,1,1,1000),
                  ('divide',1,16,3,0.0625),('add',9007199254740992,1,34,'jcs_roundtrip_loss')]
        cases=[c for c in load_corpus()['cases'] if c['category']=='annex_u']
        self.assertEqual(len(cases),len(expected))
        for c,(op,a,b,p,value) in zip(cases,expected):
            self.assertEqual(c['program']['expression'],binary(op,literal(a),literal(b)))
            self.assertEqual(c['context']['project']['srx_policy']['decimal_precision'],p)
            want=c['expect'].get('reason') if type(value) is str else c['expect']['value']
            self.assertEqual(want,value)
            assert_case(c)

    def test_corpus_in_fresh_processes_with_distinct_hash_seeds_and_locales(self):
        # A small corpus runner, not a second full pytest suite. Only structured
        # outcomes are compared; no recommendation wording, timing or layout.
        root=Path(__file__).resolve().parents[1]
        code='''import sys,json,os,locale
from decimal import DefaultContext,getcontext,ROUND_UP,Inexact
sys.path[:0]=[sys.argv[1]+"/src",sys.argv[1]+"/tests"]
from support.srx_vectors import load_corpus,assert_case,semantic_observation
locale.setlocale(locale.LC_ALL, "C")
DefaultContext.prec=1;DefaultContext.rounding=ROUND_UP
getcontext().prec=2;getcontext().traps[Inexact]=True
cases=load_corpus()["cases"]
if os.environ.get("PYTHONHASHSEED")=="911":cases.reverse()
answer={c["id"]:semantic_observation(assert_case(c)) for c in cases}
print(json.dumps(answer,sort_keys=True))
'''
        with tempfile.TemporaryDirectory() as temporary:
            import os
            results=[]
            for seed,lang,tz in [('7','C','UTC'),('911','C.UTF-8','Pacific/Auckland')]:
                env=dict(os.environ,PYTHONHASHSEED=seed,LANG=lang,LC_ALL=lang,TZ=tz)
                result=subprocess.run([sys.executable,'-B','-c',code,str(root)],cwd=temporary,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                self.assertEqual(result.returncode,0,result.stderr.decode())
                results.append(json.loads(result.stdout))
            self.assertEqual(results[0],results[1])
            self.assertEqual(len(results[0]),len(load_corpus()['cases']))

    def test_graph_source_order_does_not_change_results(self):
        for case in load_corpus()['cases']:
            if 'graph' not in case:continue
            expected=semantic_observation(assert_case(case))
            changed=copy.deepcopy(case);changed['graph'].reverse()
            for artifact in changed['graph']:artifact['relations'].reverse()
            self.assertEqual(semantic_observation(assert_case(changed)),expected)

    def test_thread_reuse_keeps_numeric_contexts_and_inputs(self):
        cases=[c for c in load_corpus()['cases'] if c['category']=='annex_u']
        before=copy.deepcopy(cases)
        def one(index):
            with localcontext(Context(prec=index%5+1,rounding=ROUND_FLOOR)):
                saved=context_state(getcontext())
                value=semantic_observation(assert_case(cases[index%len(cases)]))
                assert context_state(getcontext())==saved
                return value
        with ThreadPoolExecutor(max_workers=4) as executor:got=list(executor.map(one,range(27)))
        expected=[semantic_observation(assert_case(cases[i%9])) for i in range(27)]
        self.assertEqual(got,expected);self.assertEqual(cases,before)

    def test_failure_is_repeated_without_poisoning_valid_evaluation(self):
        good=next(c for c in load_corpus()['cases'] if c['expect']['kind']=='value')
        bad=next(c for c in load_corpus()['cases'] if c['expect'].get('reason')=='division_by_zero')
        baseline=semantic_observation(assert_case(bad))
        for _ in range(3):
            assert_case(good);self.assertEqual(semantic_observation(assert_case(bad)),baseline)

    def test_machine_diagnostics_never_embed_operand_values(self):
        secret='do-not-leak-operand-92341'
        p=SrxProgram(expression_document(binary('add',literal(secret),literal(1))),rule_id='r')
        with self.assertRaises(SrxError) as caught:evaluate(p,EvaluationContext(roots(),rule_id='r'))
        data=caught.exception.diagnostic()
        self.assertNotIn(secret,json.dumps(data))
        self.assertEqual(data['rule_id'],'r')
        self.assertEqual(data['input_pointer'],'/expression/args/0')
        self.assertEqual(data['repair_action'],'supply_declared_type')

    def test_diagnostic_projection_has_no_import_or_open_side_effect(self):
        from support.io_guards import block_imports_and_open
        error=SrxNumericError('non_terminating',rule_id='offline')
        with block_imports_and_open():data=error.diagnostic()
        self.assertEqual(data['repair_action'],'use_exact_numeric_contract')

    def test_unrecognized_reason_stays_an_explicit_generic_repair(self):
        d=SrxError('future_reason',rule_id='r').diagnostic()
        self.assertEqual(d['reason'],'future_reason')
        self.assertEqual(d['repair_action'],'check_explicit_input')

    def test_context_error_retains_distinct_input_and_expression_pointers(self):
        c=next(c for c in load_corpus()['cases'] if c['id']=='SRX1-policy-context-not-expression')
        d=assert_case(c)
        self.assertEqual(d['subject'],'context');self.assertNotEqual(d['input_pointer'],d['expression_pointer'])

    def test_raw_syntax_failure_has_structured_position(self):
        c=next(c for c in load_corpus()['cases'] if c['id']=='SRX1-raw-trailing')
        d=assert_case(c)
        self.assertIs(type(d['position']),int);self.assertGreaterEqual(d['position'],0)
        self.assertIs(type(d['line']),int);self.assertIs(type(d['column']),int)

    def test_foreign_corpus_objects_are_rejected_before_copy_hooks(self):
        calls=[]
        class Foreign:
            def __deepcopy__(self,memo):calls.append('copy');return 1
        corpus=load_corpus();corpus['cases'][0]['context']['x']=Foreign()
        with self.assertRaises(ValueError):validate_corpus(corpus)
        self.assertEqual(calls,[])

    def test_cyclic_corpus_is_rejected(self):
        c=load_corpus();c['cases'][0]['context']['cycle']=c
        with self.assertRaises(ValueError):validate_corpus(c)

    def test_nonfinite_expected_value_is_rejected(self):
        for v in (float('nan'),float('inf'),float('-inf')):
            c=load_corpus();c['cases'][0]['expect']={'kind':'value','value':v}
            with self.assertRaises(ValueError):validate_corpus(c)

    def test_nonfinite_raw_json_constant_in_corpus_is_rejected(self):
        with self.assertRaises(ValueError):json.loads('{"x":NaN}',parse_constant=_constant)

    def test_duplicate_corpus_json_key_is_rejected(self):
        with self.assertRaises(ValueError):json.loads('{"x":1,"x":2}',object_pairs_hook=_object)

    def test_multiple_program_sources_are_rejected(self):
        c=load_corpus();c['cases'][0]['program_utf8']='{}'
        with self.assertRaises(ValueError):validate_corpus(c)

    def test_unknown_category_is_not_silently_unexecuted(self):
        c=load_corpus();c['cases'][0]['category']='skip'
        with self.assertRaises(ValueError):validate_corpus(c)

    def test_unknown_expected_field_is_not_silently_ignored(self):
        c=load_corpus();case=next(x for x in c['cases'] if x['expect']['kind']=='error');case['expect']['reason_typo']='x'
        with self.assertRaises(ValueError):validate_corpus(c)

    def test_program_text_is_not_a_path_instruction(self):
        c=load_corpus()['cases'][0];del c['program'];c['program_utf8']='/etc/passwd'
        with patch('builtins.open',side_effect=AssertionError('read')):d=observe_case(c)
        self.assertEqual(d['kind'],'error')

    def test_shipped_distributions_have_same_diagnostic_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);out=root/'out';build_distribution(out);moved=root/'renamed';out.rename(moved)
            code='''from specroad.srx import *
c=EvaluationContext({'artifact':{},'project':{},'configuration':None,'relations':[]},rule_id='portable')
p=SrxProgram({'language':'srx','version':'1.0','expression':{'op':'divide','args':[{'op':'literal','value':1},{'op':'literal','value':0}]}},rule_id='portable')
try:evaluate(p,c)
except SrxError as error:
 d=error.diagnostic()
 assert d['code']=='SRV197' and d['diagnostic_version']==1
 assert d['repair_action']=='supply_nonzero_divisor' and d['input_pointer']=='/expression'
else:raise AssertionError('failure missing')
'''
            for source in (moved/'module',moved/'specroad.pyz'):
                prefix='import sys;sys.path.insert(0,'+repr(str(source))+');\n'
                result=run_python(['-I','-S','-B','-c',prefix+code],root)
                self.assertEqual(result.returncode,0,result.stderr.decode())
