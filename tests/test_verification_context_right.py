"""Explicit independent contracts and exact Appendix L context vectors."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.storage.domain_artifact import DomainArtifact
from specroad.storage.record_artifact import RecordArtifact
from specroad.verification import (VerificationContract, VerificationTest,
    VerificationContext, verification_context_projection, verification_context_sha256,
    assess_verification_context)
from support.artifacts import artifact_bytes
from support.domain import domain_value, relation
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from support.records import record_value, ref
from test_verification_context import subject, configuration, evidence_for


def independent_case(kind='requirement', *, current_config='windows', recorded_config=None,
                     contract_policy='independent', evidence_policy='independent'):
    test_id = ref('TEST') if kind == 'test' else None
    contract = VerificationContract(artifact_bytes(record_value('verification',
        configuration_policy=contract_policy,
        evidence_slots=[{'check_id': 'check', 'test_id': test_id, 'dimension': 'overall'}])))
    selected = contract if kind == 'verification' else subject(kind,
        relations=[relation('verified_by', ref('VER'))] if kind == 'requirement' else [])
    context = VerificationContext(selected,
        configuration=None if current_config is None else configuration(current_config))
    contract_context = VerificationContext(contract, configuration=None)
    subjects = {context.subject_binding['artifact_id']: context.subject_binding,
                contract_context.subject_binding['artifact_id']: contract_context.subject_binding}
    evidence = RecordArtifact(artifact_bytes(record_value('evidence',
        subjects=list(subjects.values()), configuration_policy=evidence_policy,
        configuration_hash=None if recorded_config is None else configuration(recorded_config).sha256,
        run_context={'subject_id': 'fixture-product', 'subject_state_sha256': 'c' * 64,
                     'run_id': 'test-ci:run-1', 'check_id': 'check', 'test_id': test_id})))
    return context, evidence, contract


def changed_evidence(evidence, **changes):
    return RecordArtifact(artifact_bytes({**evidence.data, **changes}))


@pytest.mark.parametrize('kind', ['requirement', 'verification', 'test'])
@pytest.mark.parametrize('current_config', [None, 'linux', 'windows'])
def test_explicit_current_independent_contract_allows_cross_configuration_freshness(kind, current_config):
    context, evidence, contract = independent_case(kind, current_config=current_config)
    before = (context.data, evidence.source_bytes, contract.source_bytes)
    with no_write_attempts(): result = assess_verification_context(context, evidence, contract=contract)
    data = result.data
    assert data['freshness'] == 'current' and data['context_current'] and data['reasons'] == []
    assert data['contract_configuration_independent'] is True
    assert data['contract']['artifact_id'] == contract.data['id']
    assert data['contract']['configuration_policy'] == 'independent'
    assert data['contract']['verification_context_sha256'] == verification_context_sha256(contract)
    assert data['contract']['source_sha256'] == sha256(contract.source_bytes).hexdigest()
    assert data['recorded_contract']['artifact_id'] == contract.data['id']
    assert data['contract_check'] == contract.data['evidence_slots'][0]
    assert data['evidence_result'] == 'failed' and data['run_context'] == evidence.data['run_context']
    assert 'verification_result' not in data
    assert not any(data[key] for key in ('full_verification_evaluated', 'run_selection_evaluated',
        'configuration_applicability_evaluated', 'release_readiness_evaluated',
        'test_code_executed', 'write_authorized', 'approval_granted'))
    assert before == (context.data, evidence.source_bytes, contract.source_bytes)


@pytest.mark.parametrize('recorded_config', [None, 'linux', 'windows'])
def test_independent_contract_does_not_erase_original_configuration_provenance(recorded_config):
    context, evidence, contract = independent_case(recorded_config=recorded_config)
    data = assess_verification_context(context, evidence, contract=contract).data
    assert data['freshness'] == 'current'
    assert data['configuration_hash'] == configuration('windows').sha256
    assert data['evidence_configuration_hash'] == evidence.data['configuration_hash']


@pytest.mark.parametrize('evidence_policy', ['bound', 'independent'])
def test_actual_bound_contract_hash_decides_exception_not_the_evidence_label(evidence_policy):
    context, evidence, contract = independent_case(recorded_config='linux', evidence_policy=evidence_policy)
    assert context.data['configuration_hash'] != evidence.data['configuration_hash']
    data = assess_verification_context(context, evidence, contract=contract).data
    assert data['freshness'] == 'current' and data['contract_configuration_independent']


@pytest.mark.parametrize('current_config,expected', [('linux', 'current'), ('windows', 'stale'), (None, 'stale')])
def test_bound_contract_always_preserves_exact_configuration_requirement(current_config, expected):
    context, evidence, contract = independent_case(current_config=current_config,
        recorded_config='linux', contract_policy='bound', evidence_policy='bound')
    data = assess_verification_context(context, evidence, contract=contract).data
    assert data['freshness'] == expected and not data['contract_configuration_independent']
    assert data['reasons'] == ([] if expected == 'current' else ['configuration_changed'])


def test_bound_contract_cannot_be_overruled_by_independent_evidence_even_with_equal_null_hashes():
    context, evidence, contract = independent_case(current_config=None, contract_policy='bound')
    data = assess_verification_context(context, evidence, contract=contract).data
    assert data['freshness'] == 'stale'
    assert data['reasons'] == ['independent_contract_required']
    assert not data['contract_configuration_independent']


@pytest.mark.parametrize('kind', ['requirement', 'verification', 'test'])
def test_independent_label_without_explicit_contract_keeps_the_existing_rejection(kind):
    context, evidence, _ = independent_case(kind)
    with pytest.raises(ModelError) as caught: assess_verification_context(context, evidence)
    assert caught.value.reason == 'independent_verification_context_not_supported'


@pytest.mark.parametrize('untyped', [{}, b'{}', 'independent', True, 1])
def test_untyped_contract_is_never_a_configuration_exception(untyped):
    context, evidence, _ = independent_case()
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        assess_verification_context(context, evidence, contract=untyped)
    assert caught.value.reason == 'typed_verification_contract_required'


@pytest.mark.parametrize('kind', ['requirement', 'verification', 'test'])
def test_unrelated_independent_contract_is_rejected_before_reuse(kind):
    context, evidence, contract = independent_case(kind)
    value = contract.data
    if kind == 'requirement': value['subjects'] = [ref('REQ', '1')]
    elif kind == 'test': value['evidence_slots'][0]['test_id'] = ref('TEST', '1')
    else: value['id'] = ref('VER', '1')
    other = VerificationContract(artifact_bytes(value))
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        assess_verification_context(context, evidence, contract=other)
    assert caught.value.reason == 'verification_contract_subject_mismatch'


@pytest.mark.parametrize('changes', [{'check_id': 'other'}, {'test_id': ref('TEST', '1')}])
def test_contract_exception_is_bound_to_actual_check_and_test_identity(changes):
    context, evidence, contract = independent_case('test')
    changed = changed_evidence(evidence, run_context={**evidence.data['run_context'], **changes})
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        assess_verification_context(context, changed, contract=contract)
    assert caught.value.reason == 'verification_contract_check_mismatch'
    assert caught.value.pointer == '/run_context'


def test_missing_run_check_does_not_get_an_inferred_overall_slot():
    context, evidence, contract = independent_case()
    evidence = changed_evidence(evidence, run_context=None, unbound_reason='No run metadata')
    with pytest.raises(ModelError) as caught: assess_verification_context(context, evidence, contract=contract)
    assert caught.value.reason == 'verification_contract_check_required'


def test_test_subject_cannot_borrow_another_valid_slot_of_the_same_contract():
    context, evidence, contract = independent_case('test')
    value = contract.data
    value['evidence_slots'].append({'check_id': 'other', 'test_id': ref('TEST', '1'), 'dimension': 'overall'})
    contract = VerificationContract(artifact_bytes(value))
    evidence = changed_evidence(evidence, run_context={**evidence.data['run_context'],
        'check_id': 'other', 'test_id': ref('TEST', '1')})
    with pytest.raises(ModelError) as caught: assess_verification_context(context, evidence, contract=contract)
    assert caught.value.reason == 'verification_contract_check_mismatch'


@pytest.mark.parametrize('changes', [
    {'procedure': ['Another procedure']}, {'oracle': {'maximum': 10}},
    {'preconditions': ['Calibrated device']}, {'method': 'measurement'},
    {'evidence_kinds': ['measurement']}, {'owner': 'another-owner'},
    {'applicability': {'op': 'literal', 'value': False}},
    {'extensions': {'sample.oracle': {'expected': 42}}}])
def test_stale_contract_never_authorizes_configuration_independence(changes):
    context, evidence, contract = independent_case()
    current = VerificationContract(artifact_bytes({**contract.data, **changes}))
    data = assess_verification_context(context, evidence, contract=current).data
    assert data['freshness'] == 'stale' and not data['contract_configuration_independent']
    assert data['reasons'] == ['contract_context_changed', 'configuration_changed']


def test_missing_contract_subject_binding_cannot_be_invented_from_argument():
    context, evidence, contract = independent_case()
    evidence = changed_evidence(evidence, subjects=[context.subject_binding])
    data = assess_verification_context(context, evidence, contract=contract).data
    assert data['freshness'] == 'stale' and data['recorded_contract'] is None
    assert data['reasons'] == ['contract_not_recorded', 'configuration_changed']


def test_contract_policy_change_invalidates_previous_contract_binding():
    context, evidence, contract = independent_case(recorded_config='linux',
        contract_policy='bound', evidence_policy='bound')
    current = VerificationContract(artifact_bytes({**contract.data, 'configuration_policy': 'independent'}))
    data = assess_verification_context(context, evidence, contract=current).data
    assert data['reasons'] == ['contract_context_changed', 'configuration_changed']
    assert not data['contract_configuration_independent']


@pytest.mark.parametrize('changes', [{'revision': 99}, {'maturity': 'proposed'}, {'tags': ['reviewed']},
    {'created_at': '2026-10-19T00:00:00Z'}, {'updated_at': '2026-10-19T01:00:00Z'},
    {'created_by': {'actor_type': 'tool', 'actor_id': 'other'}},
    {'updated_by': {'actor_type': 'human', 'actor_id': 'other'}},
    {'relations': [relation('references', ref('SRC'))]}])
def test_contract_audit_changes_retain_independence_and_historical_audit_binding(changes):
    context, evidence, contract = independent_case()
    current = VerificationContract(artifact_bytes({**contract.data, **changes}))
    data = assess_verification_context(context, evidence, contract=current).data
    assert data['freshness'] == 'current' and data['contract_configuration_independent']
    assert data['recorded_contract']['revision'] == contract.data['revision']
    assert data['recorded_contract']['artifact_sha256'] == canonical_json_sha256(contract.data)
    assert data['contract']['artifact_sha256'] != data['recorded_contract']['artifact_sha256']


def test_subject_changes_remain_stale_under_a_valid_independent_contract():
    context, evidence, contract = independent_case()
    changed = VerificationContext(DomainArtifact(artifact_bytes({**context.data['subject'],
        'statement': 'Changed behavior'})), configuration=configuration('linux'))
    data = assess_verification_context(changed, evidence, contract=contract).data
    assert data['freshness'] == 'stale' and data['reasons'] == ['subject_context_changed']


def test_contract_subject_and_selected_contract_cannot_represent_different_semantics():
    context, evidence, contract = independent_case('verification')
    changed = VerificationContract(artifact_bytes({**contract.data, 'oracle': 'New criterion'}))
    with pytest.raises(ModelError) as caught: assess_verification_context(context, evidence, contract=changed)
    assert caught.value.reason == 'verification_contract_subject_context_mismatch'


@pytest.mark.parametrize('kind', ['requirement', 'verification', 'test'])
def test_exact_projection_vectors_keep_semantic_metadata_and_drop_only_audit(kind):
    provenance = {'source_id': ref('SRC'), 'locator': 'source:contract', 'excerpt': 'Original text',
        'content_sha256': 'd' * 64, 'captured_at': '2026-01-01T00:00:00Z',
        'extensions': {'sample.source': {'revision': 4}}}
    record = subject(kind, owner={'actor_type': 'human', 'actor_id': 'engineering'},
        provenance=[provenance], extensions={'sample.inputs': {'revision': 3, 'tags': ['semantic']}},
        applicability={'op': 'literal', 'value': True}, title='Context vector',
        tags=['audit-only'], revision=7, maturity='proposed')
    common = {'schema_version': '0.2.0', 'id_scheme': 'random128-v1',
        'artifact_type': kind, 'id': ref({'requirement': 'REQ', 'verification': 'VER', 'test': 'TEST'}[kind]),
        'title': 'Context vector', 'owner': {'actor_type': 'human', 'actor_id': 'engineering'},
        'provenance': [{'source_id': ref('SRC'), 'locator': 'source:contract', 'excerpt': 'Original text',
            'content_sha256': 'd' * 64, 'extensions': {'sample.source': {'revision': 4}}}],
        'extensions': {'sample.inputs': {'revision': 3, 'tags': ['semantic']}},
        'applicability': {'op': 'literal', 'value': True}}
    fields = {
        'requirement': {'language': 'de-DE', 'requirement_kind': 'functional', 'normative_force': 'must',
            'statement': 'No network connection is required.', 'priority': 'mandatory', 'criticality': 'normal'},
        'verification': {'method': 'inspection', 'subjects': [ref()], 'preconditions': [],
            'procedure': ['Inspect data'], 'oracle': 'Required fields exist', 'evidence_kinds': ['inspection_report'],
            'dimensions': ['overall'], 'evidence_slots': [{'check_id': 'overall', 'test_id': None, 'dimension': 'overall'}],
            'configuration_policy': 'bound'},
        'test': {'test_identity': {'external_id': 'suite/test-case'}, 'test_type': 'behavior',
            'oracle': 'Operation is read-only'}}
    expected = {**common, **fields[kind]}
    assert verification_context_projection(record) == expected
    assert verification_context_sha256(record) == sha256(canonical_json_bytes(expected)).hexdigest()


@pytest.mark.parametrize('changes', [
    {'scope': {'area': 'device'}}, {'actor': 'operator'}, {'trigger': 'power-on'},
    {'preconditions': ['Battery charged']}, {'response': 'Start safely'}, {'object': 'motor'},
    {'timing': {'milliseconds': 10}}, {'thresholds': [{'maximum': 12}]}, {'exceptions': ['Emergency']},
    {'rationale': 'Safety'}, {'normative_force': 'should', 'deviation_conditions': 'Document review',
     'deviation_authority': 'safety-owner'}, {'language': 'en'}, {'text_direction': 'rtl'},
    {'priority': 'high'}, {'criticality': 'critical'}, {'requirement_kind': 'safety'}])
def test_all_structured_requirement_inputs_participate_in_context(changes):
    assert verification_context_sha256(subject(**changes)) != verification_context_sha256(subject())


@pytest.mark.parametrize('field', ['revision', 'maturity', 'verification_result', 'created_at', 'relations', 'tags'])
def test_nested_oracle_field_names_are_semantic_not_top_level_exclusions(field):
    first = subject('verification', oracle={field: 'first'})
    second = subject('verification', oracle={field: 'second'})
    assert verification_context_sha256(first) != verification_context_sha256(second)


def test_ordered_procedure_and_slot_values_are_not_silently_sorted():
    first = subject('verification', procedure=['Start', 'Measure'])
    second = subject('verification', procedure=['Measure', 'Start'])
    assert verification_context_sha256(first) != verification_context_sha256(second)
    slots = [{'check_id': name, 'test_id': None, 'dimension': 'overall'} for name in ('first', 'second')]
    first = subject('verification', evidence_slots=slots)
    second = subject('verification', evidence_slots=slots[::-1])
    assert verification_context_sha256(first) != verification_context_sha256(second)


def test_policy_observation_is_owned_and_does_not_execute_contract_or_touch_files(monkeypatch):
    context, evidence, contract = independent_case()
    original = (context.data, evidence.source_bytes, contract.source_bytes)
    def forbidden(*args, **kwargs): raise AssertionError('External action during context observation')
    with no_write_attempts(), monkeypatch.context() as patch:
        for name in ('builtins.open', 'io.open', 'subprocess.Popen', 'socket.socket'):
            patch.setattr(name, forbidden)
        result = assess_verification_context(context, evidence, contract=contract)
    before = deepcopy(result.data)
    result.data['contract'].clear(); result.data['contract_check'].clear(); contract.data.clear()
    assert before == result.data and original == (context.data, evidence.source_bytes, contract.source_bytes)
    with pytest.raises(TypeError): bool(result)
    with pytest.raises(FrozenInstanceError): result._encoded = b'{}'


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_independent_contract_gate_has_identical_isolated_core_and_pyz_results(tmp_path, mode):
    context, evidence, contract = independent_case(current_config=None)
    raw_subject = artifact_bytes(context.data['subject'])
    context = VerificationContext(DomainArtifact(raw_subject), configuration=None)
    expected = assess_verification_context(context, evidence, contract=contract).data
    body = '''import json
from specroad.storage.domain_artifact import DomainArtifact
from specroad.storage.record_artifact import RecordArtifact
from specroad.verification import VerificationContext, VerificationContract, assess_verification_context
'''
    body += 'subject=DomainArtifact(' + repr(raw_subject) + ')\n'
    body += 'evidence=RecordArtifact(' + repr(evidence.source_bytes) + ')\n'
    body += 'contract=VerificationContract(' + repr(contract.source_bytes) + ')\n'
    body += 'print(json.dumps(assess_verification_context(VerificationContext(subject,configuration=None),evidence,contract=contract).data))\n'
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
