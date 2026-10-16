"""Independent archived-byte verification, with no original tree or Git."""
from hashlib import sha256
import json
import os
import shutil

import pytest

from specroad.archive import build_baseline_manifest, verify_baseline_snapshot
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.security import ProjectBoundary, SafetyViolation
from support.model import put
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import record_value, ref
from support.scopes import descriptor
from test_baseline_manifest import baseline_inputs


def stored_snapshot(root, *, kind='working', attachment=b'\x00\xff\r\n'):
    root.mkdir()
    inputs = baseline_inputs(scope=descriptor('project'), attachment=attachment)
    snapshot = build_baseline_manifest(**inputs, baseline_id=ref('BASE'))
    record = record_value('baseline', **{k: snapshot.data[k] for k in (
        'scope_descriptor', 'manifest', 'model_root_sha256', 'configuration_hash',
        'profiles', 'tool_version')}, baseline_kind=kind)
    for item in snapshot.objects:
        put(root, item.reference.path, item.content)
    return record, snapshot


def verify(root, record):
    return verify_baseline_snapshot(ProjectBoundary(root), canonical_json_bytes(record))


def row_for(record, role):
    return next(r for r in record['manifest'] if r['role'] == role)


def replace_object(root, row, raw):
    digest = sha256(raw).hexdigest()
    path = 'archive/objects/' + digest[:2] + '/' + digest
    put(root, path, raw)
    row.update(object_path=path, sha256=digest, size=len(raw))


@pytest.mark.parametrize('kind', ['working', 'release'])
def test_archived_snapshot_reconstructs_root_without_working_tree_or_git(tmp_path, kind):
    root = tmp_path / 'archive-only'
    record, snapshot = stored_snapshot(root, kind=kind)
    assert not (root / 'specroad.json').exists() and not (root / '.git').exists()
    before = inventory(root)
    with no_write_attempts():
        report = verify(root, record)
    assert report['snapshot_integrity_verified']
    assert report['baseline_id'] == record['id'] and report['baseline_kind'] == kind
    assert report['model_root_sha256'] == snapshot.model_root_sha256
    assert report['configuration_hash'] == snapshot.data['configuration_hash']
    assert report['checked_objects'] == len(snapshot.objects)
    assert report['checked_bytes'] == sum(len(o.content) for o in snapshot.objects)
    assert report['checked_artifacts'] == 2
    assert not any(report[k] for k in ('full_validation_passed', 'release_authorized',
        'write_authorized', 'project_completeness_verified', 'atomic_snapshot'))
    assert inventory(root) == before


def test_native_baseline_verifies_after_current_sources_change_and_archive_moves(tmp_path):
    from test_baseline_creation import project, plan_for, apply

    original = tmp_path / 'original'; model = project(original)
    plan = plan_for(model); apply(plan, model)
    record = plan.data['operations'][0]['record']
    (original / 'specroad.json').write_bytes(b'not the historical configuration')
    for document in model.documents:
        (original / document.path).write_bytes(b'changed current artifact')
    current_before = inventory(original)
    with no_write_attempts():
        assert verify(original, record)['snapshot_integrity_verified']
    assert inventory(original) == current_before
    moved = tmp_path / 'moved'; moved.mkdir()
    shutil.copytree(original / 'archive', moved / 'archive')
    shutil.rmtree(original)
    with no_write_attempts():
        result = verify(moved, record)
    assert result['model_root_sha256'] == record['model_root_sha256']
    assert not original.exists()


@pytest.mark.parametrize('role', ['artifact', 'profile', 'rule', 'mapping', 'attachment',
                                  'semantic_configuration', 'effective_profile', 'model_manifest'])
def test_every_missing_referenced_object_prevents_success(tmp_path, role):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    row = row_for(record, role); (root / row['object_path']).unlink()
    before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        verify(root, record)
    assert error.value.reason == 'snapshot_referenced_object_missing'
    assert inventory(root) == before


def test_same_length_changed_object_is_rejected_by_actual_byte_hash(tmp_path):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    row = row_for(record, 'attachment'); path = root / row['object_path']
    raw = path.read_bytes(); path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
    with pytest.raises(ModelError) as error:
        verify(root, record)
    assert error.value.reason == 'snapshot_object_hash_mismatch'


def test_declared_root_cannot_replace_independent_reconstruction(tmp_path):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    record['model_root_sha256'] = '0' * 64
    with pytest.raises(ModelError) as error:
        verify(root, record)
    assert error.value.reason == 'baseline_model_root_mismatch'


def test_self_consistent_stored_manifest_and_root_still_need_actual_resources(tmp_path):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    row = row_for(record, 'model_manifest')
    value = json.loads((root / row['object_path']).read_bytes())
    value['configuration_sha256'] = 'a' * 64
    replace_object(root, row, canonical_json_bytes(value))
    record['model_root_sha256'] = row['sha256']
    with pytest.raises(ModelError) as error:
        verify(root, record)
    assert error.value.reason == 'baseline_model_root_mismatch'


