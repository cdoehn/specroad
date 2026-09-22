"""Test-only runner for versioned SRX value/error vectors, never console goldens."""
import copy
import json
from pathlib import Path

from specroad.graph.relations import SourceRelations
from specroad.srx import (EvaluationContext, LoadedGraph, MISSING, SrxError,
                          SrxProgram, evaluate, parse_program)
from support.artifacts import artifact_bytes

from .srx_vector_contract import (_object, _constant, validate_corpus, assert_json_equal)

CORPUS_PATH = Path(__file__).resolve().parents[1] / 'fixtures/srx_conformance_v1.json'


def load_corpus():
    return validate_corpus(json.loads(CORPUS_PATH.read_bytes(), object_pairs_hook=_object, parse_constant=_constant))


def observe_case(case):
    """Call actual public parser/context/evaluator APIs; unexpected exceptions escape."""
    data = copy.deepcopy(case)
    rule_id = case['id']
    try:
        graph = None
        if 'graph' in data:
            graph = LoadedGraph(tuple(SourceRelations(artifact_bytes(v)) for v in data['graph']), rule_id=rule_id)
        context = EvaluationContext(data['context'], rule_id=rule_id, graph=graph)
        program = (parse_program(data['program_utf8'].encode('utf-8'), rule_id=rule_id)
                   if 'program_utf8' in data else SrxProgram(data['program'], rule_id=rule_id))
        value = evaluate(program, context)
        return {'kind':'missing'} if value is MISSING else {'kind':'value','value':value}
    except SrxError as error:
        return {'kind':'error', **error.diagnostic()}


def assert_case(case):
    actual = observe_case(case)
    expected = case['expect']
    assert actual['kind'] == expected['kind'], (case['id'],actual,expected)
    if expected['kind'] == 'error':
        for name,value in expected.items():
            assert actual[name] == value, (case['id'],name,actual[name],value)
        assert actual['rule_id'] == case['id']
        assert actual['diagnostic_version'] == 1
        assert type(actual['repair_action']) is str and actual['repair_action']
        assert type(actual['recommendation']) is str and actual['recommendation']
        assert all(type(actual[k]) is str and actual[k] for k in ('expected_type','actual_type'))
    else:
        assert_json_equal(actual,expected)
    return actual


def semantic_observation(value):
    """Exclude the human recommendation from structured regression comparisons."""
    return {k:v for k,v in value.items() if k != 'recommendation'}


def numeric_case(vector, number=0):
    """Adapt the existing Annex U numeric fixture into the same execution contract."""
    from .srx import roots, binary, literal, expression_document
    context = roots()
    context['project']['srx_policy'] = {'decimal_precision':vector['precision']}
    expected = ({'kind':'error','code':'SRV197','reason':vector['error'],
                 'input_pointer':'/expression','expression_pointer':'/expression'}
                if 'error' in vector else {'kind':'value','value':vector['value']})
    return {'id':'SRX1-numeric-'+str(number),'operator':vector['op'],'category':'annex_u',
            'program':expression_document(binary(vector['op'],literal(vector['left']),literal(vector['right']))),
            'context':context,'expect':expected}
