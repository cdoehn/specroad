"""Subject freshness is a read-only observation, not a successful evaluation."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.configurations import resolve_configuration
from specroad.graph.relations import SourceRelations
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.storage.domain_artifact import DomainArtifact
from specroad.storage.record_artifact import RecordArtifact
from specroad.verification import (VerificationContract, VerificationTest,
    VerificationContext, VerificationContextAssessment, verification_context_projection,
    verification_context_sha256, assess_verification_context)
from support.artifacts import artifact_bytes
from support.domain import domain_value, relation, waiver
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from support.records import record_value, ref


def subject(kind='requirement', **changes):
    value = domain_value(kind, **changes) if kind == 'requirement' else record_value(kind, **changes)
    constructor = {'requirement': DomainArtifact, 'verification': VerificationContract,
                   'test': VerificationTest}[kind]
    return constructor(artifact_bytes(value))


def configuration(platform='linux', *, token='0'):
    record = SourceRelations(artifact_bytes(record_value('configuration',
        id=ref('CFG', token), selection={'platform': platform})))
    return resolve_configuration([record], record.identity.id)


def evidence_for(context, **changes):
    return RecordArtifact(artifact_bytes(record_value('evidence',
        **{'subjects': [context.subject_binding], 'configuration_policy': 'bound',
           'configuration_hash': context.data['configuration_hash'], **changes})))


@pytest.mark.parametrize('kind', ['requirement', 'verification', 'test'])
def test_recorded_binding_retains_audit_and_compares_actual_context(kind):
    current = VerificationContext(subject(kind), configuration=configuration())
    evidence = evidence_for(current)
    before = evidence.source_bytes
    with no_write_attempts(): result = assess_verification_context(current, evidence)
    data = result.data
    assert data['freshness'] == 'current' and data['context_current'] and data['reasons'] == []
    assert data['subject'] == data['recorded_subject'] == current.subject_binding
    assert current.subject_binding['artifact_sha256'] == canonical_json_sha256(current.data['subject'])
    assert data['evidence_result'] == 'failed'
    assert data['run_context'] == evidence.data['run_context']
    assert data['evidence_source_sha256'] == sha256(before).hexdigest()
    assert data['evidence_sha256'] == canonical_json_sha256(evidence.data)
    assert data['hash_algorithm'] == 'verification_context_hash-v1'
    assert 'verification_result' not in data
    assert not any(data[field] for field in ('full_verification_evaluated',
        'configuration_applicability_evaluated', 'run_selection_evaluated',
        'release_readiness_evaluated', 'test_code_executed', 'write_authorized', 'approval_granted'))
    assert evidence.source_bytes == before


@pytest.mark.parametrize('kind', ['requirement', 'verification', 'test'])
@pytest.mark.parametrize('changes', [
    {'revision': 7}, {'created_at': '2026-10-19T00:00:00Z'},
    {'updated_at': '2026-10-19T12:00:00Z'},
    {'created_by': {'actor_type': 'tool', 'actor_id': 'other'}},
    {'updated_by': {'actor_type': 'ai', 'actor_id': 'other'}},
    {'maturity': 'proposed'}, {'tags': ['reviewed']},
    {'relations': [relation('references', ref('SRC'))]}])
def test_audit_lifecycle_tags_and_relations_do_not_stale_subject_evidence(kind, changes):
    original = VerificationContext(subject(kind), configuration=configuration())
    current = VerificationContext(subject(kind, **changes), configuration=configuration())
    evidence = evidence_for(original)
    assert current.subject_binding['artifact_sha256'] != original.subject_binding['artifact_sha256']
    assert current.context_sha256 == original.context_sha256
    assert assess_verification_context(current, evidence).data['freshness'] == 'current'


@pytest.mark.parametrize('changes', [
    {'implementation_status': 'implemented'}, {'verification_plan_status': 'running'},
    {'verification_plan_status': 'waived', 'verification_waiver': waiver()},
    {'verification_waiver': waiver()}])
def test_requirement_workflow_and_waiver_decisions_do_not_change_check_subject(changes):
    original = VerificationContext(subject(), configuration=configuration())
    current = VerificationContext(subject(**changes), configuration=configuration())
    assert current.context_sha256 == original.context_sha256
    assert assess_verification_context(current, evidence_for(original)).data['freshness'] == 'current'


@pytest.mark.parametrize('kind,changes', [
    ('requirement', {'statement': 'Network access is mandatory.'}),
    ('requirement', {'normative_force': 'must_not'}),
    ('requirement', {'thresholds': [{'maximum': 10}]}),
    ('requirement', {'preconditions': ['Device offline']}),
    ('requirement', {'exceptions': ['Emergency']}),
    ('requirement', {'timing': {'deadline_ms': 10}}),
    ('requirement', {'actor': 'operator'}),
    ('requirement', {'applicability': {'op': 'literal', 'value': False}}),
    ('requirement', {'owner': 'safety-review'}),
    ('requirement', {'extensions': {'sample.contract': {'inputs': [1, 2]}}}),
    ('verification', {'procedure': ['Different measurement']}),
    ('verification', {'oracle': {'maximum': 10}}),
    ('verification', {'preconditions': ['Calibrated sensor']}),
    ('verification', {'subjects': [ref('REQ', '1')]}),
    ('verification', {'method': 'measurement'}),
    ('verification', {'evidence_kinds': ['measurement']}),
    ('verification', {'configuration_policy': 'independent'}),
    ('verification', {'evidence_slots': [{'check_id': 'other', 'test_id': None, 'dimension': 'overall'}]}),
    ('test', {'test_identity': {'external_id': 'suite/new-case'}}),
    ('test', {'test_type': 'performance'}),
    ('test', {'oracle': {'maximum_ms': 10}}),
    ('test', {'extensions': {'sample.contract': {'inputs': [1], 'dimensions': ['safety']}}})])
def test_changed_check_subject_procedure_or_oracle_makes_bound_evidence_stale(kind, changes):
    original = VerificationContext(subject(kind), configuration=configuration())
    current = VerificationContext(subject(kind, **changes), configuration=configuration())
    with no_write_attempts(): result = assess_verification_context(current, evidence_for(original)).data
    assert result['freshness'] == 'stale' and not result['context_current']
    assert result['reasons'] == ['subject_context_changed']


def test_projection_has_a_fixed_requirement_vector_and_rfc8785_hash():
    record = subject(title='Example requirement', language='en')
    expected = {'schema_version': '0.2.0', 'id': ref(), 'id_scheme': 'random128-v1',
        'artifact_type': 'requirement', 'title': 'Example requirement', 'language': 'en',
        'extensions': {}, 'requirement_kind': 'functional', 'normative_force': 'must',
        'statement': 'No network connection is required.', 'priority': 'mandatory', 'criticality': 'normal'}
    assert verification_context_projection(record) == expected
    # This all-ASCII/integer-free vector also has unambiguous stdlib JSON bytes.
    raw = json.dumps(expected, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
    assert verification_context_sha256(record) == sha256(raw).hexdigest()


def test_provenance_source_is_bound_but_capture_time_is_only_audit():
    source = {'source_id': ref('SRC'), 'excerpt': 'Required behavior', 'captured_at': '2026-01-01T00:00:00Z'}
    original = subject(provenance=[source])
    changed = {**source, 'captured_at': '2026-10-19T00:00:00Z'}
    assert verification_context_sha256(subject(provenance=[changed])) == verification_context_sha256(original)
    changed['excerpt'] = 'Changed behavior'
    assert verification_context_sha256(subject(provenance=[changed])) != verification_context_sha256(original)


@pytest.mark.parametrize('field', ['revision', 'updated_at', 'maturity', 'verification_result', 'tags'])
def test_semantic_extension_members_are_not_removed_by_name(field):
    original = subject(extensions={'sample.contract': {field: 'first'}})
    changed = subject(extensions={'sample.contract': {field: 'second'}})
    assert verification_context_sha256(changed) != verification_context_sha256(original)


@pytest.mark.parametrize('current_config,evidence_config', [
    ('linux', 'windows'), ('linux', None), (None, 'linux')])
def test_exact_configuration_difference_is_stale_even_with_identical_subject(current_config, evidence_config):
    current = VerificationContext(subject(), configuration=None if current_config is None else configuration(current_config))
    recorded = VerificationContext(subject(), configuration=None if evidence_config is None else configuration(evidence_config))
    assert current.context_sha256 == recorded.context_sha256
    if evidence_config is None:
        with no_write_attempts(), pytest.raises(ModelError) as caught:
            evidence_for(recorded)
        assert caught.value.reason == 'missing_configuration_binding'
    else:
        with no_write_attempts(): result = assess_verification_context(current, evidence_for(recorded)).data
        assert result['freshness'] == 'stale' and result['reasons'] == ['configuration_changed']


def test_identical_values_in_different_configuration_identity_do_not_reuse_binding():
    original = VerificationContext(subject(), configuration=configuration())
    changed = VerificationContext(subject(), configuration=configuration(token='1'))
    assert original.data['configuration_hash'] != changed.data['configuration_hash']
    assert assess_verification_context(changed, evidence_for(original)).data['freshness'] == 'stale'


def test_exact_configured_binding_is_current_and_is_detached_from_caller():
    supplied = configuration()
    context = VerificationContext(subject(), configuration=supplied)
    expected = context.data
    supplied.data.clear(); supplied.manifest.clear()
    context.data['subject'].clear(); context.subject_binding.clear()
    result = assess_verification_context(context, evidence_for(context))
    result.data.clear()
    assert context.data == expected and result.data['freshness'] == 'current'
    assert context.data['configuration_hash'] == supplied.sha256
    for value in (context, result):
        with pytest.raises(TypeError): bool(value)
        with pytest.raises(FrozenInstanceError): value._encoded = b'{}'
    with pytest.raises(TypeError): VerificationContextAssessment()


def test_context_and_configuration_failures_are_both_observed():
    original = VerificationContext(subject(), configuration=configuration())
    current = VerificationContext(subject(statement='Other behavior'), configuration=configuration('windows'))
    data = assess_verification_context(current, evidence_for(original)).data
    assert data['reasons'] == ['subject_context_changed', 'configuration_changed']


def test_subject_id_cannot_be_substituted_even_with_a_matching_context_digest():
    current = VerificationContext(subject(), configuration=configuration())
    binding = {**current.subject_binding, 'artifact_id': ref('REQ', '1')}
    result = assess_verification_context(current, evidence_for(current, subjects=[binding])).data
    assert result['freshness'] == 'stale' and result['recorded_subject'] is None
    assert result['reasons'] == ['subject_not_recorded']


def test_duplicate_subjects_are_not_resolved_by_first_or_latest():
    current = VerificationContext(subject(), configuration=configuration())
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        evidence_for(current, subjects=[current.subject_binding] * 2)
    assert caught.value.reason == 'duplicate_subject' and caught.value.pointer == '/subjects/1'


@pytest.mark.parametrize('field', ['configuration_hash', 'configuration_policy'])
def test_missing_configuration_binding_is_not_inferred_from_current_context(field):
    current = VerificationContext(subject(), configuration=configuration())
    data = evidence_for(current).data; data.pop(field)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        assess_verification_context(current, RecordArtifact(artifact_bytes(data)))
    expected = 'missing_configuration_binding' if field == 'configuration_hash' else 'evidence_configuration_binding_required'
    assert caught.value.reason == expected


def test_independent_evidence_label_does_not_bypass_the_future_contract_gate():
    context = VerificationContext(subject(), configuration=configuration())
    evidence = evidence_for(context, configuration_policy='independent', configuration_hash=None)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        assess_verification_context(context, evidence)
    assert caught.value.reason == 'independent_verification_context_not_supported'


@pytest.mark.parametrize('field,value', [('verification_result', 'passed'), ('run_context', {}), ('result', 'passed')])
def test_computed_and_run_fields_are_rejected_as_normative_subject_data(field, value):
    with no_write_attempts(), pytest.raises(ModelError): subject(**{field: value})


@pytest.mark.parametrize('value', [None, {}, b'{}', 'hash'])
def test_untyped_subject_and_configuration_inputs_are_not_trusted(value):
    with pytest.raises(ModelError): verification_context_projection(value)
    if value is not None:
        with pytest.raises(ModelError): VerificationContext(subject(), configuration=value)


def test_configuration_selection_must_be_explicit_even_when_unconfigured():
    with pytest.raises(TypeError): VerificationContext(subject())


def test_other_artifact_types_are_not_guessed_as_verification_subjects():
    with pytest.raises(ModelError): verification_context_projection(DomainArtifact(artifact_bytes(domain_value('component'))))
    with pytest.raises(ModelError): verification_context_projection(RecordArtifact(artifact_bytes(record_value('test'))))


def test_assessment_requires_owned_context_and_evidence_values():
    context = VerificationContext(subject(), configuration=configuration())
    evidence = evidence_for(context)
    with pytest.raises(ModelError): assess_verification_context(context.data, evidence)
    with pytest.raises(ModelError): assess_verification_context(context, evidence.data)
    with pytest.raises(ModelError): assess_verification_context(context, RecordArtifact(artifact_bytes(record_value('test'))))


def test_json_representation_and_path_do_not_change_semantic_hash():
    record = subject(extensions={'sample.contract': {'number': 1.0, 'text': 'Größe'}})
    raw = json.dumps(record.data, ensure_ascii=True, indent=4).encode()
    alternate = DomainArtifact(raw, path='different-path.json')
    assert record.source_bytes != alternate.source_bytes
    assert verification_context_sha256(record) == verification_context_sha256(alternate)


def test_context_observation_neither_reads_files_nor_executes_test_paths(monkeypatch):
    record = subject('test', test_identity={'path': 'tests/must-not-run.py'},
                     oracle={'expression': 'raise RuntimeError()'})
    context = VerificationContext(record, configuration=configuration())
    evidence = evidence_for(context)
    before = (record.source_bytes, evidence.source_bytes, deepcopy(context.data))
    def forbidden(*args, **kwargs): raise AssertionError('Unexpected external access')
    with no_write_attempts(), monkeypatch.context() as patch:
        for name in ('builtins.open', 'io.open', 'subprocess.Popen', 'socket.socket'):
            patch.setattr(name, forbidden)
        result = assess_verification_context(context, evidence)
        assert verification_context_projection(record)['oracle'] == {'expression': 'raise RuntimeError()'}
    assert result.data['freshness'] == 'current'
    assert before == (record.source_bytes, evidence.source_bytes, context.data)


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_context_and_freshness_are_identical_in_isolated_core_and_pyz(tmp_path, mode):
    record = subject()
    context = VerificationContext(record, configuration=configuration())
    evidence = evidence_for(context)
    expected = assess_verification_context(context, evidence).data
    body = '''import json
from specroad.storage.domain_artifact import DomainArtifact
from specroad.storage.record_artifact import RecordArtifact
from specroad.graph.relations import SourceRelations
from specroad.configurations import resolve_configuration
from specroad.verification import VerificationContext, assess_verification_context
'''
    body += 'cfg=SourceRelations(' + repr(artifact_bytes(record_value('configuration'))) + ')\n'
    body += 'configuration=resolve_configuration([cfg],cfg.identity.id)\n'
    body += 'subject=DomainArtifact(' + repr(record.source_bytes) + ')\n'
    body += 'evidence=RecordArtifact(' + repr(evidence.source_bytes) + ')\n'
    body += 'print(json.dumps(assess_verification_context(VerificationContext(subject,configuration=configuration),evidence).data))\n'
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
