"""14.h.W: typed object roundtrips, explicit mappings and passive boundaries."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import json
from unittest.mock import patch

import pytest

from specroad.exchange import (ReqIFDocument, ReqIFError, ReqIFLimits, decode_reqif,
                              encode_reqif, reqif_object_identifier)
from specroad.mappings import ExchangeMapping, MappingError
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.exchange_mappings import mapping_value
from support.read_only import no_write_attempts
from support.reqif_objects import (LIMITS, TIME, datatype, definition, document,
                                  one, spec_object, value)


def read(raw):
    return decode_reqif(raw, limits=LIMITS)


def semantic(doc):
    return [(o.identifier, o.type_id, [(v.family, v.definition_id, v.lexical) for v in o.values], o.element.attributes)
            for o in doc.objects]


@pytest.mark.parametrize('family,literal,expected', [
    ('BOOLEAN', 'true', True), ('BOOLEAN', '0', False), ('INTEGER', '+00012', 12),
    ('INTEGER', '-12', -12), ('REAL', '1.25E+2', 125), ('REAL', '.5', .5),
    ('STRING', ' e\u0301 é 日本語 & < " \n\t', ' e\u0301 é 日本語 & < " \n\t'),
    ('DATE', '2024-02-29T23:59:59.123456789+14:00', '2024-02-29T23:59:59.123456789+14:00'),
    ('DATE', '2024-02-29T00:00:00', '2024-02-29T00:00:00'),
    ('ENUMERATION', ['enum_b', 'enum_a'], ['enum_a', 'enum_b']),
    ('ENUMERATION', [], []),
])
def test_typed_values_and_lexemes_survive_real_xml_roundtrip(family, literal, expected):
    raw = one(family, literal)
    with no_write_attempts():
        doc = read(raw)
        encoded = encode_reqif(doc)
        again = read(encoded)
    assert doc.project_object('object')['fields'] == {'field': expected}
    assert doc.project_object('object') == again.project_object('object')
    assert semantic(again) == semantic(doc)
    assert encoded != raw and encode_reqif(again) == encoded
    assert doc.source_bytes == raw and doc.source_sha256 == sha256(raw).hexdigest()
    assert again.datatypes[0].element.attrs == doc.datatypes[0].element.attrs
    assert again.types[0].definitions[0].element.attrs == doc.types[0].definitions[0].element.attrs
    assert TIME.encode() in encoded and b'IS-EDITABLE="false"' in encoded


@pytest.mark.parametrize('family,explicit,default,expected', [
    ('BOOLEAN','false','true',False), ('INTEGER','0','12',0), ('REAL','0.0','1.5',0),
    ('STRING','','default',''), ('ENUMERATION',[],['enum_a'],[]),
])
def test_explicit_false_zero_and_empty_values_do_not_activate_defaults(family, explicit, default, expected):
    doc = read(one(family, explicit, default=default))
    projection = doc.project_object('object')
    assert projection['fields'] == {'field': expected} and projection['origins'] == {'field':'explicit'}
    again = read(encode_reqif(doc))
    assert again.project_object('object') == projection
    assert again.types[0].definitions[0].default.lexical == (tuple(default) if type(default) is list else default)


@pytest.mark.parametrize('default,expected,origin', [(None,{},'absent'), ('',{'field':''},'default'), ('default',{'field':'default'},'default')])
def test_defaults_and_absence_remain_separate_without_export_materialization(default, expected, origin):
    doc = read(one(literal=None, default=default))
    assert doc.project_object('object')['fields'] == expected
    assert doc.project_object('object')['origins'] == {'field': origin}
    assert doc.objects[0].values == ()
    again = read(encode_reqif(doc))
    assert again.objects[0].values == () and again.project_object('object') == doc.project_object('object')


def test_same_names_distinct_ids_forward_references_and_metadata_are_not_inferred():
    definitions = definition('STRING', 'first', 'dt', 'a') + definition('STRING','second','dt','b')
    raw = document(datatypes=datatype('STRING'), definitions=definitions,
                   objects=spec_object(value('STRING','second','explicit')))
    # Forward references from objects to types and datatypes remain resolvable.
    text = raw.decode(); begin=text.index('<DATATYPES>'); end=text.index('</SPEC-OBJECTS>')+len('</SPEC-OBJECTS>')
    block=text[begin:end]; a=block.index('<SPEC-TYPES>'); b=block.index('<SPEC-OBJECTS>')
    raw=(text[:begin]+block[b:]+block[a:b]+block[:a]+text[end:]).encode()
    doc=read(raw)
    assert doc.project_object('object')['fields'] == {'first':'a','second':'explicit'}
    renamed=raw.replace(b'same display name',b'changed display name')
    assert read(renamed).project_object('object') == doc.project_object('object')
    assert read(encode_reqif(doc)).project_object('object') == doc.project_object('object')


@pytest.mark.parametrize('raw', [document(), document(objects=spec_object())], ids=['empty','empty-values'])
def test_minimal_header_and_empty_object_values_are_valid(raw):
    doc = read(raw)
    assert semantic(read(encode_reqif(doc))) == semantic(doc)
    assert doc.observation()['object_count'] in (0,1)
    assert doc.observation()['import_complete'] is False


def test_empty_content_can_be_serialized_without_inventing_definitions():
    raw = document().replace(b'<SPEC-TYPES><SPEC-OBJECT-TYPE IDENTIFIER="type" LAST-CHANGE="'+TIME.encode()+b'"><SPEC-ATTRIBUTES></SPEC-ATTRIBUTES></SPEC-OBJECT-TYPE></SPEC-TYPES>', b'')
    doc=read(raw)
    assert doc.types == doc.objects == doc.datatypes == ()
    assert read(encode_reqif(doc)).types == ()


def mapping(*, value_map=None, field='field'):
    return ExchangeMapping(artifact_bytes(mapping_value(types=[{'external_type':'type','artifact_type':'requirement'}],
        fields=[{'external_type':'type','external_field':field,'target_field':'statement','value_map':value_map}],
        relations=[],hierarchies=[])))


def mapped(doc, resource, **changes):
    args={'mappings':[resource], 'key':resource.key, 'expected_mapping_sha256':resource.sha256,
          'expected_source_sha256':doc.source_sha256,'source_system':'explicit supplier','source_document':'explicit document'}
    args.update(changes)
    return doc.map_object('object',**args)


def test_mapping_uses_bound_ids_explicit_context_and_enum_array_value_map():
    doc=read(one('ENUMERATION',['enum_b']))
    resource=mapping(value_map=[{'external_value':['enum_b'],'target_value':'mapped statement'}])
    with no_write_attempts(): result=mapped(doc,resource,external_revision='external revision')
    assert result['artifact'] == {'artifact_type':'requirement','statement':'mapped statement'}
    assert result['mapping'] == resource.binding() and result['mapping_complete'] is True
    assert result['external_identity'] == {'source_system':'explicit supplier','source_document':'explicit document',
        'external_id':'object','external_revision':'external revision'}
    assert result['fields']['field'] == ['enum_b'] and result['origins']['field']=='explicit'
    assert result['import_complete'] is result['write_authorized'] is result['execution_ready'] is False


@pytest.mark.parametrize('case', ['source','mapping','names','missing','unmapped-value','format'])
def test_mapping_failures_keep_existing_contracts_and_never_infer_fields(case):
    doc=read(one());resource=mapping();changes={}
    if case=='source': changes['expected_source_sha256']='0'*64
    if case=='mapping': changes['expected_mapping_sha256']='0'*64
    if case=='names': resource=mapping(field='same display name')
    if case=='missing': doc=read(one(literal=None))
    if case=='unmapped-value': resource=mapping(value_map=[{'external_value':'other','target_value':'not selected'}])
    if case=='format':
        data=resource.data;data['source_format']='csv';resource=ExchangeMapping(artifact_bytes(data))
    with no_write_attempts(), pytest.raises((ReqIFError,MappingError)) as caught:
        mapped(doc,resource,**changes)
    if case=='source': assert caught.value.exit_code==6
    elif case=='format': assert caught.value.exit_code==2
    else: assert type(caught.value) is MappingError and caught.value.exit_code==3


@pytest.mark.parametrize('family,literal', [('INTEGER','9007199254740993'), ('REAL','1.0000000000000001'),
    ('REAL','1e-9999'), ('REAL','INF'), ('REAL','-INF'), ('REAL','NaN'), ('REAL','-0.0')])
def test_nonrepresentable_numbers_keep_source_types_and_block_native_mapping(family,literal):
    doc=read(one(family,literal,default='1'))
    projection=doc.project_object('object')
    assert projection['fields']=={} and projection['representable'] is False
    assert projection['unrepresentable'][0]['object_id']=='object'
    assert projection['unrepresentable'][0]['definition_id']=='field'
    assert projection['origins']=={'field':'explicit'}
    assert doc.objects[0].values[0].lexical==literal
    assert read(encode_reqif(doc)).objects[0].values[0].lexical==literal
    result=mapped(doc,mapping())
    assert result['artifact'] is None and result['mapping_complete'] is False
    assert result['unrepresentable']==projection['unrepresentable']


@pytest.mark.parametrize('before,after,reason', [
    (b'IDENTIFIER="object"',b'IDENTIFIER="type"','reqif_invalid_or_duplicate_identifier'),
    (b'IDENTIFIER="object"',b'IDENTIFIER="1bad"','reqif_invalid_or_duplicate_identifier'),
    (b'IDENTIFIER="object"',b'IDENTIFIER=" object"','reqif_invalid_or_duplicate_identifier'),
    (b'<SPEC-OBJECT-TYPE-REF>type<',b'<SPEC-OBJECT-TYPE-REF>missing<','reqif_object_type_reference'),
    (b'<DATATYPE-DEFINITION-STRING-REF>dt<',b'<DATATYPE-DEFINITION-STRING-REF>missing<','reqif_datatype_reference'),
    (b'<ATTRIBUTE-DEFINITION-STRING-REF>field<',b'<ATTRIBUTE-DEFINITION-STRING-REF>missing<','reqif_object_definition_reference'),
    (b'<REQ-IF-VERSION>1.0<',b'<REQ-IF-VERSION>1.2<','reqif_header_version'),
    (b'<TITLE>Types</TITLE>',b'','reqif_missing_element'),
    (b'<VALUES>',b'<VALUES>not structural whitespace','reqif_invalid_container'),
])
def test_invalid_structure_and_references_fail_before_any_object_projection(before,after,reason):
    raw=one().replace(before,after)
    with no_write_attempts(),pytest.raises(ReqIFError) as caught: read(raw)
    assert caught.value.reason==reason and caught.value.exit_code==3
    assert caught.value.pointer
    assert 'owned text' not in json.dumps(caught.value.diagnostic())


def test_duplicate_object_attribute_and_foreign_type_definition_are_rejected():
    raw=document(datatypes=datatype('STRING'),definitions=definition('STRING','field','dt'),
                 objects=spec_object(value('STRING','field','a')+value('STRING','field','b')))
    with pytest.raises(ReqIFError) as caught:read(raw)
    assert caught.value.reason=='reqif_object_definition_reference' and caught.value.object_id=='object'
    extra='<SPEC-OBJECT-TYPE IDENTIFIER="other" LAST-CHANGE="'+TIME+'"><SPEC-ATTRIBUTES>'+definition('STRING','foreign','dt')+'</SPEC-ATTRIBUTES></SPEC-OBJECT-TYPE>'
    raw=one().replace(b'</SPEC-TYPES>',extra.encode()+b'</SPEC-TYPES>').replace(b'<ATTRIBUTE-DEFINITION-STRING-REF>field<',b'<ATTRIBUTE-DEFINITION-STRING-REF>foreign<')
    with pytest.raises(ReqIFError) as caught:read(raw)
    assert caught.value.reason=='reqif_object_definition_reference'


@pytest.mark.parametrize('family,literal', [('BOOLEAN','False'),('INTEGER','1.5'),('REAL','1,2'),
    ('DATE','2023-02-29T00:00:00Z'),('ENUMERATION',['missing']),('ENUMERATION',['enum_a','enum_a'])])
def test_bad_explicit_values_are_not_replaced_by_valid_defaults(family,literal):
    defaults={'BOOLEAN':'true','INTEGER':'1','REAL':'1','DATE':'2024-01-01T00:00:00Z','ENUMERATION':['enum_a']}
    with pytest.raises(ReqIFError) as caught:read(one(family,literal,default=defaults[family]))
    assert caught.value.exit_code==3 and caught.value.object_id=='object' and caught.value.definition_id=='field'


def test_single_enumeration_keeps_array_shape_and_rejects_multiple_choices():
    assert read(one('ENUMERATION',['enum_a'],multi=False)).project_object('object')['fields']=={'field':['enum_a']}
    with pytest.raises(ReqIFError):read(one('ENUMERATION',['enum_a','enum_b'],multi=False))


def test_observations_and_metadata_are_owned_and_never_authorize_import():
    doc=read(one()); projection=doc.project_object('object');projection['fields']['field']='changed'
    assert doc.project_object('object')['fields']=={'field':'owned text'}
    doc.objects[0].element.attrs['LONG-NAME']='changed'
    assert doc.objects[0].element.attrs['LONG-NAME']=='object name'
    with pytest.raises(FrozenInstanceError): doc.objects=()
    with pytest.raises(FrozenInstanceError): doc.objects[0].values=()
    with pytest.raises(TypeError): bool(doc)
    assert doc.observation()['validation_scope']=='reqif_type_object_subset'


def test_first_export_identity_matches_independent_hash_and_ignores_names_revisions():
    artifact=domain_value(external_identities=[])
    inputs={'project_id':'project', 'source_system':'supplier','source_document':'document'}
    expected='_sr_'+sha256(json.dumps({'project_id':'project','artifact_type':artifact['artifact_type'],'id':artifact['id']},sort_keys=True,separators=(',',':')).encode()).hexdigest()
    before=deepcopy(artifact)
    with no_write_attempts():
        first=reqif_object_identifier(artifact,**inputs)
        changed={**artifact,'revision':artifact['revision']+1,'title':'another name'}
        assert reqif_object_identifier(changed,**inputs)==first==expected
    assert artifact==before
    assert reqif_object_identifier(artifact,**{**inputs,'project_id':'different'})!=first


@pytest.mark.parametrize('case',['existing','other-context','ambiguous','invalid','collision'])
def test_existing_identity_priority_and_explicit_conflicts(case):
    item={'source_system':'supplier','source_document':'document','external_id':'existing'}
    artifact=domain_value(external_identities=[item])
    args={'project_id':'project','source_system':'supplier','source_document':'document'}
    if case=='other-context': args['source_document']='elsewhere'
    if case=='ambiguous': artifact['external_identities'].append({**item,'external_id':'second'})
    if case=='invalid': artifact['external_identities'][0]['external_id']='not valid'
    if case=='collision':args['used_ids']=('existing',)
    if case in ('existing','other-context'):
        actual=reqif_object_identifier(artifact,**args)
        assert actual=='existing' if case=='existing' else actual.startswith('_sr_')
    else:
        with pytest.raises(ReqIFError) as caught:reqif_object_identifier(artifact,**args)
        assert caught.value.exit_code==6


@pytest.mark.parametrize('injection', [
    b'<!DOCTYPE REQ-IF [<!ENTITY ex SYSTEM "file:///never">]>', b'<!DOCTYPE REQ-IF SYSTEM "https://never.invalid/file">',
    b'<?external https://never.invalid?>'])
def test_dtd_entities_and_processing_instructions_are_rejected_without_resolution(injection):
    raw=one().replace(b'<REQ-IF ',injection+b'<REQ-IF ',1)
    with no_write_attempts(),pytest.raises(ReqIFError) as caught:read(raw)
    assert caught.value.exit_code==7 and caught.value.position is not None


@pytest.mark.parametrize('extra', [
    '<TOOL-EXTENSIONS><REQ-IF-TOOL-EXTENSION><unknown xmlns="urn:fixture">keep me</unknown></REQ-IF-TOOL-EXTENSION></TOOL-EXTENSIONS>',
    '<TOOL-EXTENSIONS><REQ-IF-TOOL-EXTENSION><xi:include xmlns:xi="http://www.w3.org/2001/XInclude" href="file:///never"/></REQ-IF-TOOL-EXTENSION></TOOL-EXTENSIONS>',
])
def test_unknown_content_is_retained_and_never_claims_complete_export(extra):
    raw=document(extensions=extra)
    if 'xi:include' in extra:
        with no_write_attempts(),pytest.raises(ReqIFError) as caught: read(raw)
        assert caught.value.exit_code==7
    else:
        doc=read(raw)
        assert doc.source_bytes==raw and doc.observation()['uninterpreted']
        with pytest.raises(ReqIFError):encode_reqif(doc)


@pytest.mark.parametrize('bound,value', [('max_bytes',1),('max_depth',2),('max_elements',3),('max_text_chars',4),
    ('max_attributes_per_element',1),('max_name_chars',4),('max_expanded_name_chars',4)])
def test_explicit_document_limits_use_the_shared_xml_safety_reader(bound,value):
    with pytest.raises(ReqIFError) as caught:decode_reqif(one(),limits=replace(LIMITS,**{bound:value}))
    assert caught.value.exit_code==7


@pytest.mark.parametrize('limits',[None,{},1])
def test_limits_are_explicit_typed_inputs(limits):
    with pytest.raises(ReqIFError) as caught:decode_reqif(one(),limits=limits)
    assert caught.value.exit_code==2


def test_resource_errors_are_not_converted_to_success_or_format_errors():
    with patch('specroad.exchange.reqif.read_bounded_xml',side_effect=MemoryError('host')):
        with pytest.raises(MemoryError):read(one())


@pytest.mark.parametrize('mode',['core','pyz'])
def test_passive_reqif_codec_is_available_in_isolated_distributions(mode,tmp_path):
    from support.portable import build_distribution
    from support.processes import run_core, run_python
    body='\n'.join([
        'from specroad.exchange import decode_reqif, encode_reqif, ReqIFLimits',
        'raw='+repr(one('BOOLEAN','false',default='true')),
        'limits=ReqIFLimits(8000000,128,100000,4000000,64,512,8000000)',
        'doc=decode_reqif(raw,limits=limits)',
        'assert doc.project_object("object")["fields"] == {"field":False}',
        'assert decode_reqif(encode_reqif(doc),limits=limits).project_object("object") == doc.project_object("object")',
        'assert not doc.observation()["write_authorized"]'])
    if mode=='core':
        result=run_core(body,tmp_path)
    else:
        _,app=build_distribution(tmp_path/'dist')
        result=run_python(['-I','-S','-B','-c','import sys;sys.path.insert(0,'+repr(str(app))+');'+body],tmp_path)
    assert result.returncode==0,result.stderr


def test_mismatched_value_family_does_not_reinterpret_the_definition():
    raw=one().replace(b'ATTRIBUTE-VALUE-STRING',b'ATTRIBUTE-VALUE-INTEGER').replace(
        b'ATTRIBUTE-DEFINITION-STRING-REF',b'ATTRIBUTE-DEFINITION-INTEGER-REF')
    with pytest.raises(ReqIFError) as caught:read(raw)
    assert caught.value.reason=='reqif_value_family_mismatch'
    assert caught.value.object_id=='object' and caught.value.definition_id=='field'


def test_numerical_failure_and_an_unmapped_value_are_distinguishable():
    resource=mapping()
    definitions=definition('STRING','field','text')+definition('REAL','extra','real')
    raw=document(datatypes=datatype('STRING','text')+datatype('REAL','real'),definitions=definitions,
                 objects=spec_object(value('STRING','field','mapped')+value('REAL','extra','1.5')))
    result=mapped(read(raw),resource)
    assert result['unmapped']=={'extra':1.5} and result['unrepresentable']==[]
    result=mapped(read(raw.replace(b'THE-VALUE="1.5"',b'THE-VALUE="1e-9999"')),resource)
    assert result['artifact'] is None and not result['mapping_complete']
    assert result['unrepresentable'][0]['definition_id']=='extra'
