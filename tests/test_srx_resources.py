"""Hard AST guards and non-failing work targets, with real evaluation oracles."""
import copy
import json
from dataclasses import FrozenInstanceError
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import pytest
from specroad.srx import (SrxProgram, EvaluationContext, SrxError, SrxStructureError,
    SrxResourcePolicyError, StructureLimits, WorkTargets, ResourcePolicy,
    evaluate, evaluate_with_usage, parse_program, MISSING)
from specroad.model.configuration import ProjectConfiguration
from specroad.model.semantic_configuration import semantic_configuration
from support.model import configuration_value
from support.srx import roots, literal, field, binary, quantifier, expression_document
from support.srx_resources import observed
from support.srx_graph import chain, graph, count, reach, aid


def test_defaults_are_exposed_without_modifying_context():
    data=roots();original=copy.deepcopy(data)
    c=EvaluationContext(data,rule_id='r')
    assert c.data==original==data
    assert c.resource_policy.data=={'version':'srx-resource-v1',
        'structure':{'ast_nodes':10000,'ast_depth':2048},
        'work_targets':{'evaluation_steps':1000000,'iterations':1000000,'graph_steps':2000000}}


def test_explicit_project_limits_are_bound():
    result=observed(literal(True),limits={'srx_nodes':3,'srx_depth':5,
        'srx_operations':7,'srx_iterations':11,'srx_graph_steps':13})
    assert result.usage.policy.structure==StructureLimits(3,5)
    assert result.usage.policy.work==WorkTargets(7,11,13)


@pytest.mark.parametrize('value',[0,-1,True,False,None,1.5,'10','unlimited',[],{}])
def test_invalid_structural_values_are_not_silently_unlimited(value):
    with pytest.raises(SrxResourcePolicyError):StructureLimits(ast_nodes=value)
    with pytest.raises(SrxResourcePolicyError):StructureLimits(ast_depth=value)


@pytest.mark.parametrize('name',['srx_nodes','srx_depth','srx_operations','srx_iterations','srx_graph_steps'])
def test_zero_project_limits_are_usage_errors(name):
    with pytest.raises(SrxResourcePolicyError) as e:observed(literal(True),limits={name:0})
    assert e.value.exit_code==2 and e.value.pointer.endswith('/'+name)


def test_policy_is_immutable_and_returned_maps_are_owned():
    policy=ResourcePolicy()
    with pytest.raises(FrozenInstanceError):policy.structure=StructureLimits(1,1)
    policy.data['structure']['ast_nodes']=1
    assert policy.structure.ast_nodes==10000


def test_literal_payload_is_not_an_executable_ast():
    value={'op':'import','args':[{'op':'regex'}]*50}
    result=observed(literal(value),limits={'srx_nodes':1,'srx_depth':1})
    assert result.value==value and result.usage.structure.data=={'ast_nodes':1,'ast_depth':1}


def test_exact_node_boundary_passes():
    result=observed(binary('and',literal(True),literal(False)),limits={'srx_nodes':3,'srx_depth':2})
    assert result.value is False and result.usage.structure.ast_nodes==3


def test_node_boundary_reports_first_overflow_pointer():
    with pytest.raises(SrxStructureError) as e:
        SrxProgram(expression_document(binary('and',literal(True),literal(False))),
                   rule_id='limit',structure_limits=StructureLimits(2,9))
    assert e.value.code=='SRV111' and e.value.exit_code==3
    assert e.value.metric=='ast_nodes' and e.value.observed==3 and e.value.limit==2
    assert e.value.pointer=='/expression/args/1'


def test_exact_depth_boundary_passes():
    result=observed({'op':'not','arg':literal(True)},limits={'srx_depth':2})
    assert result.value is False and result.usage.structure.ast_depth==2


def test_depth_boundary_is_hard_even_with_large_work_targets():
    with pytest.raises(SrxStructureError) as e:
        observed({'op':'not','arg':literal(True)},limits={'srx_depth':1,'srx_operations':10**12})
    assert e.value.reason=='ast_depth_exceeded' and e.value.pointer=='/expression/arg'


def test_skipped_runtime_branch_is_still_structurally_bounded():
    node=binary('or',literal(True),{'op':'not','arg':literal(False)})
    with pytest.raises(SrxStructureError):observed(node,limits={'srx_depth':2})


def test_structural_failure_occurs_before_program_snapshot_copy():
    with patch('specroad.srx.program.JsonSnapshot',side_effect=AssertionError('copied unsafe AST')):
        with pytest.raises(SrxStructureError):
            SrxProgram(expression_document(binary('eq',literal(1),literal(1))),
                       rule_id='r',structure_limits=StructureLimits(1,1))


def test_project_recheck_occurs_before_operator_execution():
    program=SrxProgram(expression_document(binary('eq',literal(1),literal(1))),rule_id='r')
    data=roots();data['project']['resource_limits']={'srx_nodes':2}
    context=EvaluationContext(data,rule_id='r')
    with patch('specroad.srx.evaluation.evaluate_expression',side_effect=AssertionError('executed')):
        with pytest.raises(SrxStructureError):evaluate(program,context)


def test_program_can_be_reused_with_distinct_project_limits():
    program=SrxProgram(expression_document(binary('eq',literal(1),literal(1))),rule_id='r')
    for n in (3,2,3):
        data=roots();data['project']['resource_limits']={'srx_nodes':n}
        context=EvaluationContext(data,rule_id='r')
        if n==2:
            with pytest.raises(SrxStructureError):evaluate(program,context)
        else:assert evaluate(program,context) is True


