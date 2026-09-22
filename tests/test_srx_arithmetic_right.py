"""Exactness, diagnostic, global-context and portable execution regressions."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import copy
from decimal import Context, Decimal, DefaultContext, getcontext, localcontext, ROUND_FLOOR, ROUND_UP, Inexact
from fractions import Fraction
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import pytest
from specroad.srx import (NumericPolicy, SrxPolicyError, SrxNumericError, SrxError,
                         EvaluationContext, SrxProgram, evaluate, arithmetic_operation,
                         parse_program, parse_context)
from support.srx import roots, literal, binary, run, field, expression_document
from support.srx_numeric import vectors, calculate
from support.srx_graph import chain, graph, call, reach
from support.portable import build_distribution
from support.processes import run_python


from support.srx_numeric import context_state, changed_defaults


def test_all_vectors_survive_modified_process_decimal_defaults():
    with changed_defaults() as current:
        before=context_state(current);default_before=context_state(DefaultContext)
        for item in vectors():
            if 'error' in item:
                with pytest.raises(SrxNumericError) as exc:
                    calculate(item['op'],item['left'],item['right'],item['precision'])
                assert exc.value.reason==item['error']
            else:
                assert calculate(item['op'],item['left'],item['right'],item['precision'])==item['value']
            assert context_state(getcontext())==before
            assert context_state(DefaultContext)==default_before


def test_direct_binary_float_expansion_is_not_used():
    assert Fraction(0.1)+Fraction(0.2)!=Fraction(Decimal('0.3'))
    assert calculate('add',0.1,0.2)==0.3


@pytest.mark.parametrize('op,a,b,value,p',[
 ('add',-999,-1,-1000,1),('subtract',1000,999,1,1),
 ('divide',6,3,2,1),('divide',0,3,0,1),('divide',1,40,0.025,2),
 ('divide',-1,40,-0.025,2),('multiply',1.25,8,10,1),
 ('multiply',1e-100,1e100,1,1),('divide',1e100,1e100,1,1),
 ('add',-0.0,0,0,1),('divide',-0.0,-3,0,1)])
def test_result_precision_ignores_input_width_and_neutral_coefficient_zeros(op,a,b,value,p):
    assert calculate(op,a,b,p)==value


@pytest.mark.parametrize('a,b',[ (1,3),(1,6),(5,21),(-1,7),(2,15)])
def test_nonterminating_is_not_repaired_by_more_precision(a,b):
    for p in (1,34,1000):
        with pytest.raises(SrxNumericError) as exc:calculate('divide',a,b,p)
        assert exc.value.reason=='non_terminating'


@pytest.mark.parametrize('op,a,b,reason',[
 ('divide',1,0,'division_by_zero'),('divide',0,0,'division_by_zero'),
 ('divide',1,-0.0,'division_by_zero'),('divide',1,8,'precision_exceeded'),
 ('multiply',1e308,10,'jcs_roundtrip_loss'),
 ('divide',5e-324,2,'jcs_roundtrip_loss'),
 ('add',9007199254740992,1,'jcs_roundtrip_loss')])
def test_numerical_reasons_are_disjoint_and_bound_to_rule(op,a,b,reason):
    p=2 if reason=='precision_exceeded' else 1000
    with pytest.raises(SrxNumericError) as exc:calculate(op,a,b,p)
    info=exc.value.diagnostic()
    assert info['code']=='SRV197' and info['reason']==reason
    assert info['rule_id'] is not None and info['expression_pointer']=='/expression'


@pytest.mark.parametrize('value',[float('inf'),float('-inf'),float('nan')])
def test_nonfinite_program_or_context_has_numeric_code(value):
    for action in (lambda:SrxProgram(expression_document(literal(value)),rule_id='finite'),
                   lambda:EvaluationContext(roots({'number':value}),rule_id='finite')):
        with pytest.raises(SrxNumericError) as exc:action()
        assert exc.value.reason=='non_finite' and exc.value.code=='SRV197'


@pytest.mark.parametrize('token,reason',[(b'NaN','non_finite'),(b'Infinity','non_finite'),
 (b'-Infinity','non_finite'),(b'1e9999','non_finite'),
 (b'9007199254740993','jcs_roundtrip_loss'),(b'0.1234567890123456789','jcs_roundtrip_loss')])
def test_numeric_raw_program_errors_keep_pointer(token,reason):
    raw=b'{"language":"srx","version":"1.0","expression":{"op":"literal","value":'+token+b'}}'
    with pytest.raises(SrxNumericError) as exc:parse_program(raw,rule_id='raw-numeric')
    assert exc.value.reason==reason and exc.value.pointer=='/expression/value'
    assert exc.value.diagnostic()['subject']=='expression'


def test_context_raw_number_failure_is_not_expression_data():
    raw=b'{"artifact":{"n":9007199254740993},"project":{},"configuration":null,"relations":[]}'
    with pytest.raises(SrxNumericError) as exc:parse_context(raw,rule_id='context-numeric')
    assert exc.value.pointer=='/artifact/n' and exc.value.subject=='context'


def test_raw_numbers_and_original_bytes_are_not_reformatted():
    raw=b'{"language":"srx", "version":"1.0", "expression":{"op":"add", "args":[{"op":"literal","value":1.20},{"op":"literal","value":0.30}]}}'
    p=parse_program(raw,rule_id='original')
    assert evaluate(p,EvaluationContext(roots(),rule_id='original'))==1.5
    assert p.source_bytes==raw


def test_non_numeric_parse_errors_remain_structural():
    for raw,reason in ((b'{"a":1,"a":2}','duplicate_key'),(b'{','invalid_json')):
        with pytest.raises(SrxError) as exc:parse_program(raw,rule_id='syntax')
        assert exc.value.code=='SRV110' and exc.value.reason==reason


def test_jcs_unrepresentable_integer_operand_is_not_silently_rounded():
    with pytest.raises(SrxNumericError) as exc:calculate('subtract',9007199254740993,9007199254740992)
    assert exc.value.reason=='jcs_roundtrip_loss'


def test_decimal_and_fraction_are_not_implicit_srx_json_numbers():
    for number in (Decimal('0.1'),Fraction(1,10)):
        with pytest.raises(SrxError) as exc:
            arithmetic_operation('add',number,1,policy=NumericPolicy(),rule_id='types')
        assert exc.value.code=='SRV110'


def test_bounded_integer_corpus_against_independent_rational_oracle():
    # These small finite cases have exact binary64/JCS representations; compare
    # against rational mathematics independently of the implementation helpers.
    for a in range(-12,13):
        for b in range(-10,11):
            for op,expected in [('add',a+b),('subtract',a-b),('multiply',a*b)]:
                assert Fraction(calculate(op,a,b))==Fraction(expected)
            if b in (-10,-8,-5,-4,-2,-1,1,2,4,5,8,10):
                got=calculate('divide',a,b)
                assert Fraction(Decimal(str(got)))==Fraction(a,b)


def test_threaded_reuse_with_distinct_policies_has_no_cross_contamination():
    p=SrxProgram(expression_document(binary('divide',literal(1),literal(8))),rule_id='threads')
    contexts=[]
    for precision in (2,3,34):
        d=roots();d['project']['srx_policy']={'decimal_precision':precision}
        contexts.append(EvaluationContext(d,rule_id='threads'))
    def one(n):
        with localcontext() as c:
            c.prec=n%7+1;c.rounding=ROUND_UP
            before=context_state(c)
            try: answer=evaluate(p,contexts[n%3])
            except SrxNumericError as exc:answer=exc.reason
            assert context_state(getcontext())==before
            return answer
    with ThreadPoolExecutor(max_workers=4) as executor:result=list(executor.map(one,range(24)))
    assert result==['precision_exceeded',0.125,0.125]*8


def test_numeric_policy_survives_graph_target_context_switches():
    values=chain()
    predicate=binary('eq',binary('divide',literal(1),literal(8)),literal(0.125))
    node=reach(depth=2,where=predicate)
    assert call(node,values,extra_roots={'project':{'srx_policy':{'decimal_precision':3}}}) is True
    with pytest.raises(SrxNumericError) as exc:
        call(node,values,extra_roots={'project':{'srx_policy':{'decimal_precision':2}}})
    assert exc.value.reason=='precision_exceeded'


def test_iterative_deep_arithmetic_chain():
    node=literal(0)
    for _ in range(1200):node=binary('add',node,literal(1))
    assert run(node)==1200


def test_no_ambient_io_for_arithmetic_evaluation():
    context=EvaluationContext(roots(),rule_id='offline')
    p=SrxProgram(expression_document(binary('add',literal(0.1),literal(0.2))),rule_id='offline')
    with patch('builtins.open',side_effect=AssertionError('I/O')):
        assert evaluate(p,context)==0.3


def test_numeric_failure_does_not_destroy_context():
    c=EvaluationContext(roots(),rule_id='reuse');before=c.data
    failing=SrxProgram(expression_document(binary('divide',literal(1),literal(3))),rule_id='reuse')
    valid=SrxProgram(expression_document(binary('multiply',literal(5),literal(2))),rule_id='reuse')
    for _ in range(2):
        with pytest.raises(SrxNumericError):evaluate(failing,c)
        assert evaluate(valid,c)==10 and c.data==before


@pytest.mark.parametrize('policy',[{'decimal_precision':None},{'numeric_policy_version':None},
 {'numeric_policy_version':True},{'numeric_policy_version':''},{'unknown':34}])
def test_policy_bad_values_never_fall_back(policy):
    d=roots();d['project']['srx_policy']=policy
    with pytest.raises(SrxPolicyError) as exc:EvaluationContext(d,rule_id='bad-policy')
    assert exc.value.exit_code==2


def test_portable_distributions_use_same_exact_policy():
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary);out=root/'out';build_distribution(out);moved=root/'moved';out.rename(moved)
        code='''
from decimal import getcontext
from specroad.srx import EvaluationContext,SrxProgram,evaluate,SrxNumericError
getcontext().prec=1
c=EvaluationContext({'artifact':{},'project':{},'configuration':None,'relations':[]},rule_id='portable')
p=SrxProgram({'language':'srx','version':'1.0','expression':{'op':'add','args':[{'op':'literal','value':0.1},{'op':'literal','value':0.2}]}},rule_id='portable')
assert evaluate(p,c)==0.3
assert getcontext().prec==1
'''
        for source in (moved/'module',moved/'specroad.pyz'):
            prefix='import sys;sys.path.insert(0,'+repr(str(source))+');\n'
            result=run_python(['-I','-S','-B','-c',prefix+code],root)
            assert result.returncode==0,result.stderr.decode()
