"""Bound measurements are immutable values, never write or approval authority."""
from dataclasses import FrozenInstanceError
import json

import pytest

from specroad.changes.values import ChangeOperation
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.identities import (ArtifactIdentity, IdentityAllocation,
    IdentityInventory, allocate_artifact_identity)
from specroad.storage.domain_artifact import DomainArtifact
from specroad.storage.record_artifact import RecordArtifact
from specroad.verification import (VerificationContract, VerificationTest,
    VerificationContext, assess_verification_context, prepare_evidence_record,
    verification_context_sha256)
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from support.records import record_value, ref
from test_verification_context import configuration


def inputs(*, with_test=False, policy='bound'):
    subjects = [DomainArtifact(artifact_bytes(domain_value('requirement')))]
    test = VerificationTest(artifact_bytes(record_value('test'))) if with_test else None
    slot = {'check_id': 'measurement', 'test_id': None if test is None else test.data['id'],
            'dimension': 'overall'}
    contract = VerificationContract(artifact_bytes(record_value('verification',
        evidence_slots=[slot], configuration_policy=policy)))
    current = [subjects[0].id, contract.data['id']]
    if test is not None:
        current.append(test.data['id'])
    identity = ArtifactIdentity(ref('EVD', '1'), 'random128-v1', 'evidence', 'SR')
    allocation = IdentityAllocation(identity, IdentityInventory('SR', current, [], [identity.id]))
    arguments = {'allocation': allocation, 'configuration': configuration(),
        'actor': {'actor_type': 'human', 'actor_id': 'recorder'},
        'planned_at': '2026-10-19T19:00:00Z', 'title': 'Bound measurement',
        'result': 'failed', 'produced_at': '2026-10-19T18:59:00Z',
        'producer': {'producer_type': 'ci', 'producer_id': 'test-ci'},
        'tool': {'name': 'runner', 'version': '2.1'},
        'environment': {'platform': 'synthetic', 'inputs': [1, {'value': 'original'}]},
        'origin': 'generated_internal',
        'run_context': {'subject_id': 'measured-product', 'subject_state_sha256': 'c' * 64,
                        'run_id': 'test-ci:measurement-1',
                        'check_id': slot['check_id'], 'test_id': slot['test_id']}, 'test': test}
    return subjects, contract, arguments


@pytest.mark.parametrize('with_test', [False, True])
def test_complete_measurement_is_created_in_one_recorded_approved_value(with_test):
    subjects, contract, args = inputs(with_test=with_test)
    before = [subject.source_bytes for subject in subjects] + [contract.source_bytes]
    with no_write_attempts():
        record = prepare_evidence_record(subjects, contract, **args)
    data = record.data
    assert data['id'] == args['allocation'].identity.id
    assert data['id_scheme'] == 'random128-v1'
    assert (data['maturity'], data['evidence_state'], data['revision']) == ('approved', 'recorded', 1)
    assert data['created_at'] == data['updated_at'] == args['planned_at']
    assert data['created_by'] == data['updated_by'] == args['actor']
    for field in ('title', 'result', 'produced_at', 'producer', 'tool', 'environment', 'origin', 'run_context'):
        assert data[field] == args[field]
    assert data['configuration_hash'] == args['configuration'].sha256
    assert data['configuration_policy'] == 'bound'
    assert data['relations'] == [] and data['extensions'] == {}
    bound = [*subjects, contract] + ([] if args['test'] is None else [args['test']])
    assert [item['artifact_id'] for item in data['subjects']] == sorted(value.data['id'] for value in bound)
    for value in bound:
        binding = next(item for item in data['subjects'] if item['artifact_id'] == value.data['id'])
        assert binding == {'artifact_id': value.data['id'], 'revision': value.data['revision'],
            'artifact_sha256': canonical_json_sha256(value.data),
            'verification_context_sha256': verification_context_sha256(value)}
    assert RecordArtifact(record.source_bytes, expected_type='evidence').data == data
    assert before == [subject.source_bytes for subject in subjects] + [contract.source_bytes]
    assert 'verification_result' not in data and 'human_review_id' not in data


