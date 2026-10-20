"""Owned generic imports bind declared measurements, never publish Evidence."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.storage.record_artifact import RecordArtifact
from specroad.verification import (EvidenceExchange, ExchangeCandidates, EvidenceImportError,
    evidence_exchange_schema, map_generic_candidates, VerificationContext, prepare_evidence_record)
from support.artifacts import artifact_bytes
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from support.records import ref
from test_evidence_construction import inputs


def exchange_case():
    subjects, contract, args = inputs(with_test=True)
    targets = [*subjects, contract, args['test']]
    value = {
        'format_version': 'specroad-evidence-exchange-v1',
        'producer': args['producer'], 'tool': args['tool'],
        'run': {k: args['run_context'][k] for k in ('subject_id', 'subject_state_sha256', 'run_id')},
        'subjects': [VerificationContext(t, configuration=None).subject_binding for t in targets],
        'results': [{'target_id': contract.data['id'], 'check_id': 'measurement',
                     'test_id': args['test'].data['id'], 'result': 'failed',
                     'produced_at': args['produced_at'], 'subject_ids': [t.data['id'] for t in targets],
                     'attachment_paths': ['attachments/report.txt']}],
        'environment': args['environment'], 'attachments': [
            {'path': 'attachments/report.txt', 'media_type': 'text/plain',
             'size': 5, 'sha256': sha256(b'trace').hexdigest()}],
        'configuration_hash': args['configuration'].sha256, 'configuration_policy': 'bound'}
    return value, targets


@pytest.mark.parametrize('result', ['passed', 'failed', 'skipped', 'incomplete', 'unclassified'])
@pytest.mark.parametrize('target_index', [0, 1, 2])
def test_explicit_measurements_bind_native_targets_run_producer_and_exact_subjects(result, target_index):
    value, targets = exchange_case()
    value['results'][0].update(result=result, target_id=targets[target_index].data['id'])
    raw = artifact_bytes(value)
    with no_write_attempts():
        doc = EvidenceExchange(raw)
        resolved = map_generic_candidates(doc, targets=targets).data
    candidate, = resolved['candidates']
    assert candidate['target'] == {
        'artifact_id': targets[target_index].data['id'],
        'artifact_type': targets[target_index].data['artifact_type'], 'revision': 1,
        'source_sha256': sha256(targets[target_index].source_bytes).hexdigest(),
        'record_sha256': canonical_json_sha256(targets[target_index].data)}
    assert candidate['result'] == result and candidate['origin'] == 'imported_generic'
    assert candidate['run_context'] == {**value['run'], 'check_id': 'measurement',
                                       'test_id': targets[2].data['id']}
    for field in ('producer', 'tool', 'subjects', 'environment', 'attachments',
                  'configuration_hash', 'configuration_policy'):
        assert candidate[field] == value[field]
    assert candidate['produced_at'] == value['results'][0]['produced_at']
    assert resolved['source'] == {'sha256': sha256(raw).hexdigest(), 'size': len(raw)}
    assert resolved['exchange_sha256'] == canonical_json_sha256(value)
    assert resolved['candidate_count'] == 1 and resolved['supplied_subjects_bound'] is True
    for field in ('external_run_verified', 'project_targets_verified', 'configuration_verified',
                  'attachments_verified', 'contract_slots_verified', 'test_code_executed',
                  'evidence_created', 'full_verification_evaluated', 'write_authorized', 'approval_granted'):
        assert resolved[field] is False


def test_results_preserve_occurrences_subject_subsets_and_only_selected_attachments():
    value, targets = exchange_case()
    first = value['results'][0]
    second = {**first, 'result': 'passed', 'subject_ids': [targets[0].data['id']], 'attachment_paths': []}
    value['results'] = [first, second, first]
    data = map_generic_candidates(EvidenceExchange(artifact_bytes(value)), targets=targets).data
    assert [c['result_index'] for c in data['candidates']] == [0, 1, 2]
    assert [c['result'] for c in data['candidates']] == ['failed', 'passed', 'failed']
    assert data['candidates'][1]['subjects'] == [value['subjects'][0]]
    assert data['candidates'][1]['attachments'] == []


def test_empty_results_never_invent_a_passing_measurement():
    value, targets = exchange_case()
    value['results'] = []
    data = map_generic_candidates(EvidenceExchange(artifact_bytes(value)), targets=targets).data
    assert data['candidate_count'] == 0 and data['candidates'] == []
    assert data['full_verification_evaluated'] is False


@pytest.mark.parametrize('path,replacement', [
    (('format_version',), 'specroad-evidence-exchange-v2'),
    (('producer',), {'producer_type': 'ai', 'producer_id': 'x', 'approved': True}),
    (('producer', 'producer_id'), ''), (('tool', 'version'), None),
    (('run', 'subject_state_sha256'), 'A' * 64), (('run', 'run_id'), 'unnamespaced'),
    (('run', 'run_id'), ' : '), (('run', 'run_id'), 'ci:'),
    (('subjects',), []), (('subjects', 0, 'revision'), 0),
    (('results', 0, 'target_id'), ref('EVD')), (('results', 0, 'check_id'), 'bad check'),
    (('results', 0, 'produced_at'), '2026-10-20T11:00:00+01:00'),
    (('results', 0, 'result'), None), (('results', 0, 'subject_ids'), []),
    (('results', 0, 'test_id'), ref('REQ')), (('environment',), []),
    (('attachments', 0, 'size'), -1), (('attachments', 0, 'sha256'), 'bad'),
    (('configuration_hash',), None), (('configuration_policy',), 'any')])
def test_invalid_or_incomplete_contract_never_yields_candidates(path, replacement):
    value, _ = exchange_case()
    parent = value
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = replacement
    with no_write_attempts(), pytest.raises(EvidenceImportError) as caught:
        EvidenceExchange(artifact_bytes(value))
    assert caught.value.diagnostic()['code'] == 'SRV091'
    assert caught.value.diagnostic()['exit_code'] == 3


@pytest.mark.parametrize('field', ['producer', 'tool', 'run', 'subjects', 'results',
                                  'environment', 'attachments', 'configuration_hash', 'configuration_policy'])
def test_no_missing_top_level_input_is_filled_from_defaults(field):
    value, _ = exchange_case()
    del value[field]
    with pytest.raises(EvidenceImportError):
        EvidenceExchange(artifact_bytes(value))


@pytest.mark.parametrize('path', ['../outside', '/absolute', 'a/../b', 'a\\b',
                                '.git/config', 'NUL', './attachments/x'])
def test_attachment_references_are_safe_relative_paths_without_access(path):
    value, _ = exchange_case()
    value['attachments'][0]['path'] = path
    with no_write_attempts(), pytest.raises(EvidenceImportError):
        EvidenceExchange(artifact_bytes(value))


@pytest.mark.parametrize('field', ['revision', 'artifact_sha256', 'verification_context_sha256'])
def test_subject_hash_and_revision_claims_must_match_actual_owned_inputs(field):
    value, targets = exchange_case()
    value['subjects'][0][field] = 2 if field == 'revision' else 'e' * 64
    doc = EvidenceExchange(artifact_bytes(value))
    with no_write_attempts(), pytest.raises(EvidenceImportError) as caught:
        map_generic_candidates(doc, targets=targets)
    assert caught.value.reason == 'import_subject_binding_mismatch'


@pytest.mark.parametrize('field,reason', [('target_id', 'import_target_not_found'),
                                       ('test_id', 'import_test_not_found')])
def test_unknown_target_or_test_is_never_resolved_by_guessing(field, reason):
    value, targets = exchange_case()
    value['results'][0][field] = ref('TEST', '2')
    with pytest.raises(EvidenceImportError) as caught:
        map_generic_candidates(EvidenceExchange(artifact_bytes(value)), targets=targets)
    assert caught.value.reason == reason


@pytest.mark.parametrize('part', ['subjects', 'attachments', 'subject_ids', 'attachment_paths'])
def test_duplicate_bindings_are_rejected(part):
    value, _ = exchange_case()
    items = value[part] if part in value else value['results'][0][part]
    items.append(items[0])
    with pytest.raises(EvidenceImportError) as caught:
        EvidenceExchange(artifact_bytes(value))
    assert caught.value.reason == 'duplicate_evidence_import_binding'


@pytest.mark.parametrize('part,replacement,reason', [
    ('subject_ids', [ref('REQ', '2')], 'unknown_import_subject'),
    ('attachment_paths', ['attachments/other.txt'], 'unknown_import_attachment')])
def test_cross_references_require_exact_declared_subjects_and_attachments(part, replacement, reason):
    value, _ = exchange_case()
    value['results'][0][part] = replacement
    with pytest.raises(EvidenceImportError) as caught:
        EvidenceExchange(artifact_bytes(value))
    assert caught.value.reason == reason


@pytest.mark.parametrize('raw', ['{}', bytearray(b'{}'), None, b'{"x":1,"x":2}',
    b'{"x":NaN}', b'[]', b'{} trailing', b'{"x":"\\ud800"}', b'{}' + bytes([255])])
def test_only_owned_strict_json_object_bytes_are_read(raw):
    with pytest.raises(EvidenceImportError):
        EvidenceExchange(raw)


def test_profile_resource_limits_reject_oversized_or_deep_inputs():
    value, _ = exchange_case()
    raw = artifact_bytes(value)
    exact = raw + b' ' * (4 * 1024 * 1024 - len(raw))
    assert EvidenceExchange(exact).data == value
    for bad in (exact + b' ', b'{"x":' + b'[' * 70 + b'0' + b']' * 70 + b'}',
                b'{"x":[' + b'0,' * 10000 + b'0]}'):
        with pytest.raises(EvidenceImportError) as caught:
            EvidenceExchange(bad)
        assert caught.value.reason.startswith('evidence_import_')


def test_independent_configuration_is_explicit_and_not_approval():
    value, targets = exchange_case()
    value.update(configuration_hash=None, configuration_policy='independent')
    result = map_generic_candidates(EvidenceExchange(artifact_bytes(value)), targets=targets).data
    assert result['candidates'][0]['configuration_hash'] is None
    assert result['configuration_verified'] is False


def test_repeated_environment_metadata_cannot_amplify_into_unbounded_candidate_output():
    value, targets = exchange_case()
    value['environment'] = {'log': 'x' * 40000}
    value['results'] *= 500
    doc = EvidenceExchange(artifact_bytes(value))
    assert len(doc.source_bytes) < 1024 * 1024
    with no_write_attempts(), pytest.raises(EvidenceImportError) as caught:
        map_generic_candidates(doc, targets=targets)
    assert caught.value.reason == 'evidence_import_candidate_limit'


def test_values_own_inputs_and_hashes_without_mutable_output_or_boolean_authority():
    value, targets = exchange_case()
    doc = EvidenceExchange(artifact_bytes(value))
    result = map_generic_candidates(doc, targets=targets)
    original = result.data
    value.clear(); doc.data.clear(); result.data['candidates'].clear()
    evidence_exchange_schema()['properties'].clear()
    assert result.data == original and result.sha256 == canonical_json_sha256(original)
    assert map_generic_candidates(EvidenceExchange(doc.source_bytes), targets=targets).data == original
    for item in (doc, result):
        with pytest.raises(TypeError): bool(item)
        with pytest.raises(FrozenInstanceError): item._encoded = b'{}'
    with pytest.raises(TypeError): ExchangeCandidates(original)
    with pytest.raises(ModelError): RecordArtifact(artifact_bytes(original), expected_type='evidence')
    object.__setattr__(doc, '_encoded', b'{}')
    assert map_generic_candidates(doc, targets=targets).data == original


@pytest.mark.parametrize('bad', [None, [], {}, 'path'])
def test_untyped_documents_and_native_targets_are_not_accepted(bad):
    value, targets = exchange_case()
    with pytest.raises(EvidenceImportError):
        map_generic_candidates(bad, targets=targets)
    with pytest.raises(EvidenceImportError):
        map_generic_candidates(EvidenceExchange(artifact_bytes(value)), targets=[bad])
    with pytest.raises(EvidenceImportError):
        map_generic_candidates(EvidenceExchange(artifact_bytes(value)), targets=[*targets, targets[0]])


def test_generic_measurement_composes_with_native_construction_using_explicit_authority_only():
    value, targets = exchange_case()
    subjects, contract, args = inputs(with_test=True)
    candidate, = map_generic_candidates(EvidenceExchange(artifact_bytes(value)),
                                        targets=targets).data['candidates']
    keys = ('result', 'produced_at', 'producer', 'tool', 'environment', 'origin', 'run_context')
    with no_write_attempts():
        evidence = prepare_evidence_record(subjects, contract,
                                           **{**args, **{k: candidate[k] for k in keys}})
    for key in keys:
        assert evidence.data[key] == candidate[key]
    assert evidence.data['subjects'] == sorted(candidate['subjects'], key=lambda s: s['artifact_id'])


def test_parsing_and_binding_never_read_host_files_network_clock_or_randomness(monkeypatch):
    value, targets = exchange_case()
    raw = artifact_bytes(value)
    def forbidden(*args, **kwargs): raise AssertionError('External access')
    with no_write_attempts(), monkeypatch.context() as patch:
        for name in ('builtins.open', 'io.open', 'time.time', 'os.urandom'):
            patch.setattr(name, forbidden)
        output = map_generic_candidates(EvidenceExchange(raw), targets=targets)
    assert output.data['candidate_count'] == 1


def test_core_and_portable_pyz_have_equal_generic_binding_behavior(tmp_path):
    value, targets = exchange_case()
    script = f"""
import json
from specroad.storage.domain_artifact import DomainArtifact
from specroad.verification import EvidenceExchange, VerificationContract, VerificationTest, map_generic_candidates
targets = [DomainArtifact({targets[0].source_bytes!r}),
           VerificationContract({targets[1].source_bytes!r}), VerificationTest({targets[2].source_bytes!r})]
print(json.dumps(map_generic_candidates(EvidenceExchange({artifact_bytes(value)!r}), targets=targets).data, sort_keys=True))
"""
    _, archive = build_distribution(tmp_path / 'dist')
    core = run_core(script, tmp_path, capture=True)
    portable = run_python(['-I', '-S', '-B', '-c',
        'import sys;sys.path.insert(0,' + repr(str(archive)) + ');\n' + script], tmp_path, capture=True)
    assert core.returncode == portable.returncode == 0, (core.stderr, portable.stderr)
    assert json.loads(core.stdout) == json.loads(portable.stdout)
