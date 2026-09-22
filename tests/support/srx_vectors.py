"""Test-only runner for versioned SRX value/error vectors, never console goldens."""
import copy
import json
import math
from pathlib import Path

from specroad.graph.relations import SourceRelations
from specroad.srx import (EvaluationContext, LoadedGraph, MISSING, SrxError,
                          SrxProgram, evaluate, parse_program)
from support.artifacts import artifact_bytes

CORPUS_PATH = Path(__file__).resolve().parents[1] / 'fixtures/srx_conformance_v1.json'


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate corpus key')
        result[key] = value
    return result


def _constant(value):
    raise ValueError('Nonfinite corpus constant')


def validate_corpus(value):
    """Reject malformed expectations rather than silently omitting test cases."""
    _require_json(value)
    if (type(value) is not dict or set(value) != {'format_version', 'language', 'language_version', 'corpus_revision', 'cases'}
            or type(value['format_version']) is not int or value['format_version'] != 1
            or value['language'] != 'srx' or value['language_version'] != '1.0'
            or type(value['corpus_revision']) is not int or value['corpus_revision'] != 1
            or type(value['cases']) is not list or not value['cases']):
        raise ValueError('Unsupported or empty SRX conformance corpus')
    seen = set()
    for case in value['cases']:
        required = {'id', 'operator', 'category', 'context', 'expect'}
        allowed = required | {'program', 'program_utf8', 'graph'}
        if type(case) is not dict or not required <= case.keys() or set(case) - allowed:
            raise ValueError('Invalid corpus case fields')
        if case['category'] not in ('positive','negative','boundary','error','annex_u','regression'):
            raise ValueError('Unknown corpus category')
        if type(case['context']) is not dict:
            raise ValueError('Explicit JSON context object required')
        if 'program_utf8' in case and type(case['program_utf8']) is not str:
            raise ValueError('Raw program must be explicit text, never a path to open')
        if 'program' in case and type(case['program']) is not dict:
            raise ValueError('Object program must be an object')
        if 'graph' in case and type(case['graph']) is not list:
            raise ValueError('Graph must be explicit source data')
        if ('program' in case) == ('program_utf8' in case):
            raise ValueError('Exactly one program input is required')
        if any(type(case[k]) is not str or not case[k] for k in ('id', 'operator', 'category')):
            raise ValueError('Case identity and category required')
        if case['id'] in seen:
            raise ValueError('Duplicate corpus identity')
        seen.add(case['id'])
        expected = case['expect']
        if type(expected) is not dict:
            raise ValueError('Expectation required')
        kind = expected.get('kind')
        if kind == 'value' and set(expected) == {'kind','value'}:
            continue
        if kind == 'missing' and set(expected) == {'kind'}:
            continue
        names = {'kind','code','reason','input_pointer','expression_pointer'}
        optional = {'expected_type','actual_type','subject','repair_action'}
        if kind != 'error' or not names <= expected.keys() or set(expected) - names - optional:
            raise ValueError('Closed value/missing/error expectation required')
        if any(type(expected[k]) is not str for k in expected):
            raise ValueError('Diagnostic expectations must be strings')
    return copy.deepcopy(value)


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


def assert_json_equal(actual, expected):
    """Independent structural oracle; Python's True == 1 is NOT JSON equality."""
    pairs = [(actual, expected)]
    while pairs:
        a, b = pairs.pop()
        numeric = type(a) in (int,float) and type(b) in (int,float)
        assert numeric or type(a) is type(b), (type(a).__name__,type(b).__name__)
        if type(a) is dict:
            assert set(a) == set(b)
            pairs.extend((a[k], b[k]) for k in a)
        elif type(a) is list:
            assert len(a) == len(b)
            pairs.extend(zip(a,b))
        else:
            assert a == b, (a,b)


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


def _require_json(value):
    """The corpus is passive built-in JSON; reject hooks and cycles before copying."""
    active = set()
    stack = [(False, value)]
    while stack:
        leaving, value = stack.pop()
        if leaving:
            active.remove(id(value)); continue
        kind = type(value)
        if kind in (dict, list):
            if id(value) in active:
                raise ValueError('Cyclic corpus data')
            active.add(id(value)); stack.append((True,value))
            if kind is dict:
                if any(type(k) is not str for k in value):
                    raise ValueError('Corpus object keys must be strings')
                for k in value: k.encode('utf-8')
                values = value.values()
            else:
                values = value
            stack.extend((False,v) for v in values)
        elif kind is str:
            value.encode('utf-8')
        elif kind is float:
            if not math.isfinite(value): raise ValueError('Nonfinite corpus number')
        elif value is not None and kind not in (bool,int):
            raise ValueError('Foreign corpus value')


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
