"""14.h.R value, inverse mapping, source retention and safety boundaries."""
from copy import deepcopy
from dataclasses import fields, replace
from decimal import localcontext, Inexact, Rounded, Overflow, Underflow
from hashlib import sha256
import json
from unittest.mock import patch

import pytest

from specroad.exchange import ReqIFDocument, ReqIFError, ReqIFLimits, decode_reqif, encode_reqif
from specroad.mappings import ExchangeMapping, MappingError
from support.artifacts import artifact_bytes
from support.exchange_mappings import mapping_value
from support.read_only import no_write_attempts
from support.reqif_objects import LIMITS, TIME, NAMESPACE, document, datatype, definition, spec_object, one, value


def read(raw):
    return decode_reqif(raw, limits=LIMITS)


def resource(value_map=None, *, field='field'):
    return ExchangeMapping(artifact_bytes(mapping_value(
        types=[{'external_type':'type', 'artifact_type':'requirement'}],
        fields=[{'external_type':'type', 'external_field':field, 'target_field':'statement', 'value_map':value_map}],
        relations=[], hierarchies=[])))


def binding(doc, mapping):
    return dict(mappings=[mapping], key=mapping.key, expected_mapping_sha256=mapping.sha256,
                expected_source_sha256=doc.source_sha256, source_system='supplier', source_document='document')


def export(doc, field, mapping=None, **changes):
    mapping = resource() if mapping is None else mapping
    args = binding(doc, mapping)
    args.update(changes)
    return doc.export_object('object', {'artifact_type':'requirement', 'statement':field}, **args)


def raw_with_bounds(family, literal, bounds):
    return document(datatypes=datatype(family, bounds=bounds), definitions=definition(family, 'field', 'dt'),
                    objects=spec_object(value(family, 'field', literal)))


@pytest.mark.parametrize('family,literal,bounds,expected', [
    ('INTEGER','-3',' MIN="-3" MAX="3"',-3), ('INTEGER','+003',' MIN="-3" MAX="3"',3),
    ('INTEGER','100000000000000000000',' MIN="0" MAX="100000000000000000000"',10**20),
    ('REAL','0.1',' MIN="0.1" MAX="0.1" ACCURACY="17"',0.1),
    ('REAL','-0.125',' MIN="-0.125" MAX="0" ACCURACY="17"',-0.125),
    ('REAL','5e-324',' MIN="0" MAX="1" ACCURACY="17"',5e-324),
    ('REAL','1.7976931348623157e308',' MIN="0" MAX="INF" ACCURACY="17"',1.7976931348623157e308),
    ('STRING','',' MAX-LENGTH="0"',''), ('STRING','e\u0301😀',' MAX-LENGTH="3"','e\u0301😀'),
])
def test_exact_type_boundaries_and_native_values(family,literal,bounds,expected):
    doc=read(raw_with_bounds(family,literal,bounds))
    assert doc.project_object('object')['fields']=={'field':expected}
    assert read(encode_reqif(doc)).objects[0].values[0].lexical==literal


@pytest.mark.parametrize('family,literal,bounds', [
    ('INTEGER','-4',' MIN="-3" MAX="3"'), ('INTEGER','4',' MIN="-3" MAX="3"'),
    ('REAL','0.0999999999999999999999999',' MIN="0.1" MAX="1" ACCURACY="17"'),
    ('REAL','-0.100000000000000000000001',' MIN="-0.1" MAX="1" ACCURACY="17"'),
    ('REAL','INF',' MIN="0" MAX="1" ACCURACY="17"'),
    ('REAL','-INF',' MIN="0" MAX="INF" ACCURACY="17"'),
    ('STRING','e\u0301😀',' MAX-LENGTH="2"'),
])
def test_type_bounds_compare_exact_values_without_rounding(family,literal,bounds):
    with pytest.raises(ReqIFError) as caught:read(raw_with_bounds(family,literal,bounds))
    assert caught.value.exit_code==3
    assert caught.value.object_id=='object' and caught.value.definition_id=='field'