def test_new_measurement_uses_new_allocation_and_retains_old_immutable_bytes(monkeypatch):
    subjects, contract, args = inputs()
    inventory = args['allocation'].inventory
    # Force a collision with the first reservation on the second allocation.
    values = iter([b'\x02' * 16, b'\x02' * 16, b'\x03' * 16])
    monkeypatch.setattr('specroad.model.identities.secrets.token_bytes', lambda count: next(values))
    first_allocation = allocate_artifact_identity('evidence', inventory)
    first = prepare_evidence_record(subjects, contract, **{**args, 'allocation': first_allocation})
    original = first.source_bytes
    second_allocation = allocate_artifact_identity('evidence', first_allocation.inventory)
    second = prepare_evidence_record(subjects, contract, **{**args, 'allocation': second_allocation,
        'run_context': {**args['run_context'], 'run_id': 'test-ci:measurement-2'}, 'result': 'passed'})
    assert first.id != second.id and first.source_bytes == original
    assert first.id in second_allocation.inventory.reserved_ids
    assert second.id in second_allocation.inventory.reserved_ids
    assert first.id not in inventory.reserved_ids and second.id not in inventory.reserved_ids
    assert first.data['result'] == 'failed' and second.data['result'] == 'passed'


def test_same_prepared_input_is_deterministic_without_another_allocation_or_clock(monkeypatch):
    subjects, contract, args = inputs()
    first = prepare_evidence_record(subjects, contract, **args)
    def forbidden(*args, **kwargs): raise AssertionError('Unexpected external input')
    with no_write_attempts(), monkeypatch.context() as patch:
        for name in ('time.time', 'builtins.open', 'io.open', 'subprocess.Popen', 'socket.socket',
                     'specroad.model.identities.secrets.token_bytes'):
            patch.setattr(name, forbidden)
        second = prepare_evidence_record(subjects, contract, **args)
    assert second.source_bytes == first.source_bytes


def test_subjects_can_be_a_subset_and_order_does_not_change_evidence_bytes():
    subjects, contract, args = inputs()
    other = DomainArtifact(artifact_bytes(domain_value('requirement', id=ref('REQ', '2'))))
    contract = VerificationContract(artifact_bytes({**contract.data, 'subjects': [subjects[0].id, other.id]}))
    allocation = args['allocation']
    args['allocation'] = IdentityAllocation(allocation.identity,
        IdentityInventory('SR', [subjects[0].id, other.id, contract.data['id']], [], [allocation.identity.id]))
    subset = prepare_evidence_record(subjects, contract, **args)
    assert other.id not in {item['artifact_id'] for item in subset.data['subjects']}
    first = prepare_evidence_record([*subjects, other], contract, **args)
    second = prepare_evidence_record([other, *subjects], contract, **args)
    assert first.source_bytes == second.source_bytes


@pytest.mark.parametrize('outcome', ['passed', 'failed', 'incomplete', 'skipped'])
def test_result_is_preserved_without_successful_default_or_run_execution(outcome):
    subjects, contract, args = inputs()
    record = prepare_evidence_record(subjects, contract, **{**args, 'result': outcome})
    observation = assess_verification_context(
        VerificationContext(subjects[0], configuration=args['configuration']), record, contract=contract).data
    assert record.data['result'] == observation['evidence_result'] == outcome
    assert observation['freshness'] == 'current'
    assert observation['full_verification_evaluated'] is False
    assert observation['test_code_executed'] is False and observation['approval_granted'] is False
    assert observation['write_authorized'] is False


