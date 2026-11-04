"""Fail closed on stale contexts, changed history and attempted legacy writes."""
from hashlib import sha256
import json
from unittest.mock import patch
import pytest

from specroad.archive.verification import verify_baseline_snapshot
from specroad.migration.history import verify_source_history, verify_migrated_history
from specroad.migration.legacy_manifest import validate_legacy_manifest
from specroad.migration.legacy_values import LegacyManifest
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.security import ProjectBoundary, SafetyViolation
from specroad.storage.domain_artifact import DomainArtifact
from specroad.storage.project import ProjectSource
from specroad.storage.representation import prepare_normalization
from specroad.verification import (VerificationContext, VerificationContract,
    assess_verification_context, prepare_evidence_record)
from support.legacy_manifest import migrated, write_files, MANIFEST
from support.migration_history import (evidence_source, BASELINE, EVIDENCE,
    REQUIREMENT, VERIFICATION, PROJECT_ID)
from support.reference01 import encoded, full_project
from support.read_only import no_write_attempts, inventory


def observation(files=None):
    old, target, _ = migrated(evidence_source() if files is None else files)
    manifest = validate_legacy_manifest(target, project_id=PROJECT_ID)
    evidence = manifest.artifact(EVIDENCE, old[EVIDENCE])
    subject = DomainArtifact(target[REQUIREMENT], expected_type='requirement')
    contract = VerificationContract(target[VERIFICATION])
    return old, target, manifest, evidence, subject, contract


@pytest.mark.parametrize('result', ['passed', 'failed', 'incomplete', 'skipped'])
@pytest.mark.parametrize('with_contract', [False, True])
def test_historical_result_never_promotes_transformed_context(result, with_contract):
    old, _, manifest, evidence, subject, contract = observation(evidence_source(result=result))
    current = VerificationContext(subject, configuration=None)
    with no_write_attempts():
        assessment = assess_verification_context(current, evidence, legacy_manifest=manifest,
            contract=contract if with_contract else None)
    data = assessment.data; original = json.loads(old[EVIDENCE])
    assert data['historical_integrity_verified'] and data['evidence_result'] == result
    assert data['freshness'] == 'stale' and not data['context_current']
    assert data['reasons'] == ['migration_context_unverified']
    assert data['recorded_subject'] == original['subjects'][0]
    assert data['recorded_subject']['verification_context_sha256'] != current.context_sha256
    assert data['historical_hash_algorithm'] == 'reference01-verification-context-v1'
    assert data['hash_algorithm'] == 'verification_context_hash-v1'
    assert data['evidence_source_sha256'] == sha256(old[EVIDENCE]).hexdigest()
    assert evidence.source_bytes == old[EVIDENCE]
    assert data['legacy_manifest_sha256'] == manifest.sha256
    assert not any(data[k] for k in ('full_verification_evaluated', 'run_selection_evaluated',
        'release_readiness_evaluated', 'historical_external_run_verified',
        'contract_configuration_independent', 'write_authorized', 'approval_granted'))
    with pytest.raises(TypeError): bool(assessment)


def test_new_measurement_has_new_id_and_current_binding_without_upgrading_old_evidence():
    from specroad.model.identities import ArtifactIdentity, IdentityAllocation, IdentityInventory
    from support.records import ref
    old, _, manifest, evidence, subject, contract = observation()
    identity = ArtifactIdentity(ref('EVD', '2'), 'random128-v1', 'evidence', 'SR')
    allocation = IdentityAllocation(identity, IdentityInventory('SR',
        [subject.id, contract.data['id'], evidence.id], (), (identity.id,)))
    with no_write_attempts():
        record = prepare_evidence_record([subject], contract, allocation=allocation,
            configuration=None, actor={'actor_type': 'tool', 'actor_id': 'synthetic-meter'},
            planned_at='2026-11-04T00:00:00Z', produced_at='2026-11-04T00:00:00Z',
            title='Synthetic new measurement', result='passed',
            producer={'producer_type': 'tool', 'producer_id': 'synthetic-meter'},
            tool={'name': 'synthetic-meter', 'version': '1'}, environment={'platform': 'synthetic'},
            origin='recorded_manual', run_context={'subject_id': 'synthetic-product',
                'subject_state_sha256': 'b' * 64, 'run_id': 'synthetic-meter:new-run',
                'check_id': 'overall', 'test_id': None})
        context = VerificationContext(subject, configuration=None)
        fresh = assess_verification_context(context, record, contract=contract).data
        historical = assess_verification_context(context, evidence, legacy_manifest=manifest).data
    assert record.id != evidence.id and record.data['schema_version'] == '0.2.0'
    assert record.data['revision'] == 1 and fresh['freshness'] == 'current'
    assert historical['freshness'] == 'stale' and evidence.source_bytes == old[EVIDENCE]
    assert not fresh['approval_granted'] and not fresh['full_verification_evaluated']
    with pytest.raises(ModelError):
        IdentityAllocation(evidence.identity, IdentityInventory('SR', [evidence.id], (), (evidence.id,)))