@pytest.mark.parametrize('family,bounds', [
    ('INTEGER',' MIN="2" MAX="1"'), ('INTEGER',' MIN="NaN" MAX="1"'),
    ('INTEGER',' MIN="1.0" MAX="2"'), ('INTEGER',' MIN="0"'),
    ('REAL',' MIN="NaN" MAX="1" ACCURACY="17"'), ('REAL',' MIN="0" MAX="NaN" ACCURACY="17"'),
    ('REAL',' MIN="INF" MAX="-INF" ACCURACY="17"'),
    ('REAL',' MIN="0" MAX="1" ACCURACY="-1"'), ('REAL',' MIN="0" MAX="1" ACCURACY="1.5"'),
    ('STRING',' MAX-LENGTH="-1"'), ('STRING',' MAX-LENGTH="1e2"'), ('STRING',''),
])
def test_invalid_datatype_metadata_is_rejected_even_without_objects(family,bounds):
    with pytest.raises(ReqIFError) as caught:read(document(datatypes=datatype(family,bounds=bounds)))
    assert caught.value.exit_code==3 and caught.value.pointer


@pytest.mark.parametrize('literal', ['1e99999999999999999999999999999','1e-99999999999999999999999999999',
    '9007199254740993','1.0000000000000001','-0','-0e100','NaN','INF','-INF'])
def test_valid_real_lexemes_outside_native_numbers_are_not_lost(literal):
    doc=read(one('REAL',literal))
    result=doc.project_object('object')
    assert result['fields']=={} and not result['representable']
    assert result['unrepresentable'][0]['object_id']=='object'
    assert result['unrepresentable'][0]['definition_id']=='field'
    assert read(encode_reqif(doc)).objects[0].values[0].lexical==literal


@pytest.mark.parametrize('sign', ['', '-'])
def test_very_large_integer_lexemes_and_type_limits_have_no_python_digit_conversion(sign):
    literal=sign+'9'*5000
    raw=raw_with_bounds('INTEGER',literal,' MIN="-'+'9'*5000+'" MAX="'+'9'*5000+'"')
    doc=read(raw)
    assert doc.objects[0].values[0].lexical==literal
    assert not doc.project_object('object')['representable']
    assert read(encode_reqif(doc)).objects[0].values[0].lexical==literal


@pytest.mark.parametrize('minimum,maximum,literal,accepted', [
    ('1e999999999999999999999','10e999999999999999999999','2e999999999999999999999',True),
    ('1e999999999999999999999','10e999999999999999999999','1e1000000000000000000001',False),
    ('1e-1000000000000000000000','1e-999999999999999999999','10e-1000000000000000000000',True),
    ('1e-1000000000000000000000','1e-999999999999999999999','.1e-1000000000000000000000',False),
    ('-10e999999999999999999999','-1e999999999999999999999','-2e999999999999999999999',True),
    ('-10e999999999999999999999','-1e999999999999999999999','-11e999999999999999999999',False),
])
def test_extreme_exponent_range_comparison(minimum,maximum,literal,accepted):
    raw=raw_with_bounds('REAL',literal,f' MIN="{minimum}" MAX="{maximum}" ACCURACY="17"')
    if accepted:assert read(raw).objects[0].values[0].lexical==literal
    else:
        with pytest.raises(ReqIFError) as caught:read(raw)
        assert caught.value.reason=='reqif_value_out_of_range'


def test_decimal_process_context_does_not_round_values_or_bounds():
    raw=one('REAL','1.250000000000000000000000')
    with localcontext() as ctx:
        ctx.prec=1;ctx.Emax=1;ctx.Emin=-1
        for trap in (Inexact,Rounded,Overflow,Underflow):ctx.traps[trap]=True
        doc=read(raw)
        assert doc.project_object('object')['fields']=={'field':1.25}
        assert read(export(doc,125.5)['xml_bytes']).project_object('object')['fields']=={'field':125.5}


@pytest.mark.parametrize('literal', ['2000-02-29T00:00:00Z','1900-02-28T24:00:00.000-14:00',
    '-0004-02-29T00:00:00','12000-02-29T01:02:03.123456789012345+00:00',
    '2024-01-01T00:00:00-00:00','2024-01-01T00:00:00+13:59',' \t2024-01-01T00:00:00Z\n'])
def test_datetime_retains_fraction_zone_absence_and_lexical_whitespace(literal):
    doc=read(one('DATE',literal))
    assert doc.project_object('object')['fields']=={'field':literal}
    assert read(encode_reqif(doc)).objects[0].values[0].lexical==literal


@pytest.mark.parametrize('literal', ['0000-01-01T00:00:00Z','02024-01-01T00:00:00Z','1900-02-29T00:00:00Z',
    '2024-13-01T00:00:00Z','2024-00-01T00:00:00Z','2024-01-00T00:00:00Z','2024-04-31T00:00:00Z',
    '2024-01-01T25:00:00Z','2024-01-01T24:00:00.1Z','2024-01-01T24:00:01Z',
    '2024-01-01T23:60:00Z','2024-01-01T23:59:60Z','2024-01-01T00:00:00+14:01',
    '2024-01-01T00:00:00+15:00','2024-01-01T00:00:00+00:60','2024-01-01 00:00:00Z',
    '2024-01-01T00:00:00z','\u00a02024-01-01T00:00:00Z'])