def test_configuration_rebinding_cannot_reuse_the_original_root(tmp_path):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    row = row_for(record, 'semantic_configuration')
    value = json.loads((root / row['object_path']).read_bytes())
    value['validation_policy']['fail_on'] = 'warning'
    replace_object(root, row, canonical_json_bytes(value))
    record['configuration_hash'] = row['sha256']
    with pytest.raises(ModelError) as error:
        verify(root, record)
    assert error.value.reason == 'baseline_model_root_mismatch'


def test_effective_profile_is_recomposed_from_stored_profile_objects(tmp_path):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    row = row_for(record, 'effective_profile')
    value = json.loads((root / row['object_path']).read_bytes())
    value['merge']['severity_overrides']['forged:rule'] = 'warning'
    replace_object(root, row, canonical_json_bytes(value))
    with pytest.raises(ModelError) as error:
        verify(root, record)
    assert error.value.reason == 'baseline_effective_profile_mismatch'


def test_omitting_an_artifact_row_cannot_claim_the_original_complete_manifest(tmp_path):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    record['manifest'].remove(row_for(record, 'artifact'))
    with pytest.raises(ModelError):
        verify(root, record)


@pytest.mark.parametrize('kind', ['symlink', 'hardlink'])
def test_archive_object_reads_cannot_follow_links(tmp_path, kind):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    row = row_for(record, 'attachment'); path = root / row['object_path']
    outside = tmp_path / 'outside'; outside.write_bytes(path.read_bytes()); path.unlink()
    if kind == 'symlink': path.symlink_to(outside)
    else: os.link(outside, path)
    before = outside.read_bytes()
    with no_write_attempts(), pytest.raises(SafetyViolation):
        verify(root, record)
    assert outside.read_bytes() == before


def test_untrusted_object_path_cannot_escape_archive_boundary(tmp_path):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    row_for(record, 'attachment')['object_path'] = '../outside'
    with pytest.raises(ModelError) as error:
        verify(root, record)
    assert error.value.reason == 'baseline_snapshot_object_path_mismatch'


def test_duplicate_logical_metadata_cannot_be_hidden_by_object_deduplication(tmp_path):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    record['manifest'].append(dict(row_for(record, 'model_manifest')))
    with pytest.raises(ModelError) as error:
        verify(root, record)
    assert error.value.reason == 'baseline_snapshot_duplicate_value'


def test_one_object_may_back_an_artifact_and_an_exact_binary_attachment(tmp_path):
    from support.relations import artifact, edge, aid

    raw = canonical_json_bytes(artifact(relations=[edge('depends_on', aid(number=2))]))
    root = tmp_path / 'archive'; record, snapshot = stored_snapshot(root, attachment=raw)
    rows = [r for r in record['manifest'] if r['sha256'] == sha256(raw).hexdigest()]
    assert {r['role'] for r in rows} == {'artifact', 'attachment'}
    report = verify(root, record)
    assert report['checked_objects'] == len(snapshot.objects) == len(record['manifest']) - 1


@pytest.mark.parametrize('field', ['configuration_hash', 'profiles', 'tool_version'])
def test_missing_snapshot_metadata_never_produces_partial_verification(tmp_path, field):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    del record[field]
    with pytest.raises(ModelError) as error:
        verify(root, record)
    assert error.value.reason == 'baseline_snapshot_metadata_missing'


@pytest.mark.parametrize('scope', ['specification', 'configured'])
def test_unimplemented_scope_requires_an_explicit_future_provider(tmp_path, scope):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    if scope == 'specification': record['scope_descriptor'] = descriptor('specification')
    else: record['scope_descriptor']['configuration_id'] = ref('CFG')
    with pytest.raises(ModelError) as error:
        verify(root, record)
    assert error.value.reason == 'baseline_verification_scope_unsupported'


def test_repeated_verification_does_not_cache_previous_success(tmp_path):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    first = verify(root, record); first['scope_descriptor'].clear()
    assert verify(root, record)['snapshot_integrity_verified']
    row = row_for(record, 'rule'); (root / row['object_path']).unlink()
    with pytest.raises(ModelError) as error:
        verify(root, record)
    assert error.value.reason == 'snapshot_referenced_object_missing'


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_verification_runs_in_isolated_core_and_portable_distribution(tmp_path, mode):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    body = '''from pathlib import Path
from specroad.archive import verify_baseline_snapshot
from specroad.security import ProjectBoundary
'''
    body += 'result=verify_baseline_snapshot(ProjectBoundary(Path(' + repr(str(root)) + ')), ' + repr(canonical_json_bytes(record)) + ')\n'
    body += 'assert result["snapshot_integrity_verified"] and not result["release_authorized"]\n'
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c', 'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body],
                            tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
