"""Exact SRX arithmetic and project policy; no human-output or doc assertions."""
import copy
from dataclasses import FrozenInstanceError
import pytest
from specroad.srx import NumericPolicy, SrxPolicyError, SrxNumericError, SrxError, EvaluationContext, SrxProgram, evaluate, arithmetic_operation
from support.srx_numeric import vectors, calculate
from support.srx import roots, literal, binary, run, field, expression_document, quantifier


def test_normative_decision_vectors():
    for item in vectors():
        args=(item['op'],item['left'],item['right'],item['precision'])
        if 'error' in item:
            with pytest.raises(SrxNumericError) as exc:calculate(*args)
            assert exc.value.code=='SRV197' and exc.value.reason==item['error']
        else:
            assert calculate(*args)==item['value']


@pytest.mark.parametrize('op,a,b,value', [('add',2,3,5),('subtract',2,3,-1),('multiply',3,-4,-12),
 ('divide',-1,8,-0.125),('multiply',0.1,0.2,0.02),('subtract',0.3,0.1,0.2),('divide',0,2,0)])
def test_basic_exact_results(op,a,b,value):
    assert calculate(op,a,b)==value


def test_default_policy_is_materialized_separately_from_original_context():
    data=roots();before=copy.deepcopy(data);context=EvaluationContext(data,rule_id='r')
    assert context.numeric_policy.data=={'numeric_policy_version':'srx-decimal-v1','decimal_precision':34}
    assert data==before and context.data==before


def test_policy_is_immutable_and_data_is_independent():
    policy=NumericPolicy()
    with pytest.raises(FrozenInstanceError): policy.decimal_precision=2
    policy.data['decimal_precision']=2
    assert policy.decimal_precision==34


def test_project_policy_changes_result_not_program():
    expression=SrxProgram(expression_document(binary('divide',literal(1),literal(8))),rule_id='same')
    for digits,passed in ((3,True),(2,False)):
        data=roots();data['project']['srx_policy']={'decimal_precision':digits}
        context=EvaluationContext(data,rule_id='same')
        if passed:assert evaluate(expression,context)==0.125
        else:
            with pytest.raises(SrxNumericError) as exc:evaluate(expression,context)
            assert exc.value.reason=='precision_exceeded'


@pytest.mark.parametrize('policy',[None,True,[],{'decimal_precision':0},{'decimal_precision':1001},
 {'decimal_precision':True},{'decimal_precision':1.5},{'decimal_precision':'34'},
 {'numeric_policy_version':'other'},{'precision':34}])
def test_bad_policies_are_code_two(policy):
    data=roots();data['project']['srx_policy']=policy
    with pytest.raises(SrxPolicyError) as exc:EvaluationContext(data,rule_id='policy')
    assert exc.value.exit_code==2 and exc.value.diagnostic()['rule_id']=='policy'


@pytest.mark.parametrize('operand',[None,False,True,'2',[],{}])
def test_no_numeric_coercion(operand):
    with pytest.raises(SrxError) as exc:calculate('add',operand,1)
    assert exc.value.code=='SRV110' and exc.value.reason=='operand_type'


def test_missing_is_not_zero():
    with pytest.raises(SrxError) as exc:run(binary('add',field('/absent'),literal(1)))
    assert exc.value.actual=='missing'


def test_nested_arithmetic_returns_plain_json_number():
    assert run(binary('multiply',binary('add',literal(0.1),literal(0.2)),literal(10)))==3


def test_arithmetic_inside_quantifier():
    node=quantifier('all',literal([1,2,3]),binary('gt',binary('add',field('',context='item'),literal(1)),literal(1)))
    assert run(node) is True


def test_boolean_short_circuit_skips_runtime_numeric_failure():
    assert run(binary('or',literal(True),binary('divide',literal(1),literal(0)))) is True


def test_failure_pointer_identifies_nested_operation():
    with pytest.raises(SrxNumericError) as exc:run(binary('add',literal(1),binary('divide',literal(1),literal(0))))
    assert exc.value.pointer=='/expression/args/1'


def test_strict_binary_arity():
    for args in ([],[literal(1)],[literal(1)]*3):
        with pytest.raises(SrxError):run({'op':'add','args':args})


def test_foreign_number_hooks_never_execute():
    calls=[]
    class Foreign:
        def __float__(self):calls.append('float');return 1.0
        def __str__(self):calls.append('str');return '1'
    with pytest.raises(SrxError):arithmetic_operation('add',Foreign(),1,policy=NumericPolicy(),rule_id='r')
    assert calls==[]


def test_nonfinite_direct_operands_have_numeric_diagnostic():
    for value in (float('nan'),float('inf'),float('-inf')):
        with pytest.raises(SrxNumericError) as exc:arithmetic_operation('add',value,1,policy=NumericPolicy(),rule_id='r')
        assert exc.value.reason=='non_finite'


def test_explicit_snapshot_preserves_original_input():
    data=roots({'a':0.1}); data['project']['srx_policy']={'decimal_precision':3};before=copy.deepcopy(data)
    context=EvaluationContext(data,rule_id='r')
    data['project']['srx_policy']['decimal_precision']=1
    program=SrxProgram(expression_document(binary('add',field('/a'),literal(0.025))),rule_id='r')
    assert evaluate(program,context)==0.125
    assert context.data==before
