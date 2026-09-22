"""Security and error precedence with resource policies; no host-performance gates."""
import copy
import json
import os
from pathlib import Path
import random
import socket
import subprocess
import tempfile
import time
from unittest.mock import patch
import pytest
from specroad.srx import (SrxProgram, EvaluationContext, SrxError, SrxNumericError,
    SrxStructureError, SrxResourcePolicyError, StructureLimits, WorkTargets,
    ResourcePolicy, evaluate, evaluate_with_usage, parse_program, EvaluationObservation)
from specroad.srx.resources import ResourceUsage, StructureObservation, SoftTargetEvent
from support.srx import roots, literal, field, binary, quantifier, expression_document
from support.srx_resources import observed
from support.srx_graph import chain, graph, reach, aid, count
from support.portable import build_distribution
from support.processes import run_python


@pytest.mark.parametrize('op',['regex','eval','exec','import','getattr','read_file','http_get','now','random','shell','call'])
def test_forbidden_operations_rejected_in_short_circuited_branches(op):
    doc=expression_document(binary('or',literal(True),{'op':op}))
    with pytest.raises(SrxError) as e:SrxProgram(doc,rule_id='forbidden')
    assert e.value.reason=='unsupported_operator' and e.value.pointer=='/expression/args/1/op'
    assert e.value.resource_usage is None


@pytest.mark.parametrize('wrapper',['empty_any','empty_all','empty_none','depth_zero'])
def test_inactive_predicates_still_validate_all_operators(wrapper):
    bad={'op':'shell','command':'not executable'}
    node=reach(depth=0,where=bad) if wrapper=='depth_zero' else quantifier(wrapper[6:],literal([]),bad)
    with pytest.raises(SrxError) as e:SrxProgram(expression_document(node),rule_id='r')
    assert e.value.reason=='unsupported_operator' and e.value.pointer=='/expression/where/op'


def test_forbidden_expression_never_reaches_executor_or_snapshot():
    node=binary('or',literal(True),{'op':'exec','code':'do not run'})
    with patch('specroad.srx.program.JsonSnapshot',side_effect=AssertionError('snapshot called')):
        with pytest.raises(SrxError) as e:SrxProgram(expression_document(node),rule_id='r')
    assert e.value.reason=='unsupported_operator'


def test_foreign_graph_filter_comparison_hooks_are_never_called():
    calls=[]
    class Foreign:
        def __eq__(self,other):calls.append('eq');raise AssertionError('executed')
        def __iter__(self):calls.append('iter');raise AssertionError('executed')
    node=count(Foreign())
    with pytest.raises(SrxError):SrxProgram(expression_document(node),rule_id='r')
    assert calls==[]


def test_foreign_language_and_operator_strings_do_not_run_equality():
    calls=[]
    class Foreign(str):
        def __eq__(self,other):calls.append('eq');raise AssertionError('executed')
        def __hash__(self):calls.append('hash');raise AssertionError('executed')
    for key in ('language','version','op'):
        doc=expression_document(literal(True))
        if key=='op':doc['expression']['op']=Foreign('literal')
        else:doc[key]=Foreign(doc[key])
        with pytest.raises(SrxError):SrxProgram(doc,rule_id='r')
    assert calls==[]


def test_foreign_keys_are_rejected_without_rehashing_them():
    calls=[]
    class Key(str):
        def __hash__(self):calls.append('hash');return str.__hash__(self)
    doc=expression_document({Key('op'):'literal','value':1});calls.clear()
    with pytest.raises(SrxError):SrxProgram(doc,rule_id='r')
    assert calls==[]


def test_json_attributes_are_data_not_reflection():
    data={'__class__':{'__bases__':['ordinary JSON']}}
    assert observed(field('/__class__/__bases__/0'),artifact=data).value=='ordinary JSON'
    assert observed(literal({'op':'getattr','name':'__class__'})).value=={'op':'getattr','name':'__class__'}


def test_literal_code_does_not_create_files_or_execute():
    with tempfile.TemporaryDirectory() as temporary:
        marker=Path(temporary)/'unwanted'
        code="__import__('pathlib').Path(%r).write_text('bad')" % str(marker)
        value={'op':'exec','code':code,'url':'https://invalid.example/no-access'}
        assert observed(literal(value)).value==value
        assert not marker.exists() and list(Path(temporary).iterdir())==[]


