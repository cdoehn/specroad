"""Complete source registration, original read paths and distinct hash domains."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from unittest.mock import patch
import pytest

from specroad.migration.legacy_manifest import validate_legacy_manifest, LegacyArtifact
from specroad.model.errors import ModelError
from specroad.storage.project import ProjectSource
from specroad.storage.artifact_common import read_common_artifact, CommonArtifact
from specroad.storage.record_artifact import read_record_artifact
from specroad.storage.domain_artifact import read_domain_artifact
from specroad.storage.relations import read_source_relations
from specroad.storage.inventory import inventory_project
from specroad.storage.model_root import prepare_model_root
from specroad.storage.resource_discovery import current_json_paths
from specroad.profiles.composition import compose_profiles
from specroad.storage.profiles import read_profile
from specroad.query.show import show_artifact
from support.legacy_manifest import MANIFEST, BASELINE, PROJECT_ID, migrated, write_files
from support.reference01 import full_project, finish_proposal, seal, digest, encoded
from support.migration_plans import vector_source


def test_registry_requalifies_complete_transitive_history_and_owned_originals():
    files = full_project(); seal(files, 3)
    old, target, _ = migrated(files)
    registry = validate_legacy_manifest(target, project_id=PROJECT_ID)
    assert registry.data == json.loads(target[MANIFEST])
    assert registry.sha256 == digest(json.loads(target[MANIFEST]))
    assert {p for p, _, _ in registry.byte_bindings} == {MANIFEST} | {r['path'] for r in registry.data['entries']}
    assert all(target[p] == raw for p, raw in old.items() if p.startswith('archive/'))
    data = registry.data; data['entries'].clear()
    assert registry.data['entries']


@pytest.mark.parametrize('path', [BASELINE, 'spec/evidence/SR-EVD-0001.json',
    'spec/relation-reviews/SR-RREV-0001.json'])
def test_regular_bound_reader_preserves_immutable_original_without_current_schema_claim(tmp_path, path):
    old, target, _ = migrated(full_project()); write_files(tmp_path, target)
    # Select the fixture's actual closed record path by type when directory names differ.
    expected = 'baseline' if path == BASELINE else 'evidence' if '/evidence/' in path else 'relation_review'
    path = next(p for p, raw in old.items() if p.startswith('spec/') and json.loads(raw)['artifact_type'] == expected)
    for reader in (read_common_artifact, read_record_artifact):
        value = reader(ProjectSource(tmp_path), path, expected_type=expected)
        assert type(value) is LegacyArtifact
        assert value.storage_class == 'legacy_immutable' and value.schema_version == '0.1.0'
        assert value.source_bytes == old[path] and value.data == json.loads(old[path])
        assert value.navigation['schema_version'] == '0.1.0'
        assert value.navigation['id_scheme'] == 'legacy-sequential-v1'
    assert {p.relative_to(tmp_path).as_posix(): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == target


@pytest.mark.parametrize('status', ['applied', 'rejected', 'stale'])
def test_completed_proposals_are_regularly_readable_originals(tmp_path, status):
    old, target, _ = migrated(finish_proposal(full_project(), status)); write_files(tmp_path, target)
    path = 'spec/proposals/SR-PROP-0001.json'
    value = read_record_artifact(ProjectSource(tmp_path), path)
    assert value.source_bytes == old[path] and value.data['proposal_status'] == status
    assert value.storage_class == 'legacy_immutable'


def test_current_mutable_reader_still_requires_current_schema(tmp_path):
    _, target, _ = migrated(); write_files(tmp_path, target)
    path = 'spec/requirements/SR-REQ-0001.json'
    value = read_domain_artifact(ProjectSource(tmp_path), path)
    assert value.data['schema_version'] == '0.2.0' and value.source_bytes == target[path]
    assert type(read_common_artifact(ProjectSource(tmp_path), path)) is CommonArtifact


def test_unregistered_old_schema_is_not_sufficient_to_read(tmp_path):
    _, target, _ = migrated(); del target[MANIFEST]; write_files(tmp_path, target)
    with pytest.raises(ModelError, match='legacy_manifest_required'):
        read_common_artifact(ProjectSource(tmp_path), BASELINE)


def test_navigation_is_detached_and_never_replaces_original_relations(tmp_path):
    old, target, _ = migrated(); write_files(tmp_path, target)
    record = read_common_artifact(ProjectSource(tmp_path), BASELINE)
    navigation = record.navigation
    assert 'relation_id' in navigation['relations'][0]
    assert 'relation_id' not in record.data['relations'][0]
    assert record.source_bytes == old[BASELINE]
    navigation['relations'].clear()
    assert record.navigation['relations']
    relation_source = read_source_relations(ProjectSource(tmp_path), BASELINE)
    assert relation_source.storage_class == 'legacy_immutable'
    assert relation_source.source_bytes == old[BASELINE]
    assert relation_source.data == json.loads(old[BASELINE])
    assert relation_source.relations[0].data == record.navigation['relations'][0]


@pytest.mark.parametrize('strategy', ['scan', 'indexed'])
def test_public_show_navigates_legacy_edges_but_returns_original_artifact(tmp_path, strategy):
    old, target, _ = migrated(); write_files(tmp_path, target)
    result = show_artifact(tmp_path, 'SR-BASE-0001', strategy=strategy)
    assert result.exit_code == 0
    data = result.as_dict()['result']
    assert data['artifact'] == json.loads(old[BASELINE])
    assert data['outgoing'][0]['stored_relation']['relation_id'].startswith('REL-')
    assert not result.as_dict()['summary']['approval_granted']


def test_complete_inventory_accepts_only_manifest_qualified_legacy(tmp_path):
    _, target, _ = migrated(); write_files(tmp_path, target)
    rows = inventory_project(ProjectSource(tmp_path)).data['resources']
    assert next(r for r in rows if r['path'] == BASELINE)['sha256'] == sha256(target[BASELINE]).hexdigest()
    assert next(r for r in rows if r['path'] == MANIFEST)['canonical_sha256'] == digest(json.loads(target[MANIFEST]))


def test_regular_model_root_agrees_with_native_plan_and_binds_byte_domain(tmp_path):
    _, target, plan = migrated(); write_files(tmp_path, target)
    source = ProjectSource(tmp_path)
    profile = read_profile(source, 'profiles/core.json', expected_key='core@0.2.0',
                           expected_sha256=digest(json.loads(target['profiles/core.json'])))
    effective = compose_profiles((profile,), core_key=profile.key,
                                  project_profiles=source.configuration.data['profiles'])
    descriptor = plan.data['operations'][0]['target_manifest']['scope_descriptor']
    result = prepare_model_root(source, current_json_paths(source),
        scope_descriptor=descriptor, effective_profile=effective.data)
    assert result.data == plan.data['operations'][0]['target_manifest']
    assert result.sha256 == plan.data['expected_result']['model_root_sha256']
    row = next(r for r in result.data['artifacts'] if r['id'] == 'SR-BASE-0001')
    assert row['hash_domain'] == 'legacy-original-bytes-v1'
    assert row['sha256'] == sha256(target[BASELINE]).hexdigest()
    assert row['legacy_manifest_sha256'] == digest(json.loads(target[MANIFEST]))


def test_even_empty_explicit_scope_binds_registered_manifest_and_archive(tmp_path):
    _, target, plan = migrated(); write_files(tmp_path, target)
    from specroad.storage.model_root import capture_model_inputs
    captured = capture_model_inputs(ProjectSource(tmp_path), ())
    rows = [r.data for r in captured.resources]
    assert next(r for r in rows if r['kind'] == 'mapping')['id'] == 'legacy-preservation'
    assert {r['path'] for r in rows if r['kind'] == 'archive'} == {p for p in target if p.startswith('archive/objects/')}
    assert not any(r['kind'] == 'artifact' for r in rows)


def test_different_current_revision_can_coexist_with_archived_original(tmp_path):
    _, target, _ = migrated(vector_source())
    path = 'spec/requirements/SR-REQ-0001.json'
    value = json.loads(target[path]); value['revision'] += 1; value['title'] = 'Later title'
    target[path] = encoded(value); write_files(tmp_path, target)
    assert read_domain_artifact(ProjectSource(tmp_path), path).data['title'] == 'Later title'


@pytest.mark.parametrize('changed', ['manifest', 'original', 'archive'])
def test_reader_detects_bound_bytes_changed_after_capture(tmp_path, changed):
    _, target, _ = migrated(); write_files(tmp_path, target)
    source = ProjectSource(tmp_path); source.check_current()
    path = MANIFEST if changed == 'manifest' else BASELINE if changed == 'original' else next(p for p in target if p.startswith('archive/objects/'))
    (tmp_path/path).write_bytes(target[path] + b' ')
    expected_reason = ('legacy_original_bytes_changed' if changed == 'original'
                       else 'legacy_manifest_changed')
    with pytest.raises(ModelError) as caught:
        read_common_artifact(source, BASELINE)
    assert caught.value.reason == expected_reason
    assert caught.value.exit_code == 6 and caught.value.path == path
    assert (tmp_path/path).read_bytes() == target[path] + b' '


def test_registration_checks_have_no_writes_processes_or_mutable_aliases(tmp_path):
    _, target, _ = migrated(); write_files(tmp_path, target)
    with patch.object(Path, 'write_bytes', side_effect=AssertionError('write')), \
         patch.object(Path, 'write_text', side_effect=AssertionError('write')), \
         patch.object(subprocess, 'run', side_effect=AssertionError('process')):
        value = read_record_artifact(ProjectSource(tmp_path), BASELINE)
        assert value.source_bytes == target[BASELINE]
    assert not (tmp_path/'.specroad').exists()


@pytest.mark.parametrize('spelling', ['1.0', '1e0'])
def test_integral_source_number_spelling_preserves_original_byte_hash(tmp_path, spelling):
    from support.migration_relations import immutable_source
    from specroad.storage.model_root import capture_model_inputs
    files = immutable_source()
    value = json.loads(files[BASELINE])
    raw = json.dumps(value, sort_keys=True).replace('"revision": 1,', '"revision": ' + spelling + ',').encode()
    assert raw != files[BASELINE] and json.loads(raw)['revision'] == 1
    files[BASELINE] = raw
    old, target, _ = migrated(files); write_files(tmp_path, target)
    original = read_common_artifact(ProjectSource(tmp_path), BASELINE)
    assert original.source_bytes == raw == old[BASELINE]
    captured = capture_model_inputs(ProjectSource(tmp_path), (BASELINE,))
    row = next(r.data for r in captured.resources if r.data['kind'] == 'artifact')
    assert row['revision'] == 1 and row['sha256'] == sha256(raw).hexdigest()
    assert row['hash_domain'] == 'legacy-original-bytes-v1'
