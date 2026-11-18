"""Real descriptor values and immutable binding; no project or worker needed."""
from hashlib import sha256
import json

import pytest

from specroad.analyzers import AnalyzerDescriptor, AnalyzerError, builtin_descriptor, classify_descriptor
from specroad.model.canonical import canonical_json_bytes


def external():
    return {'contract_version': '1.0.0', 'analyzer_id': 'example.reviewer', 'adapter_version': '2.3.1',
        'capabilities': ['consistency', 'quality'], 'subject_modes': ['multi_subject', 'structured'],
        'result_schema_version': '1.2.0', 'execution_mode': 'external_result_only',
        'determinism': 'not_guaranteed', 'dependency_requirements': [],
        'extensions': {'example.future': {'text': '原文', 'enabled': False, 'weight': None}}}


def test_builtin_and_external_are_distinct_without_claiming_installed_worker():
    builtin = builtin_descriptor()
    assert builtin.data['analyzer_id'] == 'specroad.py3langid'
    assert builtin.data['capabilities'] == ['language_detection']
    assert builtin.data['subject_modes'] == ['single_text']
    assert builtin.data['dependency_requirements'] == [
        {'name':'numpy','requirement':'*'}, {'name':'py3langid','requirement':'==0.4.0'},
        {'name':'python','requirement':'>=3.10'}]
    assert classify_descriptor(builtin)['known_builtin']
    foreign = AnalyzerDescriptor(json.dumps(external(), ensure_ascii=False).encode())
    assert foreign.data == external()
    assert not classify_descriptor(foreign)['known_builtin']
    assert not classify_descriptor(builtin)['execution_supported']
    assert not classify_descriptor(foreign)['execution_supported']


def test_descriptor_hash_owns_all_values_and_ignores_source_formatting():
    value = external()
    compact = AnalyzerDescriptor(canonical_json_bytes(value))
    formatted = AnalyzerDescriptor(json.dumps(value, indent=3).encode())
    assert compact.sha256 == formatted.sha256 == sha256(canonical_json_bytes(value)).hexdigest()
    value['extensions']['example.future']['enabled'] = True
    assert compact.data == external()
    returned = compact.data; returned['capabilities'].append('foreign')
    assert compact.data['capabilities'] == ['consistency', 'quality']
    assert AnalyzerDescriptor(canonical_json_bytes(value)).sha256 != compact.sha256


@pytest.mark.parametrize('mode', ('single_text', 'multi_subject', 'structured'))
@pytest.mark.parametrize('execution', ('builtin_worker', 'external_result_only', 'future_unsupported'))
def test_valid_subject_and_execution_metadata_remains_passive(mode, execution):
    value = external(); value.update(subject_modes=[mode], execution_mode=execution)
    descriptor = AnalyzerDescriptor(canonical_json_bytes(value))
    assert descriptor.data == value
    assert not classify_descriptor(descriptor)['execution_supported']


@pytest.mark.parametrize('version', ('1.0.0','0.0.1','1.2.3-rc.1+build.007'))
def test_adapter_and_result_version_are_data_not_execution_rights(version):
    value = external(); value.update(adapter_version=version, result_schema_version=version)
    descriptor = AnalyzerDescriptor(canonical_json_bytes(value))
    assert descriptor.data['adapter_version'] == version
    assert not classify_descriptor(descriptor)['execution_supported']


@pytest.mark.parametrize('field,value', [('contract_version','2.0.0'), ('analyzer_id','Bad Name'),
    ('subject_modes',[]), ('capabilities',['quality','consistency']), ('execution_mode','shell'),
    ('dependency_requirements',[{'name':'x','requirement':'\ninstall'}])])
def test_invalid_descriptor_refuses_whole_value(field, value):
    record=external(); record[field]=value
    with pytest.raises(AnalyzerError) as error: AnalyzerDescriptor(canonical_json_bytes(record))
    assert error.value.exit_code == 3