def test_evaluation_observes_no_file_network_clock_random_or_shell():
    data=roots({'items':[True]*10});data['project']['resource_limits']={'srx_iterations':1}
    program=SrxProgram(expression_document(quantifier('all',field('/items'),field('',context='item'))),rule_id='r')
    context=EvaluationContext(data,rule_id='r')
    def forbidden(*a,**kw):raise AssertionError('unexpected host operation')
    with patch('builtins.open',forbidden),patch.object(os,'open',forbidden),\
         patch.object(os,'getenv',forbidden),patch.object(os,'urandom',forbidden),\
         patch.object(os,'system',forbidden),patch.object(socket,'socket',forbidden),\
         patch.object(subprocess,'Popen',forbidden),patch.object(time,'time',forbidden),\
         patch.object(time,'monotonic',forbidden),patch.object(random,'random',forbidden):
        result=evaluate_with_usage(program,context)
        assert result.value is True and result.usage.iterations==10


def test_soft_events_are_bounded_and_have_first_crossing_positions():
    node=quantifier('all',literal([True]*1001),field('',context='item'))
    result=observed(node,limits={'srx_operations':1,'srx_iterations':1})
    events=result.usage.data['events']
    assert len(events)==2 and [e['metric'] for e in events]==['evaluation_steps','iterations']
    assert events[0]['expression_pointer']=='/expression/array' and events[0]['observed']==2
    assert events[1]['expression_pointer']=='/expression/where' and events[1]['observed']==2
    assert all(e['kind']=='soft_budget_exceeded' and e['target']==1 for e in events)
    assert result.usage.policy.work.evaluation_steps==1


def test_event_data_cannot_modify_owned_measurements():
    result=observed(binary('eq',literal(1),literal(1)),limits={'srx_operations':1})
    result.usage.data['events'][0]['target']=500
    assert result.usage.events[0].target==1


def test_real_numeric_error_after_overrun_keeps_numeric_diagnostic():
    node=binary('add',literal(2),binary('divide',literal(1),literal(0)))
    errors=[]
    for target in (1,100):
        with pytest.raises(SrxNumericError) as e:observed(node,limits={'srx_operations':target})
        assert e.value.reason=='division_by_zero' and e.value.code=='SRV197'
        report=e.value.resource_usage.data
        assert report['evaluation_completed'] is False and report['checkpoint'] is None
        assert report['work_counts']['evaluation_steps']==5
        assert report['soft_budget_exceeded'] is (target==1)
        errors.append(e.value.diagnostic())
    assert errors[0]==errors[1]


def test_quantifier_type_error_is_not_false_after_soft_event():
    node=quantifier('all',literal([True,None,False]),field('',context='item'))
    with pytest.raises(SrxError) as e:observed(node,limits={'srx_iterations':1})
    assert e.value.reason=='operand_type' and e.value.actual=='null'
    assert e.value.resource_usage.iterations==2 and not e.value.resource_usage.evaluation_completed
    assert e.value.resource_usage.data['exceeded_targets']==['iterations']


def test_failed_observation_does_not_pollute_next_call():
    c=EvaluationContext(roots(),rule_id='r')
    p=SrxProgram(expression_document(binary('divide',literal(1),literal(0))),rule_id='r')
    with pytest.raises(SrxError) as e:evaluate_with_usage(p,c)
    before=e.value.resource_usage.data
    good=SrxProgram(expression_document(literal(2)),rule_id='r')
    assert evaluate_with_usage(good,c).usage.evaluation_steps==1
    assert e.value.resource_usage.data==before


def test_failed_usage_cannot_be_wrapped_as_success():
    usage=ResourceUsage(StructureObservation(1,1),ResourcePolicy(),1,0,0,False)
    with pytest.raises(ValueError):EvaluationObservation(True,usage,rule_id='r')


def test_invalid_event_observations_are_rejected():
    with pytest.raises(ValueError):SoftTargetEvent('evaluation_steps',1,1,'/expression')
    with pytest.raises(ValueError):SoftTargetEvent('unknown',1,2,'/expression')
    with pytest.raises(ValueError):ResourceUsage(StructureObservation(1,1),ResourcePolicy(),True,0,0,True)
    policy=ResourcePolicy(work=WorkTargets(1,1,1))
    with pytest.raises(ValueError):ResourceUsage(StructureObservation(1,1),policy,2,0,0,True)


def test_graph_work_above_target_preserves_first_real_error():
    values=chain()
    where=binary('or',binary('eq',field('/id'),literal(aid(number=99))),literal(None))
    with pytest.raises(SrxError) as e:observed(reach(depth=3,where=where),artifact=values[0],graph=graph(values),limits={'srx_graph_steps':1})
    assert e.value.reason=='operand_type' and e.value.actual=='null'
    assert e.value.resource_usage.graph_steps>1 and not e.value.resource_usage.evaluation_completed


