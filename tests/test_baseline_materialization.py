"""Fresh Baseline views and independent restoration of actual archived bytes."""
from hashlib import sha256
import json
import os
import socket
import subprocess

import pytest

from specroad.archive import show_baseline_snapshot, materialize_baseline_snapshot
from specroad.model.canonical import canonical_json_bytes
from specroad.model.configuration import ProjectConfiguration
from specroad.model.errors import ModelError
from specroad.model.semantic_configuration import semantic_configuration
from specroad.security import ProjectBoundary, SafetyViolation
from support.model import put
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from test_baseline_verification import stored_snapshot, row_for


def show(root, record):
    return show_baseline_snapshot(ProjectBoundary(root), canonical_json_bytes(record))


def restore(root, record, destination, **options):
    return materialize_baseline_snapshot(ProjectBoundary(root), canonical_json_bytes(record),
        destination, **{'default_locale': 'en-GB', 'generated_path': 'output',
                       'protected_roots': (ProjectBoundary(root),), **options})


@pytest.mark.parametrize('kind', ['working', 'release'])
def test_show_returns_stored_manifest_and_fresh_integrity_without_writes(tmp_path, kind):
    root = tmp_path / 'archive'; record, snapshot = stored_snapshot(root, kind=kind)
    before = inventory(root)
    with no_write_attempts(): result = show(root, record)
    assert result['format_version'] == 'baseline-show-v1'
    assert result['baseline'] == record
    assert result['integrity']['status'] == 'verified'
    assert result['integrity']['verification']['model_root_sha256'] == snapshot.model_root_sha256
    assert not result['integrity']['verification']['release_authorized']
    assert inventory(root) == before


@pytest.mark.parametrize('change', ['missing', 'changed', 'declared_root'])
def test_show_recomputes_failure_instead_of_reusing_a_prior_success(tmp_path, change):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    first = show(root, record); first['baseline']['manifest'].clear()
    path = root / row_for(record, 'attachment')['object_path']
    if change == 'missing': path.unlink()
    elif change == 'changed': path.write_bytes(b'corrupt')
    else: record['model_root_sha256'] = '0' * 64
    before = inventory(root)
    with no_write_attempts(): result = show(root, record)
    assert result['baseline'] == record
    assert result['integrity']['status'] == 'failed'
    assert not result['integrity']['snapshot_integrity_verified']
    assert result['integrity']['verification'] is None
    assert len(result['integrity']['diagnostics']) == 1
    assert inventory(root) == before


@pytest.mark.parametrize('raw', [b'{', b'{}', None])
def test_show_cannot_return_a_malformed_record_as_a_baseline(tmp_path, raw):
    with no_write_attempts(), pytest.raises(ModelError):
        show_baseline_snapshot(ProjectBoundary(tmp_path), raw)


@pytest.mark.parametrize('kind', ['working', 'release'])
def test_materialized_project_preserves_snapshot_values_and_semantic_root(tmp_path, kind, monkeypatch):
    root = tmp_path / 'archive'; record, snapshot = stored_snapshot(root, kind=kind)
    target = tmp_path / 'restored'; before = inventory(root)
    def forbidden(*args, **kwargs): raise AssertionError('No process or network is needed')
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(socket, 'socket', forbidden)
    result = restore(root, record, target)
    assert not (root / '.git').exists() and not (target / '.git').exists()
    assert not (target / 'spec/baselines').exists()
    assert result['materialization_complete'] and result['snapshot_integrity_verified']
    assert result['model_root_sha256'] == snapshot.model_root_sha256
    assert result['configuration_hash'] == snapshot.data['configuration_hash']
    assert result['profile_sha256'] == snapshot.data['profile_sha256']
    assert not any(result[k] for k in ('atomic_publication', 'full_validation_passed',
                                      'write_authorized', 'release_authorized'))
    files = {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob('*') if p.is_file()}
    expected = {row['source_path']: (root / row['object_path']).read_bytes()
                for row in record['manifest'] if row['role'] not in
                ('semantic_configuration', 'effective_profile', 'model_manifest')}
    configuration = ProjectConfiguration(json.loads(files.pop('specroad.json')))
    assert configuration.data['default_locale'] == 'en-GB'
    assert configuration.generated_path == 'output'
    semantic = canonical_json_bytes(semantic_configuration(configuration))
    assert semantic == (root / row_for(record, 'semantic_configuration')['object_path']).read_bytes()
    assert files == expected
    for item in result['files']:
        raw = (target / item['path']).read_bytes()
        assert item['sha256'] == sha256(raw).hexdigest() and item['size'] == len(raw)
    assert inventory(root) == before