@pytest.mark.parametrize('origin', ['recorded_manual', 'generated_internal', 'imported_junit', 'imported_sarif', 'imported_generic'])
def test_explicit_origin_is_data_and_does_not_change_result(origin):
    subjects, contract, args = inputs()
    record = prepare_evidence_record(subjects, contract, **{**args, 'origin': origin})
    assert record.data['origin'] == origin and record.data['result'] == 'failed'


@pytest.mark.parametrize('producer_type', ['human', 'tool', 'ci', 'monitoring', 'ai'])
def test_declared_producer_does_not_replace_result_or_audit_actor(producer_type):
    subjects, contract, args = inputs()
    args['producer']['producer_type'] = producer_type
    record = prepare_evidence_record(subjects, contract, **args)
    assert record.data['producer'] == args['producer']
    assert record.data['created_by'] == args['actor']
    assert record.data['result'] == 'failed'
    assert 'reviewer' not in record.data and 'human_review_id' not in record.data


def test_independent_configuration_is_taken_only_from_contract():
    subjects, contract, args = inputs(policy='independent')
    record = prepare_evidence_record(subjects, contract, **{**args, 'configuration': None})
    assert record.data['configuration_hash'] is None and record.data['configuration_policy'] == 'independent'
    observed = assess_verification_context(
        VerificationContext(subjects[0], configuration=configuration('windows')), record, contract=contract).data
    assert observed['freshness'] == 'current' and observed['contract_configuration_independent']


def test_bound_configuration_cannot_be_omitted_or_inferred():
    subjects, contract, args = inputs()
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        prepare_evidence_record(subjects, contract, **{**args, 'configuration': None})
    assert caught.value.reason == 'missing_configuration_binding'


def test_supplied_nested_values_and_returned_data_cannot_mutate_record():
    subjects, contract, args = inputs(with_test=True)
    record = prepare_evidence_record(subjects, contract, **args)
    raw = record.source_bytes
    for name in ('producer', 'tool', 'environment', 'run_context', 'actor'):
        args[name].clear()
    record.data['subjects'].clear()
    record.data.clear()
    subjects[0].data.clear(); contract.data.clear(); args['test'].data.clear()
    assert record.source_bytes == raw
    assert record.data['environment']['inputs'][1]['value'] == 'original'
    with pytest.raises(FrozenInstanceError): record.source_bytes = b'{}'


@pytest.mark.parametrize('field,value', [
    ('result', ''), ('origin', 'unknown'), ('producer', {}),
    ('producer', {'producer_type': 'ci', 'producer_id': 'test-ci', 'extra': True}),
    ('tool', {'name': 'runner'}), ('environment', 'synthetic'),
    ('produced_at', '2026-10-19T18:59:00+00:00'), ('planned_at', 'today'),
    ('run_context', None), ('run_context', {}), ('run_context', 'latest'),
    ('configuration', {}), ('allocation', {}), ('test', {})])
def test_incomplete_or_untyped_inputs_fail_without_partial_record(field, value):
    subjects, contract, args = inputs()
    before = (subjects[0].source_bytes, contract.source_bytes, args['allocation'])
    with no_write_attempts(), pytest.raises(ModelError):
        prepare_evidence_record(subjects, contract, **{**args, field: value})
    assert before == (subjects[0].source_bytes, contract.source_bytes, args['allocation'])


@pytest.mark.parametrize('field,value', [('run_id', ''), ('subject_id', ''),
    ('subject_state_sha256', 'HEAD'), ('check_id', 'other'), ('extra', True)])
def test_missing_or_foreign_run_bindings_are_not_guessed(field, value):
    subjects, contract, args = inputs()
    args['run_context'][field] = value
    with no_write_attempts(), pytest.raises(ModelError): prepare_evidence_record(subjects, contract, **args)


