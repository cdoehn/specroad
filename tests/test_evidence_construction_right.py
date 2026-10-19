"""Unknown provenance and immutable records never become write/approval gates."""
from dataclasses import FrozenInstanceError
import json

import pytest

from specroad.changes import (AuthoringError, ChangePlanError, prepare_authoring_request,
    prepare_change_target, prepare_format_target)
from specroad.changes.values import ChangeOperation
from specroad.model.errors import ModelError
from specroad.model.identities import ArtifactIdentity, IdentityAllocation, IdentityInventory
from specroad.storage.record_artifact import RecordArtifact
from specroad.verification import (VerificationContract, VerificationTest, VerificationContext,
    assess_verification_context, prepare_evidence_record)
from support.artifacts import artifact_bytes
from support.normalization import FIELDS, operation as normalization_operation
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts, inventory
from support.records import record_value, ref
from support.targets import model, POLICY
from test_evidence_construction import inputs


def unknown_inputs(**options):
    subjects, contract, args = inputs(**options)
    args.update(run_context=None, unbound_reason='The measured product inputs were not retained.')
    return subjects, contract, args


@pytest.mark.parametrize('with_test', [False, True])
@pytest.mark.parametrize('policy', ['bound', 'independent'])
@pytest.mark.parametrize('outcome', ['passed', 'failed'])
def test_unknown_product_stays_explicitly_unbound_without_losing_measurement(with_test, policy, outcome):
    subjects, contract, args = unknown_inputs(with_test=with_test, policy=policy)
    args['result'] = outcome
    if policy == 'independent': args['configuration'] = None
    before = (subjects[0].source_bytes, contract.source_bytes)
    with no_write_attempts(): record = prepare_evidence_record(subjects, contract, **args)
    data = record.data
    assert data['run_context'] is None and data['unbound_reason'] == args['unbound_reason']
    assert data['result'] == outcome and data['producer'] == args['producer']
    assert data['configuration_policy'] == policy
    assert data['configuration_hash'] == (None if policy == 'independent' else args['configuration'].sha256)
    assert len(data['subjects']) == (3 if with_test else 2)
    assert {item['artifact_id'] for item in data['subjects']} == {
        subjects[0].id, contract.data['id'], *([] if not with_test else [args['test'].data['id']])}
    assert (data['evidence_state'], data['maturity'], data['revision']) == ('recorded', 'approved', 1)
    assert 'subject_state_sha256' not in data and 'verification_result' not in data
    assert before == (subjects[0].source_bytes, contract.source_bytes)
    assert RecordArtifact(record.source_bytes, expected_type='evidence').data == data
    assert ChangeOperation({'op': 'evidence_record', 'evidence': data}).data['evidence'] == data


@pytest.mark.parametrize('reason', [None, '', ' ', '\t\r\n', '\u2003', 0, False, {}, []])
def test_unknown_run_requires_a_real_explicit_reason(reason):
    subjects, contract, args = unknown_inputs()
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        prepare_evidence_record(subjects, contract, **{**args, 'unbound_reason': reason})
    expected = 'bound_evidence_run_context_required' if reason is None else 'evidence_unbound_reason_required'
    assert caught.value.reason == expected


def test_reason_is_owned_and_preserved_without_trimming_or_interpretation():
    subjects, contract, args = unknown_inputs()
    reason = '  Producer retained no input manifest; do not use current HEAD.\n'
    args['unbound_reason'] = reason
    record = prepare_evidence_record(subjects, contract, **args)
    args['unbound_reason'] = 'Other reason'
    record.data['unbound_reason'] = 'Changed'
    assert record.data['unbound_reason'] == reason and record.data['run_context'] is None
    with pytest.raises(FrozenInstanceError): record.source_bytes = b'{}'


@pytest.mark.parametrize('reason', ['Unknown run', '', False])
def test_known_run_cannot_simultaneously_claim_unknown_provenance(reason):
    subjects, contract, args = inputs()
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        prepare_evidence_record(subjects, contract, **{**args, 'unbound_reason': reason})
    assert caught.value.reason == 'bound_evidence_has_unbound_reason'
    assert caught.value.pointer == '/unbound_reason'


@pytest.mark.parametrize('field', ['subject_id', 'subject_state_sha256', 'run_id', 'check_id', 'test_id'])
def test_partial_run_is_rejected_without_downgrading_or_filling_fields(field):
    subjects, contract, args = inputs()
    args['run_context'].pop(field)
    for extra in ({}, {'unbound_reason': 'Some source fields are missing'}):
        with no_write_attempts(), pytest.raises(ModelError):
            prepare_evidence_record(subjects, contract, **{**args, **extra})
    assert field not in args['run_context']


def test_unknown_check_does_not_select_the_first_test_or_required_slot():
    subjects, contract, args = unknown_inputs(with_test=True)
    value = contract.data
    value['evidence_slots'].append({'check_id': 'second', 'test_id': ref('TEST', '2'), 'dimension': 'overall'})
    contract = VerificationContract(artifact_bytes(value))
    args['test'] = None
    record = prepare_evidence_record(subjects, contract, **args)
    assert record.data['run_context'] is None
    assert {entry['artifact_id'] for entry in record.data['subjects']} == {subjects[0].id, contract.data['id']}