def test_invalid_datetime_is_localized(literal):
    with pytest.raises(ReqIFError) as caught:read(one('DATE',literal))
    assert caught.value.reason=='reqif_invalid_datetime'
    assert caught.value.object_id=='object' and caught.value.definition_id=='field'


def test_date_year_larger_than_host_integer_string_limit_is_transportable():
    literal='1'+'0'*5000+'-02-29T00:00:00Z'
    doc=read(one('DATE',literal))
    assert read(encode_reqif(doc)).project_object('object')['fields']['field']==literal


@pytest.mark.parametrize('family,literal', [('BOOLEAN','\u00a0true'),('INTEGER','1\u00a0'),('REAL','\u20031'),
    ('REAL','+INF'),('REAL','nan'),('REAL','1_000'),('INTEGER','١'),('BOOLEAN','TRUE')])
def test_non_xml_whitespace_and_wrong_numeric_or_boolean_grammar(family,literal):
    with pytest.raises(ReqIFError) as caught:read(one(family,literal))
    assert caught.value.exit_code==3


@pytest.mark.parametrize('family,default,expected', [('BOOLEAN','false',False),('INTEGER','0',0),('REAL','.25',.25),
    ('STRING','\r\n\t<&😀','\r\n\t<&😀'),('DATE','2024-02-29T00:00:00','2024-02-29T00:00:00'),
    ('ENUMERATION',[],[]),('ENUMERATION',['enum_b','enum_a'],['enum_a','enum_b'])])
def test_all_default_types_preserve_absence_and_explicit_origin(family,default,expected):
    doc=read(one(family,None,default=default))
    assert doc.project_object('object')['fields']=={'field':expected}
    assert doc.project_object('object')['origins']=={'field':'default'}
    assert read(encode_reqif(doc)).objects[0].values==()


@pytest.mark.parametrize('family,default', [('BOOLEAN','no'),('INTEGER','1.2'),('REAL','foo'),
    ('STRING','a'*4097),('DATE','2023-02-29T00:00:00Z'),('ENUMERATION',['missing']),('ENUMERATION',['enum_a','enum_a'])])
def test_invalid_defaults_are_checked_even_without_an_object_value(family,default):
    with pytest.raises(ReqIFError) as caught:read(one(family,None,default=default))
    assert caught.value.exit_code==3 and caught.value.definition_id=='field'


@pytest.mark.parametrize('identifier', ['header','type','field','dt','object'])
def test_later_reqif_objects_cannot_hide_duplicate_ids(identifier):
    addition=f'<SPECIFICATIONS><SPECIFICATION IDENTIFIER="{identifier}" LAST-CHANGE="{TIME}"/></SPECIFICATIONS>'
    raw=one().replace(b'</REQ-IF-CONTENT>',addition.encode()+b'</REQ-IF-CONTENT>')
    with pytest.raises(ReqIFError) as caught:read(raw)
    assert caught.value.reason=='reqif_invalid_or_duplicate_identifier'


