"""Required checks from explicit contracts, never execution or verification success."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
import shutil

import pytest

from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.verification import (VerificationContract, VerificationContractResolution,
    VerificationTest, prepare_verification_contract, resolve_verification_contract)
from support.artifacts import artifact_bytes
from support.domain import domain_value, relation
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import record_value, ref
from support.targets import model, SCOPE


def contract_records(**overrides):
    contract = record_value('verification', **overrides)
    subject = domain_value('requirement', relations=[relation('verified_by', contract['id'])])
    return [subject, contract]


def referenced_test_records():
    records = contract_records(dimensions=['safety', 'performance'], evidence_slots=[
        {'check_id': 'latency', 'test_id': ref('TEST'), 'dimension': 'performance'},
        {'check_id': 'safe-stop', 'test_id': ref('TEST'), 'dimension': 'safety'},
        {'check_id': 'review', 'test_id': None, 'dimension': 'safety'}])
    records.append(record_value('test', test_identity={'path': 'tests/device.py'}))
    return records


@pytest.mark.parametrize('method', ['inspection', 'review', 'analysis', 'simulation',
    'automated_test', 'manual_test', 'formal_proof', 'monitoring', 'audit', 'measurement'])
def test_all_normative_methods_preserve_procedure_oracle_and_configuration_policy(method):
    records = contract_records(method=method, preconditions=['Device is offline'],
        procedure=['Open fixture', 'Measure response'], oracle={'max_ms': 10},
        evidence_kinds=['measurement', 'report'], configuration_policy='independent')
    supplied = model(records)
    with no_write_attempts():
        result = resolve_verification_contract(supplied, ref(), ref('VER'))
    data = result.data
    assert data['contract']['record'] == records[1]
    assert data['required_checks'] == [{'subject_artifact_id': ref(), 'contract_id': ref('VER'),
        'test_id': None, 'check_id': 'overall', 'dimension': 'overall'}]
    assert data['tests'] == []
    assert data['scope_descriptor'] == SCOPE
    assert data['model_root_sha256'] == supplied.manifest(supplied.artifacts, SCOPE).sha256
    assert data['input_sha256'] == supplied._sources_sha256


@pytest.mark.parametrize('identity', [{'external_id': 'suite/device#case'}, {'path': 'tests/device.py'}])
def test_stable_test_identity_and_oracle_are_passive_bound_metadata(identity):
    records = referenced_test_records(); records[2]['test_identity'] = identity
    supplied = model(records)
    with no_write_attempts():
        result = resolve_verification_contract(supplied, ref(), ref('VER'))
    data = result.data
    assert len(data['tests']) == 1
    assert data['tests'][0]['record'] == records[2]
    assert data['contract']['record']['evidence_slots'] == records[1]['evidence_slots']
    assert data['required_checks'] == [
        {'subject_artifact_id': ref(), 'contract_id': ref('VER'), 'test_id': None,
         'check_id': 'review', 'dimension': 'safety'},
        {'subject_artifact_id': ref(), 'contract_id': ref('VER'), 'test_id': ref('TEST'),
         'check_id': 'latency', 'dimension': 'performance'},
        {'subject_artifact_id': ref(), 'contract_id': ref('VER'), 'test_id': ref('TEST'),
         'check_id': 'safe-stop', 'dimension': 'safety'}]
    for binding in (data['subject'], data['contract'], data['tests'][0]):
        value = binding['record']; path = artifact_path(value['artifact_type'], value['id'], 'SR')
        assert binding['path'] == path and binding['revision'] == value['revision']
        assert binding['source_sha256'] == sha256(supplied.source_files[path]).hexdigest()
        assert binding['record_sha256'] == canonical_json_sha256(value)
    assert data['relations'][0]['record'] == records[0]['relations'][0]
    assert data['relations'][0]['pointer'] == '/relations/0'
    assert data['relations'][0]['record_sha256'] == canonical_json_sha256(records[0]['relations'][0])
    assert not any(data[key] for key in ('project_files_verified', 'full_validation_passed',
        'project_required_checks_complete', 'configuration_applicability_evaluated',
        'evidence_evaluated', 'test_code_executed', 'write_authorized', 'approval_granted'))


@pytest.mark.parametrize('declare_dimension', [True, False])
def test_new_draft_materializes_overall_only_when_slots_are_absent(declare_dimension):
    value = record_value('verification'); value.pop('evidence_slots')
    if not declare_dimension: value.pop('dimensions')
    before = deepcopy(value)
    with no_write_attempts(): result = prepare_verification_contract(value)
    assert result.data['dimensions'] == ['overall']
    assert result.data['evidence_slots'] == [{'check_id': 'overall', 'test_id': None, 'dimension': 'overall'}]
    assert result.data['revision'] == 1 and result.data['maturity'] == 'draft'
    assert value == before


def test_explicit_slots_and_declared_dimensions_are_not_replaced_by_defaults():
    value = referenced_test_records()[1]
    result = prepare_verification_contract(value)
    assert result.data == value


@pytest.mark.parametrize('dimensions', [['overall', 'safety'], ['safety'], [], None])
def test_default_never_discards_an_explicit_dimension_selection(dimensions):
    value = record_value('verification', dimensions=dimensions); value.pop('evidence_slots')
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        prepare_verification_contract(value, path='contract.json')
    assert caught.value.reason == 'explicit_verification_slots_required'
    assert caught.value.pointer == '/evidence_slots' and caught.value.path == 'contract.json'


@pytest.mark.parametrize('slots', [None, [], {}])
def test_explicit_empty_or_malformed_slots_are_not_absence(slots):
    value = record_value('verification', evidence_slots=slots)
    with no_write_attempts(), pytest.raises(ModelError): prepare_verification_contract(value)


@pytest.mark.parametrize('overrides', [{'revision': 2}, {'maturity': 'approved'}])
def test_new_draft_helper_cannot_repair_an_existing_revision_or_approved_record(overrides):
    value = record_value('verification', **overrides); value.pop('evidence_slots')
    with no_write_attempts(), pytest.raises(ModelError) as caught: prepare_verification_contract(value)
    assert caught.value.reason == 'new_verification_draft_required'


def test_stored_contract_read_never_synthesizes_missing_slots():
    value = record_value('verification'); value.pop('evidence_slots')
    with no_write_attempts(), pytest.raises(ModelError): VerificationContract(artifact_bytes(value))


def test_every_declared_dimension_requires_an_actual_slot():
    value = record_value('verification', dimensions=['overall', 'safety'])
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        VerificationContract(artifact_bytes(value), path='contract.json')
    assert caught.value.reason == 'missing_verification_dimension_slot'
    assert caught.value.pointer == '/dimensions/1' and caught.value.path == 'contract.json'


@pytest.mark.parametrize('field', ['method', 'subjects', 'preconditions', 'procedure', 'oracle',
    'evidence_kinds', 'dimensions', 'configuration_policy'])
def test_incomplete_contracts_fail_without_synthesizing_required_data(field):
    value = record_value('verification'); value.pop(field)
    with no_write_attempts(), pytest.raises(ModelError): VerificationContract(artifact_bytes(value))


@pytest.mark.parametrize('change', [
    {'method': 'shell'}, {'configuration_policy': 'latest'},
    {'evidence_slots': [{'check_id': 'duplicate', 'test_id': None, 'dimension': 'overall'}] * 2},
    {'evidence_slots': [{'check_id': 'bad space', 'test_id': None, 'dimension': 'overall'}]},
    {'evidence_slots': [{'check_id': 'check', 'test_id': ref(), 'dimension': 'overall'}]}])
def test_invalid_local_contract_values_preserve_native_field_rejection(change):
    with no_write_attempts(), pytest.raises(ModelError):
        VerificationContract(artifact_bytes(record_value('verification', **change)))


@pytest.mark.parametrize('change', [{'test_identity': {}},
    {'test_identity': {'external_id': 'suite/case', 'path': 'test.py'}},
    {'test_identity': {'path': '../outside.py'}}, {'test_type': ''}, {'oracle': ''}])
def test_invalid_test_metadata_cannot_be_bound_as_a_successful_reference(change):
    records = referenced_test_records(); records[2].update(change)
    with no_write_attempts(), pytest.raises(ModelError):
        resolve_verification_contract(model(records), ref(), ref('VER'))


def test_slot_with_missing_test_fails_at_its_source_pointer():
    records = referenced_test_records(); records.pop()
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_verification_contract(model(records), ref(), ref('VER'))
    assert caught.value.reason == 'verification_test_not_found'
    assert caught.value.pointer == '/evidence_slots/0/test_id'
    assert caught.value.path == artifact_path('verification', ref('VER'), 'SR')


@pytest.mark.parametrize('change,reason', [('edge', 'verification_relation_required'),
    ('subject', 'verification_subject_not_declared'), ('missing', 'verification_subject_not_found')])
def test_contract_requires_actual_relation_and_resolvable_declared_subjects(change, reason):
    records = contract_records()
    if change == 'edge': records[0]['relations'] = []
    elif change == 'subject': records[1]['subjects'] = [ref('REQ', '1')]
    else: records[1]['subjects'].append(ref('REQ', '1'))
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_verification_contract(model(records), ref(), ref('VER'))
    assert caught.value.reason == reason


def test_direct_test_target_is_not_misreported_as_a_complete_explicit_contract():
    records = [domain_value('requirement', relations=[relation('verified_by', ref('TEST'))]),
               record_value('test')]
    with no_write_attempts(), pytest.raises(ModelError):
        resolve_verification_contract(model(records), ref(), ref('TEST'))


@pytest.mark.parametrize('offset', [1, 2])
def test_resolution_is_deterministic_under_supplied_file_order(offset):
    records = referenced_test_records(); expected = resolve_verification_contract(model(records), ref(), ref('VER'))
    result = resolve_verification_contract(model(records[offset:] + records[:offset]), ref(), ref('VER'))
    assert result.data == expected.data and result.sha256 == expected.sha256


def test_resolution_and_owned_records_do_not_expose_mutation_handles():
    records = referenced_test_records(); supplied = model(records)
    result = resolve_verification_contract(supplied, ref(), ref('VER')); before = result.data
    owned = [VerificationContract(artifact_bytes(records[1])), VerificationTest(artifact_bytes(records[2]))]
    for item in owned:
        original = item.data; raw = item.source_bytes
        item.data.clear(); item.binding['record'].clear()
        assert item.data == original and item.source_bytes == raw
        with pytest.raises(FrozenInstanceError): item.source_bytes = b'{}'
        with pytest.raises(TypeError): bool(item)
    records[1]['oracle'] = 'Changed'; result.data['required_checks'].clear()
    assert result.data == before
    with pytest.raises(FrozenInstanceError): result._encoded = b'{}'
    with pytest.raises(TypeError): bool(result)
    with pytest.raises(TypeError): VerificationContractResolution()


@pytest.mark.parametrize('position,field,value', [(0, 'statement', 'Changed subject'),
    (1, 'oracle', 'Different criterion'), (2, 'test_identity', {'external_id': 'suite/new-case'})])
def test_source_changes_are_bound_to_different_resolution_hashes(position, field, value):
    records = referenced_test_records(); first = resolve_verification_contract(model(records), ref(), ref('VER'))
    records[position][field] = value
    second = resolve_verification_contract(model(records), ref(), ref('VER'))
    assert first.sha256 != second.sha256
    assert first.data['input_sha256'] != second.data['input_sha256']


def test_owned_resolution_neither_reads_test_code_nor_changes_or_requires_live_files(tmp_path, monkeypatch):
    supplied = model(referenced_test_records()); root = tmp_path / 'project'
    for name, raw in supplied.source_files.items():
        path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    code = root / 'tests/device.py'; code.parent.mkdir(); code.write_text('raise RuntimeError("must not execute")')
    before = inventory(root)
    def no_read(*args, **kwargs): raise AssertionError('Contract resolution tried to read a file')
    with no_write_attempts(), monkeypatch.context() as patch:
        patch.setattr('builtins.open', no_read); patch.setattr('io.open', no_read)
        result = resolve_verification_contract(supplied, ref(), ref('VER'))
    assert inventory(root) == before
    shutil.rmtree(root)
    with no_write_attempts(): repeated = resolve_verification_contract(supplied, ref(), ref('VER'))
    assert repeated.data == result.data and not root.exists()


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_contract_resolution_has_identical_bindings_in_isolated_core_and_pyz(tmp_path, mode):
    supplied = model(referenced_test_records()); expected = resolve_verification_contract(supplied, ref(), ref('VER')).data
    body = '''import json
from specroad.changes import TargetModel
from specroad.verification import resolve_verification_contract
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument
'''
    body += 'config=' + repr(supplied.configuration_bytes) + '\n'
    body += 'documents=' + repr([(d.path, d.content) for d in supplied.documents]) + '\n'
    body += 'resources=' + repr([(d.path, d.content) for d in supplied.resource_files]) + '\n'
    body += 'core_key=' + repr(supplied.profile.profile_chain[0]) + '\n'
    body += '''profile=compose_profiles([ProfileResource(raw) for path,raw in resources],core_key=core_key)
owned=TargetModel(config,ProjectReadBinding('sample','/explicit/provider',(1,2)),
 [ModelDocument(path,raw) for path,raw in documents],profile=profile,
 resource_files=[ModelDocument(path,raw) for path,raw in resources])
'''
    body += 'print(json.dumps(resolve_verification_contract(owned,' + repr(ref()) + ',' + repr(ref('VER')) + ').data))\n'
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