def test_current_contract_independence_configuration_or_projection_cannot_refresh_old_record():
    from test_verification_context import configuration
    old, _, manifest, evidence, subject, contract = observation()
    independent = VerificationContract(canonical_json_bytes({**contract.data, 'configuration_policy': 'independent'}))
    context = VerificationContext(subject, configuration=configuration())
    data = assess_verification_context(context, evidence, legacy_manifest=manifest, contract=independent).data
    assert data['reasons'] == ['migration_context_unverified'] and not data['context_current']
    assert not data['contract_configuration_independent']
    assert evidence.source_bytes == old[EVIDENCE]
    with pytest.raises(ModelError, match='typed_verification_evidence_required'):
        assess_verification_context(context, evidence.navigation)
    with pytest.raises(ModelError, match='typed_verification_contract_required'):
        assess_verification_context(context, evidence, legacy_manifest=manifest, contract=independent.data)


def test_missing_subject_and_optional_source_configuration_remain_explicit():
    _, _, manifest, evidence, subject, _ = observation(full_project())
    other = DomainArtifact(canonical_json_bytes({**subject.data, 'id': 'SR-REQ-0002'}))
    data = assess_verification_context(VerificationContext(other, configuration=None),
        evidence, legacy_manifest=manifest).data
    assert data['recorded_subject'] is None
    assert data['reasons'] == ['migration_context_unverified', 'subject_not_recorded']
    assert data['evidence_configuration_binding'] == {}


@pytest.mark.parametrize('kind', ['none', 'report', 'dict', 'missing_file', 'changed_file', 'changed_binding'])
def test_evidence_requires_actual_complete_originals_not_cached_success(kind):
    _, _, manifest, evidence, subject, _ = observation()
    supplied = manifest
    if kind == 'none': supplied = None
    elif kind == 'report': supplied = verify_source_history(evidence_source())
    elif kind == 'dict': supplied = manifest.data
    else:
        supplied = object.__new__(LegacyManifest)
        files = dict(manifest._files)
        path = next(p for p in files if p.startswith('archive/objects/'))
        if kind == 'missing_file': del files[path]
        elif kind == 'changed_file': files[path] += b'changed'
        object.__setattr__(supplied, '_files', tuple(files.items()))
        object.__setattr__(supplied, '_encoded', b'{}' if kind == 'changed_binding' else manifest._encoded)
        object.__setattr__(supplied, '_originals', manifest._originals)
    with pytest.raises(ModelError):
        assess_verification_context(VerificationContext(subject, configuration=None),
            evidence, legacy_manifest=supplied)


@pytest.mark.parametrize('damage', ['missing_manifest', 'wrong_project', 'changed_original',
    'missing_transitive_object', 'invented_reader', 'modified_projection', 'wrong_hash_algorithm'])
def test_modified_original_closure_is_never_historically_verified(damage):
    _, target, _ = migrated(evidence_source(nested=True))
    project = PROJECT_ID
    if damage == 'missing_manifest': del target[MANIFEST]
    elif damage == 'wrong_project': project = 'different-project'
    elif damage == 'changed_original': target[EVIDENCE] += b'\n'
    elif damage == 'missing_transitive_object':
        row = next(r for r in json.loads(target[BASELINE])['manifest'] if r['path'] == REQUIREMENT)
        del target['archive/objects/' + row['byte_sha256'][:2] + '/' + row['byte_sha256']]
    else:
        registry = json.loads(target[MANIFEST])
        if damage == 'invented_reader': registry['entries'][0]['legacy_reader_id'] = 'host-selected-reader'
        elif damage == 'modified_projection':
            next(r for r in registry['entries'] if r['role'] == 'artifact')['identity_projection']['id_scheme'] = 'random128-v1'
        else:
            original = json.loads(target[EVIDENCE]); original['context_hash_algorithm'] = 'verification_context_hash-v1'
            replacement = encoded(original); previous = target[EVIDENCE]
            # Even rewritten registry hashes cannot waive the real original
            # archive addresses or its fixed source algorithm.
            paths = {p for p, raw in target.items() if raw == previous}
            for row in registry['entries']:
                if row['path'] in paths:
                    target[row['path']] = replacement
                    row['original_size'] = len(replacement)
                    row['original_byte_sha256'] = sha256(replacement).hexdigest()
        target[MANIFEST] = encoded(registry)
    with pytest.raises(ModelError): verify_migrated_history(target, project_id=project)


@pytest.mark.parametrize('algorithm', ['verification_context_hash-v1', 'reference01-verification-context-v2', ''])
def test_source_algorithm_is_fixed_not_selected_from_an_untrusted_label(algorithm):
    from support.reference01 import seal
    files = {p: raw for p, raw in evidence_source().items()
             if not p.startswith(('archive/', 'spec/baselines/'))}
    value = json.loads(files[EVIDENCE]); value['context_hash_algorithm'] = algorithm
    files[EVIDENCE] = encoded(value); seal(files)
    with pytest.raises(ModelError): verify_source_history(files)


