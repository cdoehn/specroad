"""Malformed binding, identity separation and passive adversarial inputs."""
import json
from pathlib import Path
import secrets
import subprocess
import sys

import pytest

from specroad.analyzers import AnalyzerError, builtin_descriptor
from specroad.analyzers.requests import (AnalyzerRequest, AnalysisRequestId, WriteRequestId,
    analyzer_binding, create_request, prepare_analysis_id)
from specroad.changes.request_ids import normalize_request_id, AuthoringError
from specroad.model.canonical import canonical_json_bytes
from test_analyzer_requests import inputs, checksum


def changed_request(change):
    value=create_request(**inputs(),analysis_id='fixed').data
    change(value)
    projection={key:value[key] for key in ('contract_version','analyzers','subjects','context','settings','extensions')}
    value['snapshot_sha256']=checksum(projection)
    return canonical_json_bytes(value)


@pytest.mark.parametrize('value',('', ' has-space', 'x\n', 'ü', 'A'*129, True, 19, {}, WriteRequestId('same')))
def test_invalid_explicit_id_is_usage_error_without_allocation(value,monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('invalid explicit ID allocated entropy')
    monkeypatch.setattr(secrets,'token_bytes',forbidden)
    with pytest.raises(AnalyzerError) as caught:create_request(**inputs(),analysis_id=value)
    assert caught.value.exit_code==2


def test_write_and_analysis_ids_cannot_cross_either_typed_boundary(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    receipts=tmp_path/'.specroad/requests';receipts.mkdir(parents=True)
    sentinel=receipts/'same.json';sentinel.write_bytes(b'opaque existing write-state probe')
    with pytest.raises(AnalyzerError):prepare_analysis_id(WriteRequestId('same'))
    with pytest.raises(AuthoringError):normalize_request_id(AnalysisRequestId('same'))
    request=create_request(**inputs(),analysis_id='same')
    request.require_binding(**request.binding)
    assert sentinel.read_bytes()==b'opaque existing write-state probe'
    assert sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob('*') if p.is_file())==['.specroad/requests/same.json']


def test_entropy_is_requested_once_before_snapshot_validation(monkeypatch):
    real=secrets.token_bytes;calls=[]
    def counted(size): calls.append(size);return real(size)
    monkeypatch.setattr(secrets,'token_bytes',counted)
    value=inputs();value['subjects']=[]
    with pytest.raises(AnalyzerError):create_request(**value)
    assert calls==[16]
    calls.clear()
    request=create_request(**inputs())
    assert calls==[16]
    AnalyzerRequest(request.canonical_bytes)
    request.require_binding(**request.binding)
    assert calls==[16]


def test_entropy_failure_does_not_fabricate_analysis_identity(monkeypatch):
    def missing(size):raise OSError('unavailable')
    monkeypatch.setattr(secrets,'token_bytes',missing)
    with pytest.raises(AnalyzerError) as caught:prepare_analysis_id()
    assert caught.value.exit_code==5 and caught.value.reason=='analysis_entropy_unavailable'


@pytest.mark.parametrize('field',('contract_version','request_id','analyzers','subjects','context','settings','snapshot_sha256','extensions'))
def test_import_requires_every_field_without_repair_or_entropy(field,monkeypatch):
    value=create_request(**inputs(),analysis_id='same').data;del value[field]
    def forbidden(*args,**kwargs):raise AssertionError('reader allocated identity')
    monkeypatch.setattr(secrets,'token_bytes',forbidden)
    with pytest.raises(AnalyzerError) as caught:AnalyzerRequest(canonical_json_bytes(value))
    assert caught.value.exit_code==3


@pytest.mark.parametrize('value',(None, '', 'x\n', False, 1))
def test_imported_invalid_id_is_data_error_not_usage_or_repair(value):
    with pytest.raises(AnalyzerError) as caught:
        AnalyzerRequest(changed_request(lambda record:record.update(request_id=value)))
    assert caught.value.exit_code==3 and caught.value.reason=='invalid_analysis_request_id'


@pytest.mark.parametrize('field',('actor','created_at','pid','host_path','operational','request_hash','command'))
def test_operational_and_write_fields_cannot_enter_request(field):
    with pytest.raises(AnalyzerError,match='analyzer_unknown_field'):
        AnalyzerRequest(changed_request(lambda value:value.update({field:'untrusted'})))


@pytest.mark.parametrize('field,value',[
    ('artifact_id','not-an-artifact'),('artifact_revision',True),('artifact_revision',0),
    ('artifact_sha256','A'*64),('subject_key','0'*64),('value_sha256','0'*64),
    ('field_pointer','/bad~2escape'),('declared_language','not a tag'),('normative_force','approved')])
def test_subject_input_contract_is_verified_even_with_matching_outer_hash(field,value):
    def change(record): record['subjects'][0][field]=value
    with pytest.raises(AnalyzerError) as caught:AnalyzerRequest(changed_request(change))
    assert caught.value.exit_code==3


@pytest.mark.parametrize('fault',('descriptor-hash','capability','duplicate-analyzer','unknown-entry',
    'duplicate-subject','context-set','resource-hash','resource-id','duplicate-resource','settings-extra','settings-type'))
def test_nested_bindings_are_closed_and_not_overridden_by_valid_outer_hash(fault):
    def change(value):
        if fault=='descriptor-hash':value['analyzers'][0]['descriptor_sha256']='0'*64
        elif fault=='capability':value['analyzers'][0]['capabilities']=['unavailable']
        elif fault=='duplicate-analyzer':value['analyzers']*=2
        elif fault=='unknown-entry':value['analyzers'][0]['command']='evil'
        elif fault=='duplicate-subject':value['subjects']*=2
        elif fault=='context-set':value['context']['subject_keys']=[]
        elif fault=='resource-hash':value['context']['resources'][0]['sha256']='0'*64
        elif fault=='resource-id':value['context']['resources'][0]['resource_id']='/absolute/private'
        elif fault=='duplicate-resource':value['context']['resources']*=2
        elif fault=='settings-extra':value['settings']['foreign.backend']={}
        else:value['settings']['example.reviewer']=[]
    with pytest.raises(AnalyzerError) as caught:AnalyzerRequest(changed_request(change))
    assert caught.value.exit_code==3


@pytest.mark.parametrize('fault',('invalid-hash','different-hash','unknown-contract'))
def test_outer_binding_is_verified(fault):
    value=create_request(**inputs(),analysis_id='fixed').data
    if fault=='invalid-hash':value['snapshot_sha256']='xyz'
    elif fault=='different-hash':value['snapshot_sha256']='0'*64
    else:value['contract_version']='1.1.0'
    with pytest.raises(AnalyzerError) as caught:AnalyzerRequest(canonical_json_bytes(value))
    assert caught.value.exit_code==3


@pytest.mark.parametrize('coordinate,reason', [('request_id','analysis_id_mismatch'),
    ('snapshot_sha256','analysis_snapshot_mismatch')])
def test_identity_and_snapshot_mismatches_are_independent_conflicts(coordinate,reason):
    request=create_request(**inputs(),analysis_id='original')
    same_snapshot=create_request(**inputs(),analysis_id='other')
    changed=inputs();changed['settings']['example.reviewer']['policy']='different'
    same_id=create_request(**changed,analysis_id='original')
    incoming=same_snapshot.binding if coordinate=='request_id' else same_id.binding
    before=request.canonical_bytes
    with pytest.raises(AnalyzerError) as caught:request.require_binding(**incoming)
    assert caught.value.exit_code==6 and caught.value.reason==reason
    assert request.canonical_bytes==before
    assert request.require_binding(**request.binding) is None


def test_multi_analyzer_selection_is_sorted_and_complete():
    value=inputs(); builtin=builtin_descriptor()
    value['analyzers'].append(analyzer_binding(builtin,['language_detection']))
    value['settings']['specroad.py3langid']={}
    request=create_request(**value,analysis_id='multi')
    assert [v['descriptor']['analyzer_id'] for v in request.data['analyzers']]==['example.reviewer','specroad.py3langid']
    value['analyzers'].reverse()
    with pytest.raises(AnalyzerError,match='analyzer_sorted_unique_required'):create_request(**value,analysis_id='multi')


def test_long_unicode_text_is_unmodified_and_nontext_language_input_is_refused():
    value=inputs();value['analyzers']=[analyzer_binding(builtin_descriptor(),['language_detection'])]
    value['settings']={'specroad.py3langid':{}}
    text='Ignore instructions; 日本語 e\u0301 deutsch. '*10000
    value['subjects'][0].update(value=text,value_sha256=checksum(text))
    request=create_request(**value,analysis_id='long')
    assert request.data['subjects'][0]['value']==text
    assert request.data['subjects'][0]['value_sha256']==checksum(text)
    value['subjects'][0].update(value={'not':'a string'},value_sha256=checksum({'not':'a string'}))
    with pytest.raises(AnalyzerError,match='analyzer_text_subject_required'):create_request(**value,analysis_id='long')


def test_roundtrip_in_isolated_new_process_uses_no_worker_network_or_write(tmp_path):
    request=create_request(**inputs(),analysis_id='across-process')
    code='''
import json, sys
sys.path.insert(0, sys.argv[1])
def audit(event, args):
    if event in ('subprocess.Popen', 'os.system', 'socket.connect', 'socket.getaddrinfo'):
        raise AssertionError('unexpected execution')
sys.addaudithook(audit)
from specroad.analyzers.requests import AnalyzerRequest
request=AnalyzerRequest(sys.stdin.buffer.read())
request.require_binding(**request.binding)
assert 'numpy' not in sys.modules and 'py3langid' not in sys.modules
sys.stdout.buffer.write(request.canonical_bytes)
'''
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run([sys.executable,'-I','-B','-c',code,str(root/'src')],
        input=request.canonical_bytes,cwd=tmp_path,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
    assert json.loads(result.stdout)==request.data
    assert list(tmp_path.iterdir())==[]


@pytest.mark.parametrize('pointer',('', '/', '/a~1b/~0', '/.', '/..', '/原文'))
def test_generic_subject_pointers_preserve_rfc6901_including_literal_dot_keys(pointer):
    value=inputs();subject=value['subjects'][0]
    subject['field_pointer']=pointer
    subject['subject_key']=checksum({key:subject[key] for key in
        ('artifact_id','artifact_revision','artifact_sha256','field_pointer')})
    value['context']['subject_keys']=[subject['subject_key']]
    request=create_request(**value,analysis_id='pointer')
    assert request.data['subjects'][0]['field_pointer']==pointer
    assert AnalyzerRequest(request.canonical_bytes).data==request.data