def test_supplied_test_still_requires_membership_in_the_explicit_contract():
    subjects, contract, args = unknown_inputs()
    args['test'] = VerificationTest(artifact_bytes(record_value('test')))
    allocation = args['allocation']
    args['allocation'] = IdentityAllocation(allocation.identity, IdentityInventory('SR',
        [*allocation.inventory.current_ids, args['test'].data['id']], [], [allocation.identity.id]))
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        prepare_evidence_record(subjects, contract, **args)
    assert caught.value.reason == 'evidence_test_binding_mismatch'
    assert caught.value.pointer == '/subjects'


def test_unknown_run_does_not_disable_bound_configuration_requirement():
    subjects, contract, args = unknown_inputs()
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        prepare_evidence_record(subjects, contract, **{**args, 'configuration': None})
    assert caught.value.reason == 'missing_configuration_binding'


def test_matching_subject_context_never_proves_an_unbound_measurement_is_current_run():
    subjects, contract, args = unknown_inputs()
    record = prepare_evidence_record(subjects, contract, **{**args, 'result': 'passed'})
    context = VerificationContext(subjects[0], configuration=args['configuration'])
    with no_write_attempts(): observation = assess_verification_context(context, record).data
    assert observation['context_current'] and observation['run_context'] is None
    assert observation['run_selection_evaluated'] is False
    assert observation['full_verification_evaluated'] is False
    assert observation['approval_granted'] is False and observation['write_authorized'] is False
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        assess_verification_context(context, record, contract=contract)
    assert caught.value.reason == 'verification_contract_check_required'


def test_missing_provenance_is_never_read_from_clock_files_processes_or_network(monkeypatch):
    subjects, contract, args = unknown_inputs()
    expected = prepare_evidence_record(subjects, contract, **args).source_bytes
    def forbidden(*args, **kwargs): raise AssertionError('Unexpected external input')
    with no_write_attempts(), monkeypatch.context() as patch:
        for name in ('time.time', 'builtins.open', 'io.open', 'subprocess.Popen', 'socket.socket',
                     'specroad.model.identities.secrets.token_bytes'):
            patch.setattr(name, forbidden)
        actual = prepare_evidence_record(subjects, contract, **args)
    assert actual.source_bytes == expected and actual.data['run_context'] is None


@pytest.mark.parametrize('origin', ['recorded_manual', 'generated_internal', 'imported_junit', 'imported_sarif', 'imported_generic'])
def test_ai_origin_keeps_ai_audit_and_cannot_authorize_record_or_human_review(origin):
    subjects, contract, args = inputs()
    args.update(origin=origin, result='passed', actor={'actor_type': 'ai', 'actor_id': 'test-agent'},
                producer={'producer_type': 'ai', 'producer_id': 'test-agent'},
                run_context={**args['run_context'], 'run_id': 'test-agent:run-1'})
    record = prepare_evidence_record(subjects, contract, **args)
    before = record.source_bytes
    assert record.data['created_by'] == record.data['updated_by'] == args['actor']
    assert record.data['producer'] == args['producer']
    assert record.data['maturity'] == 'approved' and record.data['result'] == 'passed'
    for command, reason in (('evidence record', 'ai_requires_proposal'),
                            ('relation review', 'human_review_required'),
                            ('proposal review', 'human_review_required')):
        with no_write_attempts(), pytest.raises(AuthoringError) as caught:
            prepare_authoring_request(command_id=command, actor=args['actor'], request_id='evidence-1',
                operations=[{'op': 'evidence_record', 'evidence': record.data}])
        assert caught.value.reason == reason and caught.value.exit_code == 7
    proposed = prepare_authoring_request(command_id='evidence record', actor=args['actor'],
        request_id='evidence-1', operations=[{'op': 'evidence_record', 'evidence': record.data}], as_proposal=True)
    assert proposed.data['route'] == 'proposal_authoring'
    assert not proposed.data['write_authorized'] and not proposed.data['actor_authenticated']
    observation = assess_verification_context(
        VerificationContext(subjects[0], configuration=args['configuration']), record, contract=contract).data
    assert not observation['approval_granted'] and not observation['full_verification_evaluated']
    assert record.source_bytes == before


@pytest.mark.parametrize('producer_type', ['human', 'tool', 'ci', 'monitoring', 'ai'])
def test_unbound_producer_kind_is_not_an_implicit_success_or_human_actor(producer_type):
    subjects, contract, args = unknown_inputs()
    args['producer']['producer_type'] = producer_type
    args['actor'] = {'actor_type': 'tool', 'actor_id': 'recording-adapter'}
    record = prepare_evidence_record(subjects, contract, **args)
    assert record.data['producer'] == args['producer'] and record.data['result'] == 'failed'
    assert record.data['created_by'] == args['actor']
    assert record.data['run_context'] is None and 'reviewer' not in record.data


@pytest.mark.parametrize('field,value', [('/result', 'passed'), ('/title', 'Changed'),
    ('/run_context', None), ('/subjects', []), ('/producer/producer_type', 'human'),
    ('/maturity', 'draft'), ('/evidence_state', 'draft'), ('/revision', 2),
    ('/id', ref('EVD', '2'))])