@pytest.mark.parametrize('case', ['missing', 'extra', 'foreign'])
def test_check_slot_requires_the_exact_optional_test(case):
    subjects, contract, args = inputs(with_test=case != 'extra')
    if case == 'missing': args['test'] = None
    elif case == 'extra': args['test'] = VerificationTest(artifact_bytes(record_value('test')))
    else: args['test'] = VerificationTest(artifact_bytes(record_value('test', id=ref('TEST', '2'))))
    # Include supplied identities so this tests the check binding, not inventory membership.
    allocation = args['allocation']
    current = set(allocation.inventory.current_ids)
    if args['test'] is not None: current.add(args['test'].data['id'])
    args['allocation'] = IdentityAllocation(allocation.identity,
        IdentityInventory('SR', current, [], [allocation.identity.id]))
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        prepare_evidence_record(subjects, contract, **args)
    assert caught.value.reason == 'evidence_test_binding_mismatch'


@pytest.mark.parametrize('case', ['empty', 'duplicate', 'untyped', 'other_kind', 'undeclared', 'not_current'])
def test_only_explicit_current_declared_requirement_subjects_are_bound(case):
    subjects, contract, args = inputs()
    if case == 'empty': subjects = []
    elif case == 'duplicate': subjects *= 2
    elif case == 'untyped': subjects = [subjects[0].data]
    elif case == 'other_kind': subjects = [DomainArtifact(artifact_bytes(domain_value('task')))]
    elif case == 'undeclared': subjects = [DomainArtifact(artifact_bytes(domain_value('requirement', id=ref('REQ', '2'))))]
    else:
        allocation = args['allocation']
        args['allocation'] = IdentityAllocation(allocation.identity,
            IdentityInventory('SR', [contract.data['id']], [subjects[0].id], [allocation.identity.id]))
    with no_write_attempts(), pytest.raises(ModelError): prepare_evidence_record(subjects, contract, **args)


def test_identity_reserved_for_another_artifact_type_cannot_create_evidence():
    subjects, contract, args = inputs()
    identity = ArtifactIdentity(ref('TEST', '2'), 'random128-v1', 'test', 'SR')
    args['allocation'] = IdentityAllocation(identity,
        IdentityInventory('SR', args['allocation'].inventory.current_ids, [], [identity.id]))
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        prepare_evidence_record(subjects, contract, **args)
    assert caught.value.reason == 'new_evidence_identity_required'


def test_bound_value_is_accepted_by_existing_evidence_operation_contract():
    subjects, contract, args = inputs()
    record = prepare_evidence_record(subjects, contract, **args)
    operation = ChangeOperation({'op': 'evidence_record', 'evidence': record.data})
    assert operation.data['evidence'] == record.data


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_constructor_has_identical_output_in_isolated_core_and_pyz(tmp_path, mode):
    subjects, contract, args = inputs()
    expected = prepare_evidence_record(subjects, contract, **args).data
    body = '''import json
from specroad.configurations import resolve_configuration
from specroad.graph.relations import SourceRelations
from specroad.model.identities import ArtifactIdentity, IdentityAllocation, IdentityInventory
from specroad.storage.domain_artifact import DomainArtifact
from specroad.verification import VerificationContract, prepare_evidence_record
'''
    body += 'subjects=[DomainArtifact(' + repr(subjects[0].source_bytes) + ')]\n'
    body += 'contract=VerificationContract(' + repr(contract.source_bytes) + ')\n'
    body += 'cfg=SourceRelations(' + repr(artifact_bytes(record_value('configuration'))) + ')\n'
    body += 'identity=ArtifactIdentity(' + repr(args['allocation'].identity.id) + ',"random128-v1","evidence","SR")\n'
    body += 'allocation=IdentityAllocation(identity,IdentityInventory("SR",[subjects[0].id,contract.data["id"]],[],[identity.id]))\n'
    plain = {key: value for key, value in args.items() if key not in ('allocation', 'configuration')}
    body += 'args=' + repr(plain) + '\n'
    body += 'record=prepare_evidence_record(subjects,contract,allocation=allocation,configuration=resolve_configuration([cfg],cfg.identity.id),**args)\n'
    body += 'print(json.dumps(record.data))\n'
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