@pytest.mark.parametrize('kind',['extension','hierarchy','xhtml','attribute','container-text','enum-reference-attribute'])
def test_uninterpreted_source_is_retained_and_blocks_complete_serialization(kind):
    raw=one()
    if kind=='extension':raw=raw.replace(b'</REQ-IF>',b'<TOOL-EXTENSIONS><REQ-IF-TOOL-EXTENSION><x xmlns="urn:owned" IDENTIFIER="object">keep</x></REQ-IF-TOOL-EXTENSION></TOOL-EXTENSIONS></REQ-IF>')
    if kind=='hierarchy':raw=raw.replace(b'</REQ-IF-CONTENT>',f'<SPECIFICATIONS><SPECIFICATION IDENTIFIER="spec" LAST-CHANGE="{TIME}"><CHILDREN><SPEC-HIERARCHY IDENTIFIER="hier" LAST-CHANGE="{TIME}"/></CHILDREN></SPECIFICATION></SPECIFICATIONS></REQ-IF-CONTENT>'.encode())
    if kind=='xhtml':
        raw=one('XHTML','').replace(b' THE-VALUE=""',b'').replace(b'</ATTRIBUTE-VALUE-XHTML>',b'<THE-VALUE><x:div xmlns:x="http://www.w3.org/1999/xhtml">rich <x:b>text</x:b></x:div></THE-VALUE></ATTRIBUTE-VALUE-XHTML>')
    if kind=='attribute':raw=raw.replace(b'xml:lang="de"',b'xml:lang="de" z="keep" a="also keep"')
    if kind=='container-text':raw=raw.replace(b'</REQ-IF-CONTENT>',b'<SPECIFICATIONS>keep</SPECIFICATIONS></REQ-IF-CONTENT>')
    if kind=='enum-reference-attribute':raw=one('ENUMERATION',['enum_a']).replace(b'<ENUM-VALUE-REF>',b'<ENUM-VALUE-REF note="keep">')
    doc=read(raw)
    assert doc.source_bytes==raw and doc.source_sha256==sha256(raw).hexdigest()
    assert doc.observation()['uninterpreted'] and doc.observation()['import_complete'] is False
    with pytest.raises(ReqIFError) as caught:encode_reqif(doc)
    assert caught.value.reason=='reqif_uninterpreted_export'
    with pytest.raises(ReqIFError):export(doc,'new')
    if kind=='attribute':assert doc.unsupported[0][0].endswith('/@a') and doc.unsupported[1][0].endswith('/@z')
    if kind=='xhtml':assert not doc.project_object('object')['representable']


@pytest.mark.parametrize('injection', [
    '<x xmlns="http://www.w3.org/2001/XInclude" href="file:///never"/>',
    '<x xmlns="http://www.w3.org/2001/XMLSchema"/>',
    '<x xmlns:s="http://www.w3.org/2001/XMLSchema-instance" s:schemaLocation="urn:x https://never.invalid/schema"/>',
    '<x xmlns:s="http://www.w3.org/2001/XMLSchema-instance" s:noNamespaceSchemaLocation="file:///never"/>',
    '<?request file:///never?>',
])
def test_unknown_subtrees_do_not_bypass_xml_safety(injection):
    raw=document(extensions='<TOOL-EXTENSIONS><REQ-IF-TOOL-EXTENSION>'+injection+'</REQ-IF-TOOL-EXTENSION></TOOL-EXTENSIONS>')
    with no_write_attempts(),patch('socket.socket',side_effect=AssertionError('network')),pytest.raises(ReqIFError) as caught:read(raw)
    assert caught.value.exit_code==7 and caught.value.position is not None
    assert 'file:///never' not in json.dumps(caught.value.diagnostic())


@pytest.mark.parametrize('family,literal,native', [('BOOLEAN','true',False),('INTEGER','1',10**20),('REAL','1.5',2.25),
    ('STRING','before','after\r\n\t<&😀'),('DATE','2024-01-01T00:00:00Z','2024-02-29T12:00:00.123-14:00'),
    ('ENUMERATION',['enum_a'],['enum_a','enum_b'])])
def test_inverse_mapping_writes_only_the_bound_object_and_keeps_source(family,literal,native):
    raw=one(family,literal)
    if family=='INTEGER':raw=raw.replace(b'MAX="10000000000000000"',b'MAX="100000000000000000000"')
    doc=read(raw); mapping=resource();original=doc.project_object('object')
    with no_write_attempts():result=export(doc,native,mapping)
    after=read(result['xml_bytes'])
    assert after.project_object('object')['fields']=={'field':native}
    assert after.map_object('object',**binding(after,mapping))['artifact']['statement']==native
    assert doc.project_object('object')==original and doc.source_bytes==raw
    assert after.objects[0].identifier==doc.objects[0].identifier
    assert after.objects[0].element.attributes==doc.objects[0].element.attributes
    assert result['source_sha256']==doc.source_sha256 and result['external_identity']['external_id']=='object'
    assert result['export_complete'] is result['write_authorized'] is result['execution_ready'] is False
    assert result['xml_bytes']==export(doc,native,mapping)['xml_bytes']


@pytest.mark.parametrize('family,literal,default,native', [
    ('REAL','1.2500',None,1.25),('BOOLEAN','0',None,False),('STRING',None,'default','default'),
    ('ENUMERATION',['enum_b','enum_a'],None,['enum_a','enum_b']),('ENUMERATION',None,[],[]),
])
def test_unchanged_inverse_fields_preserve_original_lexemes_order_and_absence(family,literal,default,native):
    doc=read(one(family,literal,default=default))
    result=export(doc,native)
    assert result['xml_bytes']==encode_reqif(doc)
    assert read(result['xml_bytes']).project_object('object')==doc.project_object('object')


