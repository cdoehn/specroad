"""Independent complete input values exercise real request parsing and hashing."""
from hashlib import sha256
import json

import pytest

from specroad.analyzers import AnalyzerDescriptor
from specroad.analyzers.requests import (AnalysisRequestId, AnalyzerRequest, WriteRequestId,
    analyzer_binding, create_request, prepare_analysis_id)
from specroad.model.canonical import canonical_json_bytes
from specroad.model.identity_tokens import decode128
from test_analyzer_descriptors import external


def checksum(value):
    return sha256(canonical_json_bytes(value)).hexdigest()


def inputs():
    descriptor=external()
    binding={'artifact_id':'TEST-REQ-0001', 'artifact_revision':1,
             'artifact_sha256':'a'*64, 'field_pointer':'/statement'}
    text='原文 bleibt vollständig: Prüfe den gesamten Text.'
    subject={**binding,'subject_key':checksum(binding),'value':text,'value_sha256':checksum(text),
             'declared_language':'de','normative_force':'must'}
    context_value={'declared':'untrusted explicit context'}
    return dict(analyzers=[{'descriptor':descriptor,'descriptor_sha256':checksum(descriptor),
                'capabilities':['quality']}], subjects=[subject],
        context={'subject_keys':[subject['subject_key']], 'resources':[
            {'resource_id':'explicit-context','value':context_value,'sha256':checksum(context_value)}]},
        settings={'example.reviewer':{'policy':'full-text'}}, extensions={'example.future':{'key':'preserved'}})


def test_request_contains_complete_data_and_exact_independent_snapshot_projection():
    data=inputs(); request=create_request(**data,analysis_id='manual:Analysis-7')
    expected={'contract_version':'1.0.0',**data}
    assert request.data=={**expected,'request_id':'manual:Analysis-7','snapshot_sha256':checksum(expected)}
    read=AnalyzerRequest(json.dumps(request.data,indent=2,ensure_ascii=False).encode())
    assert read.data==request.data and read.analysis_id==AnalysisRequestId('manual:Analysis-7')
    assert read.binding=={'request_id':'manual:Analysis-7','snapshot_sha256':checksum(expected)}
    data['subjects'][0]['value']='mutated caller'
    exposed=read.data; exposed['subjects'].clear()
    assert read.data==request.data and len(read.data['subjects'])==1


def test_automatic_id_is_random128_and_independent_of_snapshot():
    first=create_request(**inputs()); second=create_request(**inputs())
    assert first.analysis_id != second.analysis_id
    for request in (first,second):
        assert request.analysis_id.value.startswith('AN-')
        assert len(decode128(request.analysis_id.value[3:]))==16
    assert first.binding['snapshot_sha256']==second.binding['snapshot_sha256']


def test_id_can_be_assigned_before_snapshot_and_is_preserved_by_every_read(monkeypatch):
    identity=prepare_analysis_id()
    def forbidden(*args,**kwargs):raise AssertionError('identity regenerated')
    monkeypatch.setattr('secrets.token_bytes',forbidden)
    request=create_request(**inputs(),analysis_id=identity)
    for _ in range(3):
        request=AnalyzerRequest(request.canonical_bytes)
        assert request.analysis_id==identity
    assert prepare_analysis_id(identity) is identity


@pytest.mark.parametrize('value',('X','same.write:id','A'*128))
def test_manual_analysis_id_is_unchanged_and_separate_from_write_namespace(value):
    identity=AnalysisRequestId(value); write=WriteRequestId(value)
    assert identity!=write and identity.namespace=='analysis' and write.namespace=='normative_write'
    assert create_request(**inputs(),analysis_id=value).analysis_id==identity


def test_selected_capabilities_and_descriptor_are_fully_bound():
    descriptor=AnalyzerDescriptor(canonical_json_bytes(external()))
    bound=analyzer_binding(descriptor,['quality'])
    assert bound==inputs()['analyzers'][0]
    assert bound['descriptor_sha256']==checksum(external())
    changed=inputs(); changed['analyzers']=[analyzer_binding(descriptor,['consistency'])]
    assert create_request(**changed,analysis_id='same').binding['snapshot_sha256'] != create_request(
        **inputs(),analysis_id='same').binding['snapshot_sha256']


@pytest.mark.parametrize('field',('subjects','context','settings','extensions','analyzers'))
def test_each_snapshot_component_changes_the_binding(field):
    original=inputs(); changed=inputs()
    if field=='subjects':
        changed[field][0]['value']+='!';changed[field][0]['value_sha256']=checksum(changed[field][0]['value'])
    elif field=='context':
        changed[field]['resources'][0]['value']={'declared':'different'}
        changed[field]['resources'][0]['sha256']=checksum(changed[field]['resources'][0]['value'])
    elif field=='settings':changed[field]['example.reviewer']['policy']='another-policy'
    elif field=='extensions':changed[field]['example.future']['key']='different'
    else:
        changed[field][0]['descriptor']['adapter_version']='3.0.0'
        changed[field][0]['descriptor_sha256']=checksum(changed[field][0]['descriptor'])
    assert create_request(**original,analysis_id='same').binding != create_request(**changed,analysis_id='same').binding
