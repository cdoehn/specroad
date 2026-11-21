"""Closed data boundaries, exact identity binding and absence of execution."""
import importlib
import json
import socket
import subprocess
import sys

import pytest

from specroad.analyzers import AnalyzerDescriptor, AnalyzerError, builtin_descriptor, classify_descriptor
from specroad.model.canonical import canonical_json_bytes
from test_analyzer_descriptors import external


@pytest.mark.parametrize('field',tuple(external()))
def test_every_descriptor_field_is_required(field):
    value=external(); del value[field]
    with pytest.raises(AnalyzerError, match='analyzer_missing_field'):
        AnalyzerDescriptor(canonical_json_bytes(value))


@pytest.mark.parametrize('field',('command','module','entrypoint','url','environment','execution_supported'))
def test_no_executable_descriptor_fields_are_admitted(field):
    value=external(); value[field]='untrusted.module'
    with pytest.raises(AnalyzerError, match='analyzer_unknown_field'):
        AnalyzerDescriptor(canonical_json_bytes(value))


@pytest.mark.parametrize('field,value', [
    ('contract_version', True), ('contract_version', '1.1.0'), ('contract_version', '1.0.0+unknown'),
    ('adapter_version', '01.0.0'), ('adapter_version', '1.0.0-01'), ('result_schema_version', '1.2'),
    ('analyzer_id','x'*129), ('analyzer_id','аnalyzer'), ('analyzer_id','a..b'), ('analyzer_id','a\n'),
    ('capabilities', ['x','x']), ('capabilities', [True]), ('subject_modes',['unknown']),
    ('determinism', None), ('execution_mode', {'command':'evil'}),
    ('extensions', {'plain':1}), ('extensions',{'example. x':1}),
    ('dependency_requirements',{}), ('dependency_requirements',[{'name':'x','requirement':'*','command':'evil'}]),
    ('dependency_requirements',[{'name':'x','requirement':'*'},{'name':'x','requirement':'==1'}]),
    ('dependency_requirements',[{'name':'z','requirement':'*'},{'name':'a','requirement':'*'}]),
    ('dependency_requirements',[{'name':'x','requirement':False}]),
    ('dependency_requirements',[{'name':'x','requirement':''}]),
])
def test_descriptor_edge_values_fail_without_coercion(field,value):
    record=external();record[field]=value
    with pytest.raises(AnalyzerError) as caught: AnalyzerDescriptor(canonical_json_bytes(record))
    assert caught.value.exit_code==3


@pytest.mark.parametrize('raw',(b'[]',b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":"\xff"}',b'{'))
def test_native_json_refusals_stay_data_errors(raw):
    with pytest.raises(AnalyzerError) as caught: AnalyzerDescriptor(raw)
    assert caught.value.exit_code==3


@pytest.mark.parametrize('field,value,reason',[
    ('analyzer_id','foreign.backend','analyzer_identity_mismatch'),
    ('adapter_version','9.0.0','analyzer_version_mismatch'),
    ('descriptor_sha256','0'*64,'analyzer_descriptor_mismatch')])
def test_declared_hash_never_overrides_observed_descriptor(field,value,reason):
    descriptor=AnalyzerDescriptor(canonical_json_bytes(external()))
    binding=dict(analyzer_id='example.reviewer',adapter_version='2.3.1',descriptor_sha256=descriptor.sha256)
    assert descriptor.require_binding(**binding) is None
    binding[field]=value
    with pytest.raises(AnalyzerError) as caught: descriptor.require_binding(**binding)
    assert caught.value.exit_code==6 and caught.value.reason==reason


@pytest.mark.parametrize('capabilities',([],['unknown'],['quality','consistency'],['quality','quality']))
def test_selection_is_nonempty_sorted_declared_subset(capabilities):
    descriptor=AnalyzerDescriptor(canonical_json_bytes(external()))
    assert descriptor.select_capabilities(['quality'])==('quality',)
    with pytest.raises(AnalyzerError): descriptor.select_capabilities(capabilities)


def test_spoofed_builtin_and_unknown_extensions_never_import_or_start_code(monkeypatch):
    record=external();record.update(analyzer_id='specroad.py3langid',execution_mode='builtin_worker')
    record['extensions']={'evil.plugin':{'module':'numpy','command':['touch','forbidden'],'url':'https://invalid.example/'}}
    raw=canonical_json_bytes(record)
    imports=set(sys.modules)
    def forbidden(*args,**kwargs): raise AssertionError('passive metadata executed')
    with monkeypatch.context() as patch:
        patch.setattr(importlib,'import_module',forbidden)
        patch.setattr(subprocess,'Popen',forbidden)
        patch.setattr(socket.socket,'connect',forbidden)
        descriptor=AnalyzerDescriptor(raw)
        classification=classify_descriptor(descriptor)
        assert descriptor.data==record
        assert not classification['known_builtin'] and not classification['execution_supported']
        copy=AnalyzerDescriptor(json.dumps(builtin_descriptor().data).encode())
        assert classify_descriptor(copy)['known_builtin']
        assert classify_descriptor(copy)['execution_supported']
        assert classify_descriptor(copy)['availability'] == 'not_checked'
    assert not ({'numpy','py3langid'} & (set(sys.modules)-imports))


def test_changed_known_descriptor_is_not_a_new_registry_entry():
    original=builtin_descriptor(); value=original.data
    value['extensions']['example.future']='still passive'
    copy=AnalyzerDescriptor(canonical_json_bytes(value))
    assert not classify_descriptor(copy)['known_builtin']
    assert classify_descriptor(original)['known_builtin']
    assert builtin_descriptor().data==original.data
