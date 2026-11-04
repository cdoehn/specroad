"""Hostile registry and original-byte boundaries; no projected-current laundering."""
import json
from hashlib import sha256
from unittest.mock import patch
import pytest

from specroad.migration.legacy_manifest import validate_legacy_manifest, manifest_paths
from specroad.model.errors import ModelError
from specroad.model.canonical import canonical_json_bytes
from specroad.model.model_manifest import ProjectReadBinding
from specroad.storage.project import ProjectSource
from specroad.storage.artifact_common import read_common_artifact, CommonArtifact
from specroad.storage.record_artifact import RecordArtifact
from specroad.storage.model_root import capture_model_inputs, check_model_inputs_current
from specroad.storage.relations import read_source_relations
from specroad.graph.relations import SourceRelations
from support.legacy_manifest import MANIFEST, BASELINE, PROJECT_ID, migrated, write_files
from support.reference01 import encoded, full_project


def changed_manifest(target, change):
    target = dict(target); value = json.loads(target[MANIFEST]); change(value)
    target[MANIFEST] = encoded(value)
    return target


@pytest.mark.parametrize('field', ['source_schema_version', 'original_canonical_sha256',
    'legacy_reader_id', 'migration_provenance', 'identity_projection', 'referenced_payloads',
    'relation_projections', 'artifact_type', 'original_revision', 'extra'])
def test_manifest_field_tampering_cannot_supply_its_own_interpretation(field):
    _, target, _ = migrated()
    def alter(value):
        row = next(r for r in value['entries'] if r['path'] == BASELINE)
        row[field] = 'untrusted'
    bad = changed_manifest(target, alter)
    with pytest.raises(ModelError): validate_legacy_manifest(bad, project_id=PROJECT_ID)


@pytest.mark.parametrize('field', ['contract_sha256', 'contract_id', 'contract_version', 'project_id', 'schema_version'])
def test_source_contract_is_core_bound_not_manifest_selected(field):
    _, target, _ = migrated()
    bad = changed_manifest(target, lambda m: m['source'].update({field: 'forged'}))
    with pytest.raises(ModelError): validate_legacy_manifest(bad, project_id=PROJECT_ID)


@pytest.mark.parametrize('field', ['contract_sha256', 'project_id', 'schema_version'])
def test_target_contract_is_closed_and_bound(field):
    _, target, _ = migrated()
    bad = changed_manifest(target, lambda m: m['target'].update({field: 'forged'}))
    with pytest.raises(ModelError): validate_legacy_manifest(bad, project_id=PROJECT_ID)


@pytest.mark.parametrize('mutation', ['extra', 'duplicate', 'reorder', 'omitted', 'proposal-transition'])
def test_whole_manifest_membership_order_and_transition_contract_is_checked(mutation):
    _, target, _ = migrated()
    def alter(m):
        if mutation == 'extra': m['unknown'] = True
        if mutation == 'duplicate': m['entries'].append(m['entries'][0])
        if mutation == 'reorder': m['entries'].reverse()
        if mutation == 'omitted': m['entries'] = [r for r in m['entries'] if r['path'] != BASELINE]
        if mutation == 'proposal-transition': m['proposal_transitions'].append({'approved': True})
    with pytest.raises(ModelError):
        validate_legacy_manifest(changed_manifest(target, alter), project_id=PROJECT_ID)


@pytest.mark.parametrize('path', ['../secret', '/tmp/secret', '.git/config', '.codex/config.toml',
    'specroad.json', 'profiles/forged.json', 'archive/objects/00/' + '1'*64])
def test_unsafe_physical_destinations_rejected_before_read(path):
    _, target, _ = migrated()
    bad = changed_manifest(target, lambda m: m['entries'][0].update(path=path))
    with pytest.raises(ModelError): manifest_paths(bad[MANIFEST])


def test_projection_is_rejected_as_original_even_if_canonical_json_is_well_formed(tmp_path):
    _, target, _ = migrated(); write_files(tmp_path, target)
    source = ProjectSource(tmp_path)
    original = read_common_artifact(source, BASELINE)
    raw = canonical_json_bytes(original.navigation)
    for read in (CommonArtifact, RecordArtifact, SourceRelations):
        with pytest.raises(ModelError): read(raw, path=BASELINE)
    target[BASELINE] = raw; write_files(tmp_path, target)
    with pytest.raises(ModelError): read_common_artifact(ProjectSource(tmp_path), BASELINE)


def test_new_current_label_cannot_overwrite_registered_original(tmp_path):
    _, target, _ = migrated(); value = json.loads(target[BASELINE])
    value.update(schema_version='0.2.0', id_scheme='legacy-sequential-v1')
    target[BASELINE] = encoded(value); write_files(tmp_path, target)
    with pytest.raises(ModelError, match='legacy_original_bytes_changed'):
        read_common_artifact(ProjectSource(tmp_path), BASELINE)