def test_inverse_explicit_edit_does_not_change_definition_default_or_other_objects():
    raw=one(literal=None,default='default').replace(b'</SPEC-OBJECTS>',spec_object(value('STRING','field','other'),identifier='second').encode()+b'</SPEC-OBJECTS>')
    doc=read(raw)
    after=read(export(doc,'changed')['xml_bytes'])
    assert after.project_object('object')['origins']=={'field':'explicit'}
    assert after.project_object('second')==doc.project_object('second')
    assert after.types[0].definitions[0].default.lexical=='default'


@pytest.mark.parametrize('target,expected', [('first',['enum_a']),('second',['enum_b']),('none',[])])
def test_explicit_inverse_enum_value_map(target,expected):
    doc=read(one('ENUMERATION',['enum_a']))
    mapping=resource([{'external_value':['enum_a'],'target_value':'first'},
        {'external_value':['enum_b'],'target_value':'second'},{'external_value':[],'target_value':'none'}])
    after=read(export(doc,target,mapping)['xml_bytes'])
    assert after.project_object('object')['fields']=={'field':expected}
    assert after.map_object('object',**binding(after,mapping))['artifact']['statement']==target


@pytest.mark.parametrize('table,target,reason', [
    ([{'external_value':'a','target_value':1},{'external_value':'b','target_value':1}],1,'reqif_inverse_mapping_ambiguous'),
    ([{'external_value':'a','target_value':'x'}],'missing','reqif_inverse_value_unmapped'),
])
def test_inverse_mapping_never_selects_first_match_or_defaults(table,target,reason):
    doc=read(one(default='fallback')); before=doc.source_bytes
    with pytest.raises(ReqIFError) as caught:export(doc,target,resource(table))
    assert caught.value.reason==reason and caught.value.exit_code==6
    assert caught.value.definition_id=='field' and caught.value.object_id=='object'
    assert doc.source_bytes==before


@pytest.mark.parametrize('family,native', [('BOOLEAN',1),('INTEGER',True),('INTEGER',1.5),('STRING',None),
    ('STRING',1),('REAL','1.5'),('DATE','yesterday'),('ENUMERATION','enum_a'),
    ('ENUMERATION',['missing']),('ENUMERATION',['enum_a','enum_a']),('ENUMERATION',['enum_b','enum_a']),
    ('STRING','\x00'),('REAL',float('inf')),('REAL',float('nan'))])
def test_invalid_or_noninvertible_native_values_cannot_be_silently_exported(family,native):
    literal={'BOOLEAN':'true','INTEGER':'1','REAL':'1','STRING':'text','DATE':'2024-01-01T00:00:00Z','ENUMERATION':['enum_a']}[family]
    doc=read(one(family,literal))
    with no_write_attempts(),pytest.raises(ReqIFError) as caught:export(doc,native)
    assert caught.value.exit_code==6


@pytest.mark.parametrize('case',['source','mapping','type','missing','names','format'])
def test_inverse_bindings_and_required_fields_are_explicit(case):
    doc=read(one());mapping=resource();args=binding(doc,mapping)
    native={'artifact_type':'requirement','statement':'text'}
    if case=='source':args['expected_source_sha256']='0'*64
    if case=='mapping':args['expected_mapping_sha256']='0'*64
    if case=='type':native['artifact_type']='task'
    if case=='missing':del native['statement']
    if case=='names':mapping=resource(field='same display name');args=binding(doc,mapping)
    if case=='format':
        data=mapping.data;data['source_format']='csv';mapping=ExchangeMapping(artifact_bytes(data));args=binding(doc,mapping)
    with pytest.raises((ReqIFError,MappingError)) as caught:doc.export_object('object',native,**args)
    if case in ('source','type'):assert caught.value.exit_code==6
    if case in ('mapping','missing'):assert type(caught.value) is MappingError and caught.value.exit_code==3
    if case=='format':assert caught.value.exit_code==2


@pytest.mark.parametrize('key,value',[('source_system',''),('source_document',None),('external_revision',12)])
@pytest.mark.parametrize('direction',['import','export'])
def test_invalid_call_context_has_configuration_error(key,value,direction):
    doc=read(one());mapping=resource();args={**binding(doc,mapping),key:value}
    with pytest.raises(ReqIFError) as caught:
        if direction=='import':doc.map_object('object',**args)
        else:doc.export_object('object',{'artifact_type':'requirement','statement':'text'},**args)
    assert caught.value.exit_code==2