@pytest.mark.parametrize('raw', [b'', b'\x00\xff\r\n', b'\x00' * 70000])
def test_materialization_preserves_exact_binary_attachment_bytes(tmp_path, raw):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root, attachment=raw)
    target = tmp_path / 'restored'; restore(root, record, target)
    assert (target / 'attachments/manual.bin').read_bytes() == raw


@pytest.mark.parametrize('role', ['artifact', 'profile', 'rule', 'mapping', 'attachment',
                                  'semantic_configuration', 'effective_profile', 'model_manifest'])
def test_missing_original_object_cannot_fall_back_to_current_files(tmp_path, role):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    row = row_for(record, role); raw = (root / row['object_path']).read_bytes()
    (root / row['object_path']).unlink()
    if 'source_path' in row: put(root, row['source_path'], raw)
    target = tmp_path / 'restored'; before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        restore(root, record, target)
    assert error.value.reason == 'snapshot_referenced_object_missing'
    assert not target.exists() and inventory(tmp_path) == before


@pytest.mark.parametrize('kind', ['directory', 'file', 'symlink'])
def test_existing_target_is_never_replaced_even_if_empty(tmp_path, kind):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    target = tmp_path / 'restored'; outside = tmp_path / 'outside'; outside.write_bytes(b'keep')
    if kind == 'directory': target.mkdir()
    elif kind == 'file': target.write_bytes(b'existing')
    else: target.symlink_to(outside)
    before = inventory(tmp_path)
    with pytest.raises(FileExistsError): restore(root, record, target)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('case', ['archive', 'protected', 'project_parent', 'public_parent'])
def test_destination_must_be_private_external_and_outside_protected_inputs(tmp_path, case):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    other = tmp_path / 'other'; other.mkdir(mode=0o700)
    target = (root if case == 'archive' else other) / 'restored'
    protected = (ProjectBoundary(root), ProjectBoundary(other)) if case == 'protected' else (ProjectBoundary(root),)
    if case == 'project_parent': (other / 'specroad.json').write_bytes(b'{}')
    if case == 'public_parent': other.chmod(0o755)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(SafetyViolation):
        restore(root, record, target, protected_roots=protected)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('protected', [(), [], ('not-a-boundary',)])
def test_materialization_requires_explicit_protected_boundaries(tmp_path, protected):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        restore(root, record, tmp_path / 'restored', protected_roots=protected)
    assert error.value.reason == 'baseline_materialization_protected_roots_required'


def test_conflicting_operational_output_path_is_rejected_before_creation(tmp_path):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    with no_write_attempts(), pytest.raises(ModelError):
        restore(root, record, tmp_path / 'restored', generated_path='spec')
    assert not (tmp_path / 'restored').exists()


def test_failed_write_retains_partial_output_without_publishing_configuration(tmp_path, monkeypatch):
    from specroad.changes import _staging_files

    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    target = tmp_path / 'restored'; before = inventory(root)
    original = _staging_files._write_new
    def fail_after_write(parent, name, raw):
        original(parent, name, raw)
        raise OSError('injected storage failure')
    monkeypatch.setattr(_staging_files, '_write_new', fail_after_write)
    with pytest.raises(OSError): restore(root, record, target)
    assert target.is_dir() and any(p.is_file() for p in target.rglob('*'))
    assert not (target / 'specroad.json').exists()
    assert inventory(root) == before
    retained = inventory(target)
    with pytest.raises(FileExistsError): restore(root, record, target)
    assert inventory(target) == retained


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_show_and_materialization_run_without_installed_dependencies_or_git(tmp_path, mode):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    target = tmp_path / 'restored'
    code = '''from pathlib import Path
from specroad.archive import show_baseline_snapshot, materialize_baseline_snapshot
from specroad.security import ProjectBoundary
'''
    code += 'boundary=ProjectBoundary(' + repr(str(root)) + ')\n'
    code += 'record=' + repr(canonical_json_bytes(record)) + '\n'
    code += 'assert show_baseline_snapshot(boundary,record)["integrity"]["snapshot_integrity_verified"]\n'
    code += 'result=materialize_baseline_snapshot(boundary,record,' + repr(str(target)) + ',default_locale="de-DE",generated_path="output",protected_roots=(boundary,))\n'
    code += 'assert result["materialization_complete"] and not result["release_authorized"]\n'
    if mode == 'core': result = run_core(code, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c', 'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + code],
                            tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