def test_identical_semantics_with_other_original_bytes_is_conflict():
    _, target, _ = migrated()
    value = json.loads(target[MANIFEST]); row = next(r for r in value['entries'] if r['path'] == BASELINE)
    # Self-consistently rehash one registered physical copy; its historical
    # archive twin still has the same identity/revision but different bytes.
    target[BASELINE] += b' '
    row.update(original_size=len(target[BASELINE]), original_byte_sha256=sha256(target[BASELINE]).hexdigest())
    target[MANIFEST] = encoded(value)
    with pytest.raises(ModelError) as caught: validate_legacy_manifest(target, project_id=PROJECT_ID)
    assert caught.value.exit_code == 6
    assert caught.value.reason in ('legacy_original_conflict', 'legacy_original_revision_conflict')


@pytest.mark.parametrize('subject', ['current', 'archive', 'manifest'])
def test_write_target_authorization_refuses_protected_originals(tmp_path, subject):
    _, target, _ = migrated(); write_files(tmp_path, target)
    path = BASELINE if subject == 'current' else MANIFEST if subject == 'manifest' else next(p for p in target if p.startswith('archive/objects/'))
    with pytest.raises(ModelError, match='legacy_immutable_write_forbidden'):
        ProjectSource(tmp_path).require_write_target(path)


def test_mutable_write_path_is_rechecked_against_manifest_freshness(tmp_path):
    _, target, _ = migrated(); write_files(tmp_path, target)
    source = ProjectSource(tmp_path); source.check_current()
    (tmp_path/MANIFEST).write_bytes(target[MANIFEST] + b' ')
    with pytest.raises(ModelError, match='legacy_manifest_changed'):
        source.require_write_target('spec/requirements/SR-REQ-0001.json')


def test_legacy_resource_cannot_be_bound_to_a_different_project(tmp_path):
    _, target, _ = migrated(); write_files(tmp_path, target)
    original = read_common_artifact(ProjectSource(tmp_path), BASELINE)
    binding = ProjectReadBinding('foreign', str(tmp_path), (1, 2))
    with pytest.raises(ModelError, match='legacy_project_mismatch'):
        original.manifest_resource(binding)


def test_missing_and_symlink_archive_are_not_optional(tmp_path):
    _, target, _ = migrated(); write_files(tmp_path, target)
    archive = next(p for p in target if p.startswith('archive/objects/'))
    raw = target[archive]; path = tmp_path/archive; path.unlink()
    with pytest.raises((ModelError, OSError)): read_common_artifact(ProjectSource(tmp_path), BASELINE)
    outside = tmp_path/'untrusted'; outside.write_bytes(raw); path.symlink_to(outside)
    from specroad.security import SafetyViolation
    with pytest.raises((ModelError, OSError, SafetyViolation)):
        read_common_artifact(ProjectSource(tmp_path), BASELINE)


def test_model_capture_rechecks_manifest_and_historical_archive(tmp_path):
    _, target, _ = migrated(); write_files(tmp_path, target)
    source = ProjectSource(tmp_path); captured = capture_model_inputs(source, (BASELINE,))
    path = next(p for p in target if p.startswith('archive/objects/'))
    (tmp_path/path).write_bytes(target[path] + b' ')
    with pytest.raises(ModelError): check_model_inputs_current(source, captured)


def test_reader_does_not_qualify_model_before_the_model_phase(tmp_path):
    _, target, _ = migrated(); write_files(tmp_path, target)
    with patch('specroad.storage.legacy.capture_legacy_manifest', side_effect=AssertionError('early model read')):
        source = ProjectSource(tmp_path)
        assert source.configuration.project_id == PROJECT_ID
    assert read_common_artifact(source, BASELINE).storage_class == 'legacy_immutable'


def test_source_schema_stays_builtin_even_if_old_schema_claim_is_rehashed():
    _, target, _ = migrated(); value = json.loads(target[MANIFEST])
    row = next(r for r in value['entries'] if r['logical_path'] == BASELINE)
    raw = json.loads(target[row['path']]); raw['unrecognized_normative_field'] = True
    changed = encoded(raw); new_hash = sha256(changed).hexdigest()
    old_path = row['path']; address = 'archive/objects/' + new_hash[:2] + '/' + new_hash
    # Rehash every alias of the baseline; the qualified source schema must still reject it.
    for item in value['entries']:
        if item['logical_path'] == BASELINE:
            if item['path'].startswith('archive/objects/'): item['path'] = address
            item.update(original_size=len(changed), original_byte_sha256=new_hash,
                        original_canonical_sha256=sha256(encoded(raw)).hexdigest())
            target[item['path']] = changed
    value['entries'].sort(key=lambda r: (r['path'], r['source_model_root_sha256'], r['logical_path']))
    target[MANIFEST] = encoded(value)
    with pytest.raises(ModelError): validate_legacy_manifest(target, project_id=PROJECT_ID)


def test_wrong_expected_type_never_uses_legacy_bypass(tmp_path):
    _, target, _ = migrated(); write_files(tmp_path, target)
    with pytest.raises(ModelError, match='artifact_type_mismatch'):
        read_common_artifact(ProjectSource(tmp_path), BASELINE, expected_type='requirement')


def test_source_relations_cannot_be_constructed_from_a_raw_navigation_dictionary(tmp_path):
    _, target, _ = migrated(); write_files(tmp_path, target)
    original = read_common_artifact(ProjectSource(tmp_path), BASELINE)
    with pytest.raises(ModelError, match='legacy_original_required'):
        SourceRelations.from_legacy(original.navigation)