@pytest.mark.parametrize('phase', ['source', 'migrated'])
def test_baseline_verifier_rejects_same_json_with_different_original_bytes(tmp_path, phase):
    old, target, _ = migrated(evidence_source())
    write_files(tmp_path, old if phase == 'source' else target)
    with no_write_attempts(), pytest.raises(ModelError, match='legacy_original_unregistered'):
        verify_baseline_snapshot(ProjectBoundary(tmp_path), old[BASELINE] + b'\n')


@pytest.mark.parametrize('damage', ['missing_manifest', 'missing_original', 'changed_original', 'symlink', 'open_transaction'])
def test_live_baseline_verifier_refuses_incomplete_or_unsafe_migrated_state(tmp_path, damage):
    old, target, _ = migrated(evidence_source())
    write_files(tmp_path, target)
    if damage == 'missing_manifest': (tmp_path/MANIFEST).unlink()
    elif damage == 'open_transaction': (tmp_path/'.specroad/transactions/pending').mkdir(parents=True)
    else:
        path = next(p for p in target if p.startswith('archive/objects/'))
        file = tmp_path/path
        if damage == 'changed_original': file.write_bytes(b'changed')
        else:
            file.unlink()
            if damage == 'symlink': file.symlink_to(tmp_path/EVIDENCE)
    with no_write_attempts(), pytest.raises((ModelError, SafetyViolation, FileNotFoundError)):
        verify_baseline_snapshot(ProjectBoundary(tmp_path), old[BASELINE])


def test_live_original_change_during_history_report_is_rechecked(tmp_path):
    from specroad.migration import history
    old, target, _ = migrated(evidence_source()); write_files(tmp_path, target)
    original = history._baseline_report
    def changed(*args, **kwargs):
        report = original(*args, **kwargs)
        (tmp_path/EVIDENCE).write_bytes(old[EVIDENCE] + b'\n')
        return report
    with patch.object(history, '_baseline_report', changed), pytest.raises(ModelError, match='legacy_manifest_changed'):
        verify_baseline_snapshot(ProjectBoundary(tmp_path), old[BASELINE])


@pytest.mark.parametrize('path', [BASELINE, EVIDENCE])
def test_format_and_write_target_reject_qualified_legacy_originals(tmp_path, path):
    _, target, _ = migrated(evidence_source()); write_files(tmp_path, target)
    source = ProjectSource(tmp_path); before = inventory(tmp_path)
    with no_write_attempts():
        with pytest.raises(ModelError, match='legacy_immutable_write_forbidden'):
            prepare_normalization(source, path)
        with pytest.raises(ModelError, match='legacy_immutable_write_forbidden'):
            source.require_write_target(path)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('operation', ['update', 'transition', 'retire'])
@pytest.mark.parametrize('projection', [False, True])
def test_update_and_lifecycle_cannot_rewrite_historical_values(operation, projection):
    from specroad.changes.lifecycle import prepare_change_lifecycle_bytes
    old, _, manifest, evidence, _, _ = observation()
    raw = canonical_json_bytes(evidence.navigation) if projection else evidence.source_bytes
    operations = [{'op': operation, 'target': evidence.id, **{
        'update': {'expected_revision': evidence.data['revision'], 'patch':
            [{'op': 'replace', 'path': '/title', 'value': 'Forbidden historical rewrite'}]},
        'transition': {'from': 'approved', 'to': 'retired', 'metadata': {'reason': 'Synthetic refusal'}},
        'retire': {'expected_revision': evidence.data['revision'], 'reason': 'Synthetic refusal'}
    }[operation]}]
    # Validate real source bytes first; even a plausible projected identity
    # cannot enter the current-schema lifecycle fold.
    with no_write_attempts(), pytest.raises(ModelError, match='schema|version'):
        prepare_change_lifecycle_bytes([raw], operations,
            metadata_policy_version='change-metadata-v1',
            actor={'actor_type': 'tool', 'actor_id': 'synthetic-editor'},
            planned_at='2026-11-04T00:00:00Z')
    assert manifest.artifact(EVIDENCE, old[EVIDENCE]).source_bytes == old[EVIDENCE]


def test_actual_writer_requires_host_for_current_verification_contract(tmp_path):
    from specroad.changes.schema_transition import SchemaTransitionError
    from support.migration_transaction import setup, apply, normative, journal_path
    root, old, plan, args = setup(tmp_path, files=evidence_source(nested=True))
    with pytest.raises(SchemaTransitionError, match='migration_target_validation_failed'):
        apply(root, plan, args)
    assert normative(root) == old
    assert not journal_path(root, args).exists()