def test_graph_work_uses_deterministic_read_order():
    values=chain();node=reach(aid(number=3),depth=2)
    a=observed(node,artifact=values[0],graph=graph(values),limits={'srx_graph_steps':1})
    b=observed(node,artifact=values[0],graph=graph(list(reversed(values))),limits={'srx_graph_steps':1})
    assert a.value==b.value and a.usage.data==b.usage.data


def test_soft_targets_do_not_activate_extra_paths():
    values=chain();node=reach(aid(number=3),depth=0)
    result=observed(node,artifact=values[0],graph=graph(values),limits={'srx_graph_steps':1})
    assert result.value is False and result.usage.evaluation_steps==4
    assert result.usage.graph_steps==2


def test_wide_ast_stops_at_small_limit_before_late_unknown_operator():
    node={'op':'and','args':[literal(True)]*20000+[{'op':'exec'}]}
    with pytest.raises(SrxStructureError) as e:
        SrxProgram(expression_document(node),rule_id='r',structure_limits=StructureLimits(3,10))
    assert e.value.observed==4 and e.value.pointer=='/expression/args/2'


def test_large_valid_ast_is_not_limited_by_work_target():
    node={'op':'and','args':[literal(True)]*1201}
    result=observed(node,limits={'srx_operations':1,'srx_nodes':1202,'srx_depth':2})
    assert result.value is True and result.usage.evaluation_steps==1202


def test_deep_ast_is_validated_without_python_recursion():
    node=literal(True)
    for _ in range(1100):node={'op':'not','arg':node}
    result=observed(node,limits={'srx_depth':1101,'srx_operations':1})
    assert result.value is True and result.usage.structure.ast_depth==1101
    with pytest.raises(SrxStructureError):observed(node,limits={'srx_depth':1100})


@pytest.mark.parametrize('limits',[{'srx_steps':1},{'srx_depth':None},{'srx_iterations':True},{'srx_graph_steps':1.5},{'srx_operations':'unlimited'}])
def test_unrecognized_or_nonintegral_policy_cannot_disable_guards(limits):
    with pytest.raises(SrxResourcePolicyError) as e:observed(literal(True),limits=limits)
    assert e.value.diagnostic()['exit_code']==2


def test_unknown_resource_field_has_valid_json_pointer():
    with pytest.raises(SrxResourcePolicyError) as e:observed(literal(True),limits={'srx_x~/y':1})
    assert e.value.pointer=='/project/resource_limits/srx_x~0~1y'


def test_non_srx_configuration_is_passive_data():
    result=observed(literal(True),limits={'model_bytes':1,'trace_depth':0})
    assert result.value is True and result.usage.policy==ResourcePolicy()


def test_original_inputs_survive_errors_and_success():
    node=binary('add',literal(0.1),literal(0.2));doc=expression_document(node)
    data=roots();data['project']['resource_limits']={'srx_operations':1}
    before=copy.deepcopy((doc,data))
    p=SrxProgram(doc,rule_id='r');c=EvaluationContext(data,rule_id='r')
    assert evaluate_with_usage(p,c).value==0.3
    assert (doc,data)==before
    with pytest.raises(SrxStructureError):SrxProgram(doc,rule_id='r',structure_limits=StructureLimits(1,1))
    assert (doc,data)==before


def test_raw_parser_preserves_duplicate_key_error():
    raw=b'{"language":"srx","version":"1.0","expression":{"op":"literal","op":"exec","value":1}}'
    with pytest.raises(SrxError) as e:parse_program(raw,rule_id='r')
    assert e.value.reason=='duplicate_key' and e.value.resource_usage is None


def test_portable_resources_evaluate_with_owned_usage():
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary);output=root/'built';build_distribution(output);moved=root/'moved';output.rename(moved)
        code='''
from specroad.srx import SrxProgram,EvaluationContext,evaluate_with_usage,SrxStructureError
p=SrxProgram({'language':'srx','version':'1.0','expression':{'op':'add','args':[{'op':'literal','value':0.1},{'op':'literal','value':0.2}]}},rule_id='portable')
c=EvaluationContext({'artifact':{},'configuration':None,'project':{'resource_limits':{'srx_operations':1}},'relations':[]},rule_id='portable')
o=evaluate_with_usage(p,c)
assert o.value==0.3 and o.usage.evaluation_steps==3 and o.usage.data['soft_budget_exceeded']
assert o.usage.data['checkpoint'] is None
'''
        for source in (moved/'module',moved/'specroad.pyz'):
            prefix='import sys;sys.path.insert(0,'+repr(str(source))+');\n'
            result=run_python(['-I','-S','-B','-c',prefix+code],root)
            assert result.returncode==0,result.stderr.decode()