def test_recorded_evidence_update_is_refused_before_writing_original_bytes(tmp_path, field, value):
    subjects, contract, args = inputs()
    record = prepare_evidence_record(subjects, contract, **args)
    m = model([subjects[0].data, contract.data, record.data])
    # Deliberately noncanonical stored bytes must not be rewritten on denial.
    path = tmp_path / args['allocation'].identity.path
    path.parent.mkdir(parents=True)
    raw = json.dumps(record.data, ensure_ascii=False, indent=4).encode() + b'\n'
    path.write_bytes(raw)
    loaded = RecordArtifact(path.read_bytes(), expected_type='evidence', path=str(path))
    before = inventory(tmp_path)
    operation = {'op': 'update', 'target': record.id, 'expected_revision': 1,
                 'patch': [{'op': 'replace', 'path': field, 'value': value}]}
    with no_write_attempts(), pytest.raises(ChangePlanError) as caught:
        prepare_change_target(m, [operation], policy=POLICY, **FIELDS)
    assert caught.value.reason == 'specialized_operation_required'
    assert path.read_bytes() == loaded.source_bytes == raw and inventory(tmp_path) == before
    assert next(a for a in m.artifacts if a['id'] == record.id) == record.data


@pytest.mark.parametrize('pool', ['current_ids', 'archived_ids'])
def test_stored_evidence_id_cannot_be_reused_through_a_stale_reservation(pool):
    subjects, contract, args = inputs()
    original = prepare_evidence_record(subjects, contract, **args)
    allocation = args['allocation']
    value = allocation.inventory
    pools = {name: set(getattr(value, name)) for name in ('current_ids', 'archived_ids', 'reserved_ids')}
    pools[pool].add(original.id)
    # Simulate a stale/tampered native value; the constructor revalidates it.
    object.__setattr__(allocation, 'inventory', IdentityInventory('SR', **pools))
    before = original.source_bytes
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        prepare_evidence_record(subjects, contract, **{**args, 'result': 'passed'})
    assert caught.value.reason == 'allocation_reservation_mismatch'
    assert original.source_bytes == before and original.data['result'] == 'failed'


def test_later_known_provenance_needs_a_new_identity_and_preserves_unbound_record():
    subjects, contract, args = unknown_inputs()
    previous = prepare_evidence_record(subjects, contract, **args)
    original = previous.source_bytes
    identity = ArtifactIdentity(ref('EVD', '2'), 'random128-v1', 'evidence', 'SR')
    args['allocation'] = IdentityAllocation(identity, IdentityInventory('SR',
        [*args['allocation'].inventory.current_ids, previous.id], [], [identity.id]))
    args.pop('unbound_reason')
    args['run_context'] = inputs()[2]['run_context']
    replacement = prepare_evidence_record(subjects, contract, **args)
    assert replacement.id != previous.id and replacement.data['run_context'] == args['run_context']
    assert previous.source_bytes == original and previous.data['run_context'] is None


@pytest.mark.parametrize('unbound', [False, True])
def test_formatting_cannot_rewrite_recorded_evidence_or_create_an_update(unbound):
    subjects, contract, args = unknown_inputs() if unbound else inputs()
    record = prepare_evidence_record(subjects, contract, **args)
    m = model([record.data])
    before = m.source_files
    with no_write_attempts():
        assessment = prepare_format_target(m, policy=POLICY, **FIELDS)
        with pytest.raises(ChangePlanError):
            prepare_change_target(m, [normalization_operation(m.documents[0])], policy=POLICY, **FIELDS)
    path = m.documents[0].path
    assert path not in {op['path'] for op in assessment.plan.data['operations']}
    assert next(d.content for d in assessment.documents if d.path == path) == before[path]
    assert not assessment.target_validated and m.source_files == before


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_unbound_construction_is_identical_in_isolated_core_and_pyz(tmp_path, mode):
    subjects, contract, args = unknown_inputs(policy='independent')
    args['configuration'] = None
    expected = prepare_evidence_record(subjects, contract, **args).data
    body = '''import json
from specroad.model.identities import ArtifactIdentity, IdentityAllocation, IdentityInventory
from specroad.storage.domain_artifact import DomainArtifact
from specroad.verification import VerificationContract, prepare_evidence_record
'''
    body += 'subjects=[DomainArtifact(' + repr(subjects[0].source_bytes) + ')]\n'
    body += 'contract=VerificationContract(' + repr(contract.source_bytes) + ')\n'
    body += 'identity=ArtifactIdentity(' + repr(args['allocation'].identity.id) + ',"random128-v1","evidence","SR")\n'
    body += 'allocation=IdentityAllocation(identity,IdentityInventory("SR",[subjects[0].id,contract.data["id"]],[],[identity.id]))\n'
    body += 'args=' + repr({key: value for key, value in args.items() if key != 'allocation'}) + '\n'
    body += 'print(json.dumps(prepare_evidence_record(subjects,contract,allocation=allocation,**args).data))\n'
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