def test_shared_occurrences_are_counted_separately():
    item=literal(True)
    program=SrxProgram(expression_document({'op':'and','args':[item,item,item]}),rule_id='r')
    assert program.structure.ast_nodes==4
    assert evaluate(program,EvaluationContext(roots(),rule_id='r')) is True


def test_cyclic_ast_is_rejected_without_looping():
    node={'op':'not'};node['arg']=node
    with pytest.raises(SrxError) as e:SrxProgram(expression_document(node),rule_id='r')
    assert e.value.reason=='cyclic_json_value'


def test_soft_operation_target_is_not_an_error_or_truncation():
    result=observed(binary('add',literal(0.1),literal(0.2)),limits={'srx_operations':1})
    assert result.value==0.3
    assert result.usage.data['work_counts']['evaluation_steps']==3
    assert result.usage.data['soft_budget_exceeded'] is True
    assert result.usage.policy.work.evaluation_steps==1


def test_exact_work_target_is_not_exceeded():
    result=observed(binary('eq',literal(1),literal(1)),limits={'srx_operations':3})
    assert result.value is True and result.usage.data['soft_budget_exceeded'] is False


def test_empty_quantifier_has_no_item_iterations():
    result=observed(quantifier('all',literal([]),literal(True)),limits={'srx_iterations':1})
    assert result.value is True and result.usage.iterations==0 and result.usage.evaluation_steps==2


def test_large_array_completes_beyond_iteration_target():
    result=observed(quantifier('all',field('/items'),binary('gte',field('',context='item'),literal(0))),
        artifact={'items':list(range(2049))},limits={'srx_iterations':1,'srx_operations':2})
    assert result.value is True and result.usage.iterations==2049
    assert result.usage.evaluation_steps==2+2049*3
    assert result.usage.data['exceeded_targets']==['evaluation_steps','iterations']


def test_nested_quantifier_iterations_share_only_one_evaluation_meter():
    result=observed(quantifier('all',literal([[True,True]]*3),
        quantifier('all',field('',context='item'),field('',context='item'))))
    assert result.value is True and result.usage.iterations==9


def test_short_circuit_does_not_count_skipped_runtime_work():
    node=binary('or',literal(True),binary('divide',literal(1),literal(0)))
    result=observed(node,limits={'srx_operations':2})
    assert result.value is True and result.usage.evaluation_steps==2
    assert result.usage.structure.ast_nodes==5 and not result.usage.data['soft_budget_exceeded']


def test_graph_observation_does_not_filter_results_to_budget():
    values=chain()
    result=observed(reach(aid(number=3),depth=2),artifact=values[0],graph=graph(values),limits={'srx_graph_steps':1})
    assert result.value is True and result.usage.graph_steps>1
    assert 'graph_steps' in result.usage.data['exceeded_targets']


def test_filter_misses_still_account_for_graph_reads():
    values=chain()
    result=observed(count(['refines']),artifact=values[0],graph=graph(values))
    assert result.value==0 and result.usage.graph_steps==1


def test_reachable_depth_remains_semantic_not_a_work_target():
    values=chain()
    result=observed(reach(aid(number=3),depth=1),artifact=values[0],graph=graph(values),limits={'srx_graph_steps':1})
    assert result.value is False and result.usage.data['soft_budget_exceeded'] is True


def test_value_only_api_retains_missing_and_null():
    context=EvaluationContext(roots(),rule_id='r')
    assert evaluate(SrxProgram(expression_document(field('/absent')),rule_id='r'),context) is MISSING
    result=observed(field('/absent'))
    assert result.value is MISSING and result.usage.data['evaluation_completed'] is True
    assert observed(literal(None)).value is None


def test_observations_are_owned_and_immutable():
    result=observed(literal({'x':[1]}))
    result.value['x'].append(2)
    result.usage.data['work_counts']['evaluation_steps']=999
    with pytest.raises(FrozenInstanceError):result.usage.iterations=10
    assert result.value=={'x':[1]} and result.usage.evaluation_steps==1


def test_no_checkpoint_or_resume_claim_after_soft_exceedance():
    report=observed(binary('eq',literal(1),literal(1)),limits={'srx_operations':1}).usage.data
    assert report['evaluation_completed'] is True and report['continuation']=='in_process'
    assert report['checkpoint'] is None and report['resume_available'] is False
    json.dumps(report,allow_nan=False)


def test_counters_are_fresh_for_repeated_and_concurrent_calls():
    program=SrxProgram(expression_document(quantifier('all',literal([True]*7),field('',context='item'))),rule_id='r')
    context=EvaluationContext(roots(),rule_id='r')
    with ThreadPoolExecutor(max_workers=2) as pool:
        reports=list(pool.map(lambda _:evaluate_with_usage(program,context).usage.data,range(12)))
    assert all(x==reports[0] for x in reports) and reports[0]['work_counts']['iterations']==7


def test_raw_program_uses_same_structural_limit():
    raw=json.dumps(expression_document(binary('eq',literal(1),literal(1)))).encode()
    with pytest.raises(SrxStructureError):parse_program(raw,rule_id='r',structure_limits=StructureLimits(2,3))
    program=parse_program(raw,rule_id='r',structure_limits=StructureLimits(3,2))
    assert program.source_bytes==raw and program.structure.ast_nodes==3


def test_semantic_configuration_excludes_only_soft_srx_targets():
    original=semantic_configuration(ProjectConfiguration(configuration_value()))
    soft=semantic_configuration(ProjectConfiguration(configuration_value(resource_limits={
        'srx_operations':1,'srx_iterations':1,'srx_graph_steps':1})))
    hard=semantic_configuration(ProjectConfiguration(configuration_value(resource_limits={'srx_nodes':4,'srx_depth':2})))
    assert soft==original and hard!=original
