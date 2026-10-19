"""Implicit test contracts and hostile/incomplete verification inputs."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
import shutil

import pytest

from specroad.changes import TargetModel
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.validation import ModelDocument
from specroad.verification import resolve_verification_contract, resolve_verification_target
from support.domain import domain_value, relation
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import record_value, ref
from support.targets import model, SCOPE
from test_verification_contracts import contract_records, referenced_test_records


def direct_test_records(**overrides):
    test = record_value('test', **overrides)
    return [domain_value('requirement', relations=[relation('verified_by', test['id'])]), test]


@pytest.mark.parametrize('identity', [{'external_id': 'suite/stable-case'}, {'path': 'tests/offline.py'}])
@pytest.mark.parametrize('oracle', ['Required observable behavior', {'expected': {'state': 'safe'}}])
def test_direct_test_materializes_exact_normative_overall_identity_without_inventing_a_record(identity, oracle):
    records = direct_test_records(test_identity=identity, oracle=oracle, test_type='manual')
    supplied = model(records); before = supplied.source_files
    with no_write_attempts(): result = resolve_verification_target(supplied, ref(), ref('TEST'))
    data = result.data
    assert data['implicit_contract'] == {'contract_id': ref('TEST'), 'test_id': ref('TEST'),
        'dimensions': ['overall'],
        'evidence_slots': [{'check_id': 'overall', 'test_id': ref('TEST'), 'dimension': 'overall'}]}
    assert data['required_checks'] == [{'subject_artifact_id': ref(), 'contract_id': ref('TEST'),
        'test_id': ref('TEST'), 'check_id': 'overall', 'dimension': 'overall'}]
    assert data['contract'] == data['tests'][0]
    assert data['contract']['artifact_type'] == 'test' and data['contract']['record'] == records[1]
    assert data['validation_scope'] == 'supplied_model_implicit_test_contract'
    assert 'method' not in data['implicit_contract'] and 'configuration_policy' not in data['implicit_contract']
    assert data['scope_descriptor'] == SCOPE
    assert data['input_sha256'] == supplied._sources_sha256
    assert data['model_root_sha256'] == supplied.manifest(supplied.artifacts, SCOPE).sha256
    for binding in (data['subject'], data['contract']):
        value = binding['record']; path = artifact_path(value['artifact_type'], value['id'], 'SR')
        assert binding['path'] == path and binding['revision'] == value['revision']
        assert binding['source_sha256'] == sha256(before[path]).hexdigest()
        assert binding['record_sha256'] == canonical_json_sha256(value)
    assert not any(data[key] for key in ('project_files_verified', 'full_validation_passed',
        'project_required_checks_complete', 'configuration_applicability_evaluated',
        'evidence_evaluated', 'test_code_executed', 'write_authorized', 'approval_granted'))
    assert supplied.source_files == before


def test_explicit_target_delegates_without_changing_existing_contract_results():
    supplied = model(referenced_test_records())
    with no_write_attempts():
        expected = resolve_verification_contract(supplied, ref(), ref('VER'))
        result = resolve_verification_target(supplied, ref(), ref('VER'))
    assert result.data == expected.data and result.sha256 == expected.sha256


def test_mixed_explicit_and_direct_targets_have_distinct_pair_keys_without_a_project_success_claim():
    records = referenced_test_records()
    records[0]['relations'].append(dict(relation('verified_by', ref('TEST')), relation_id='REL-' + '1' * 26))
    supplied = model(records)
    explicit = resolve_verification_target(supplied, ref(), ref('VER')).data
    direct = resolve_verification_target(supplied, ref(), ref('TEST')).data
    checks = explicit['required_checks'] + direct['required_checks']
    assert len(checks) == len({tuple(item[k] for k in
        ('subject_artifact_id', 'contract_id', 'test_id', 'check_id')) for item in checks}) == 4
    assert direct['relations'][0]['pointer'] == '/relations/1'
    assert direct['relations'][0]['record'] == records[0]['relations'][1]
    assert direct['relations'][0]['record_sha256'] == canonical_json_sha256(records[0]['relations'][1])
    assert explicit['project_required_checks_complete'] is direct['project_required_checks_complete'] is False


def test_shared_direct_test_does_not_merge_required_checks_of_different_subjects():
    records = direct_test_records()
    records.append(domain_value('requirement', id=ref('REQ', '1'), relations=[
        dict(relation('verified_by', ref('TEST')), relation_id='REL-' + '1' * 26)]))
    supplied = model(records)
    results = [resolve_verification_target(supplied, ref('REQ', token), ref('TEST')).data for token in ('0', '1')]
    assert results[0]['contract'] == results[1]['contract']
    assert results[0]['required_checks'][0]['subject_artifact_id'] == ref()
    assert results[1]['required_checks'][0]['subject_artifact_id'] == ref('REQ', '1')
    assert results[0]['required_checks'] != results[1]['required_checks']


def test_only_the_actual_test_artifact_id_selects_the_contract_not_equal_external_metadata():
    records = direct_test_records()
    records.append(record_value('test', id=ref('TEST', '1')))
    supplied = model(records)
    assert resolve_verification_target(supplied, ref(), ref('TEST')).data['contract']['artifact_id'] == ref('TEST')
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_verification_target(supplied, ref(), ref('TEST', '1'))
    assert caught.value.reason == 'verification_relation_required'


@pytest.mark.parametrize('field', ['test_identity', 'test_type', 'oracle'])
def test_direct_test_cannot_hide_missing_required_metadata_behind_implicit_defaults(field):
    records = direct_test_records(); records[1].pop(field)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_verification_target(model(records), ref(), ref('TEST'))
    assert caught.value.path == artifact_path('test', ref('TEST'), 'SR')


@pytest.mark.parametrize('identity', [None, {}, {'external_id': ''}, {'path': ''},
    {'external_id': 'case', 'path': 'test.py'}, {'external_id': 7},
    {'path': '/tmp/test.py'}, {'path': '../test.py'}, {'path': 'a/../test.py'},
    {'path': 'tests\\test.py'}])
def test_malformed_test_identities_are_rejected_for_direct_targets(identity):
    records = direct_test_records(test_identity=identity)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_verification_target(model(records), ref(), ref('TEST'))
    assert caught.value.path == artifact_path('test', ref('TEST'), 'SR')


@pytest.mark.parametrize('test_id', ['', 0, False, [], {}, ref(), 'SR-TEST-' + 'z' * 26])
def test_explicit_slots_reject_invalid_test_ids_instead_of_converting_them_to_null(test_id):
    records = contract_records(evidence_slots=[{'check_id': 'check', 'test_id': test_id, 'dimension': 'overall'}])
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_verification_target(model(records), ref(), ref('VER'))
    assert caught.value.path == artifact_path('verification', ref('VER'), 'SR')


@pytest.mark.parametrize('change', [
    {'dimensions': ['overall', 'mandatory']},
    {'dimensions': ['overall', 'overall']},
    {'dimensions': []}, {'dimensions': None},
    {'evidence_slots': [{'check_id': 'other', 'test_id': None, 'dimension': 'undeclared'}]},
    {'evidence_slots': [{'check_id': 'overall', 'test_id': None, 'dimension': 'overall', 'optional': True}]},
    {'evidence_slots': [{'check_id': 'overall', 'test_id': None}]},
    {'evidence_slots': [{'check_id': 'overall', 'dimension': 'overall'}]},
    {'evidence_slots': []}])
def test_incomplete_or_selectively_optional_contracts_never_resolve_a_partial_success(change):
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_verification_target(model(contract_records(**change)), ref(), ref('VER'))
    assert caught.value.path == artifact_path('verification', ref('VER'), 'SR')


@pytest.mark.parametrize('check_id', ['a', 'a' * 128, 'check.part:1-2_3'])
def test_normative_check_id_boundaries_preserve_required_identity(check_id):
    records = contract_records(evidence_slots=[{'check_id': check_id, 'test_id': None, 'dimension': 'overall'}])
    result = resolve_verification_target(model(records), ref(), ref('VER'))
    assert result.data['required_checks'][0]['check_id'] == check_id


@pytest.mark.parametrize('check_id', ['', 'a' * 129, '_prefix', 'é', 'line\nbreak'])
def test_outside_check_id_boundaries_are_not_sanitized_to_another_check(check_id):
    records = contract_records(evidence_slots=[{'check_id': check_id, 'test_id': None, 'dimension': 'overall'}])
    with no_write_attempts(), pytest.raises(ModelError):
        resolve_verification_target(model(records), ref(), ref('VER'))


@pytest.mark.parametrize('missing', ['subject', 'target'])
def test_missing_subject_or_target_has_an_input_location_and_no_fallback(missing):
    supplied = model(direct_test_records())
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_verification_target(supplied, ref('REQ', '1') if missing == 'subject' else ref(),
                                    ref('TEST', '1') if missing == 'target' else ref('TEST'))
    assert caught.value.reason == 'verification_artifact_not_found'
    assert caught.value.pointer == '/' + missing + '_id'


@pytest.mark.parametrize('value', [None, {}, [], True, 7])
@pytest.mark.parametrize('field', ['subject_id', 'target_id'])
def test_nonstring_lookup_arguments_are_typed_errors(value, field):
    supplied = model(direct_test_records()); args = {'subject_id': ref(), 'target_id': ref('TEST')}; args[field] = value
    with no_write_attempts(), pytest.raises(ModelError) as caught: resolve_verification_target(supplied, **args)
    assert caught.value.reason == 'artifact_id_required' and caught.value.pointer == '/' + field


@pytest.mark.parametrize('value', [None, {}, [], b'{}'])
def test_unowned_model_values_cannot_supply_contract_authority(value):
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_verification_target(value, ref(), ref('TEST'))
    assert caught.value.reason == 'verification_target_model_required'


def test_nonverification_target_is_not_promoted_to_an_implicit_contract():
    records = direct_test_records(); records.append(record_value('source'))
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_verification_target(model(records), ref(), ref('SRC'))
    assert caught.value.reason == 'verification_or_test_target_required'


def test_direct_target_requires_verified_by_instead_of_an_unrelated_edge():
    records = direct_test_records(); records[0]['relations'] = []
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_verification_target(model(records), ref(), ref('TEST'))
    assert caught.value.reason == 'verification_relation_required' and caught.value.pointer == '/relations'


@pytest.mark.parametrize('defect', ['duplicate_relation_id', 'missing_target', 'invalid_type_pair'])
def test_native_relation_boundaries_still_apply_to_implicit_contracts(defect):
    records = direct_test_records()
    if defect == 'duplicate_relation_id':
        records.append(domain_value('requirement', id=ref('REQ', '1'), relations=[relation('verified_by', ref('TEST'))]))
    elif defect == 'missing_target':
        records[0]['relations'].append(dict(relation('derived_from', ref('SRC')), relation_id='REL-' + '1' * 26))
    else:
        records[0] = record_value('test', id=ref('TEST', '1'), relations=[relation('verified_by', ref('TEST'))])
    with no_write_attempts(), pytest.raises(ModelError):
        resolve_verification_target(model(records), records[0]['id'], ref('TEST'))


def test_actual_test_bytes_override_tampered_model_caches_and_preserve_original_format_binding():
    records = direct_test_records(); original = model(records)
    docs = [ModelDocument(d.path, b' \n' + d.content + b'\n') for d in original.documents]
    supplied = TargetModel(original.configuration_bytes, original.binding, docs,
                           profile=original.profile, resource_files=original.resource_files)
    expected = resolve_verification_target(supplied, ref(), ref('TEST'))
    object.__setattr__(supplied, 'configuration', None)
    object.__setattr__(supplied, 'resources', ())
    result = resolve_verification_target(supplied, ref(), ref('TEST'))
    assert result.data == expected.data and result.sha256 == expected.sha256
    canonical = resolve_verification_target(original, ref(), ref('TEST'))
    assert result.data['contract']['record_sha256'] == canonical.data['contract']['record_sha256']
    assert result.data['contract']['source_sha256'] != canonical.data['contract']['source_sha256']


@pytest.mark.parametrize('change', ['source_bytes', 'source_hash'])
def test_changed_source_binding_cannot_be_reused_for_implicit_checks(change):
    supplied = model(direct_test_records())
    if change == 'source_bytes':
        first = supplied.documents[0]
        object.__setattr__(supplied, 'documents',
            (ModelDocument(first.path, first.content + b'\n'), *supplied.documents[1:]))
    else:
        object.__setattr__(supplied, '_sources_sha256', 'f' * 64)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_verification_target(supplied, ref(), ref('TEST'))
    assert caught.value.reason == 'target_sources_changed'


def test_implicit_projection_is_owned_and_does_not_change_its_test_record():
    records = direct_test_records(); before = deepcopy(records)
    result = resolve_verification_target(model(records), ref(), ref('TEST')); expected = result.data
    result.data['implicit_contract']['evidence_slots'].clear(); result.data['contract']['record'].clear()
    records[1]['oracle'] = 'Caller mutation'
    assert result.data == expected and result.data['contract']['record'] == before[1]
    with pytest.raises(FrozenInstanceError): result._encoded = b'{}'
    with pytest.raises(TypeError): bool(result)


@pytest.mark.parametrize('change', ['identity', 'oracle', 'revision'])
def test_changed_test_metadata_produces_a_different_implicit_binding(change):
    records = direct_test_records(); before = resolve_verification_target(model(records), ref(), ref('TEST'))
    if change == 'identity': records[1]['test_identity'] = {'external_id': 'suite/changed'}
    elif change == 'oracle': records[1]['oracle'] = 'Changed criterion'
    else: records[1]['revision'] = 2
    after = resolve_verification_target(model(records), ref(), ref('TEST'))
    assert before.sha256 != after.sha256
    assert before.data['contract']['record_sha256'] != after.data['contract']['record_sha256']


def test_input_order_does_not_change_implicit_contract_bindings():
    records = direct_test_records(); first = resolve_verification_target(model(records), ref(), ref('TEST'))
    second = resolve_verification_target(model(list(reversed(records))), ref(), ref('TEST'))
    assert first.data == second.data and first.sha256 == second.sha256


def test_implicit_resolution_never_reads_or_runs_code_and_survives_loss_of_live_files(tmp_path, monkeypatch):
    supplied = model(direct_test_records(test_identity={'path': 'test.py'})); root = tmp_path / 'project'
    for name, raw in supplied.source_files.items():
        path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    (root / 'test.py').write_text('raise RuntimeError("must not execute")')
    before = inventory(root)
    def no_read(*args, **kwargs): raise AssertionError('Implicit contract tried to read a file')
    with no_write_attempts(), monkeypatch.context() as patch:
        patch.setattr('builtins.open', no_read); patch.setattr('io.open', no_read)
        result = resolve_verification_target(supplied, ref(), ref('TEST'))
    assert inventory(root) == before
    shutil.rmtree(root)
    with no_write_attempts(): repeated = resolve_verification_target(supplied, ref(), ref('TEST'))
    assert repeated.data == result.data and not root.exists()


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_implicit_contract_bindings_are_identical_in_fresh_core_and_pyz(mode, tmp_path):
    supplied = model(direct_test_records()); expected = resolve_verification_target(supplied, ref(), ref('TEST')).data
    body = '''import json
from specroad.changes import TargetModel
from specroad.verification import resolve_verification_target
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
    body += 'print(json.dumps(resolve_verification_target(owned,' + repr(ref()) + ',' + repr(ref('TEST')) + ').data))\n'
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