def test_distinct_source_context_is_explicit_and_observations_do_not_mutate_inputs():
    doc=read(one());mapping=resource();args=binding(doc,mapping)
    a=doc.map_object('object',**args)
    b=doc.map_object('object',**{**args,'source_document':'another explicit document'})
    assert a['fields']==b['fields'] and a['external_identity']!=b['external_identity']
    native={'artifact_type':'requirement','statement':'changed','extra':{'nested':[1]}}
    before=deepcopy(native)
    result=doc.export_object('object',native,**args)
    assert result['unmapped']=={'extra':{'nested':[1]}}
    result['unmapped']['extra']['nested'].append(2)
    assert native==before
    with pytest.raises(AttributeError):doc.__init__(one(literal='replacement'),limits=LIMITS)
    assert doc.source_bytes==one()


@pytest.mark.parametrize('exception',[MemoryError,RecursionError])
@pytest.mark.parametrize('stage',['read','projection','serialize'])
def test_resource_failures_remain_real_exceptions(exception,stage):
    doc=read(one('REAL','1'))
    target={'read':'read_bounded_xml','projection':'number_from_token','serialize':'_serialize'}[stage]
    with patch('specroad.exchange.reqif.'+target,side_effect=exception('host')):
        with pytest.raises(exception):
            if stage=='read':read(one())
            elif stage=='projection':doc.project_object('object')
            else:export(doc,2)


@pytest.mark.parametrize('bound',[f.name for f in fields(ReqIFLimits)])
@pytest.mark.parametrize('bad',[0,-1,True,1.5,'1',None])
def test_invalid_limits_are_not_coerced(bound,bad):
    with pytest.raises(ReqIFError) as caught:replace(LIMITS,**{bound:bad})
    assert caught.value.exit_code==2


def test_many_objects_are_fully_checked_before_projection_and_tail_errors():
    body=''.join(spec_object(value('STRING','field',str(i)),identifier='o'+str(i)) for i in range(2500))
    raw=document(datatypes=datatype('STRING'),definitions=definition('STRING','field','dt'),objects=body)
    doc=read(raw)
    assert len(doc.objects)==2500 and doc.project_object('o2499')['fields']=={'field':'2499'}
    bad=raw.replace(b'IDENTIFIER="o2499"',b'IDENTIFIER="o0"')
    with pytest.raises(ReqIFError):read(bad)
    assert read(encode_reqif(doc)).project_object('o2499')['fields']=={'field':'2499'}


def test_namespace_prefixes_and_entity_escapes_have_identical_deterministic_output():
    raw=one(literal='a<&\r\n\t😀')
    # Prefix every ReqIF element, keeping attribute namespaces separate.
    import re
    prefixed=re.sub(rb'<(/?)([A-Z][A-Z-]*)',rb'<\1r:\2',raw).replace(
        ('xmlns="'+NAMESPACE+'"').encode(),('xmlns:r="'+NAMESPACE+'"').encode())
    assert encode_reqif(read(raw))==encode_reqif(read(prefixed))


@pytest.mark.parametrize('mode',['core','pyz'])
def test_inverse_mapping_and_large_lexemes_in_isolated_distributions(mode,tmp_path):
    from support.portable import build_distribution
    from support.processes import run_core, run_python
    raw=one('REAL','1e999999999999999999999999')
    mapping=resource()
    body='\n'.join([
        'from specroad.exchange import decode_reqif, ReqIFLimits',
        'from specroad.mappings import ExchangeMapping',
        'doc=decode_reqif('+repr(raw)+',limits=ReqIFLimits(8000000,128,100000,4000000,64,512,8000000))',
        'm=ExchangeMapping('+repr(mapping.source_bytes)+')',
        'assert not doc.project_object("object")["representable"]',
        'out=doc.export_object("object",{"artifact_type":"requirement","statement":2.5},mappings=[m],key=m.key,expected_mapping_sha256=m.sha256,expected_source_sha256=doc.source_sha256,source_system="s",source_document="d")',
        'assert b\'THE-VALUE="2.5"\' in out["xml_bytes"]',
        'assert out["source_sha256"]==doc.source_sha256 and not out["export_complete"]'])
    if mode=='core':result=run_core(body,tmp_path)
    else:
        _,app=build_distribution(tmp_path/'dist')
        result=run_python(['-I','-S','-B','-c','import sys;sys.path.insert(0,'+repr(str(app))+');'+body],tmp_path)
    assert result.returncode==0,result.stderr
