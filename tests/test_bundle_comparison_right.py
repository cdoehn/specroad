"""15.h.R: full-source boundaries and retained bundle observations."""
import importlib
import json

import pytest

from specroad.bundles import (BundleContainer, BundleError, prepare_partial_bundle,
                              prepare_project_bundle, verify_bundle)
from specroad.cli.application import dispatch_result, execute_request
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.query import ComparisonSourceSnapshot, compare_sources, diff_project
from specroad.query.project_diff import _diff_steps
from specroad.security import ProjectBoundary
from specroad.storage.archive import encode_archive
from support.git_objects import GitFixture
from support.model import put
from support.read_only import inventory, no_write_attempts
from test_bundle_comparison import captured
from test_bundle_verification import rebind
from test_partial_bundle import project as partial_project, scope
from test_project_bundle import project


@pytest.mark.parametrize('filename', [None, True, 12, b'input.zip', [], {}, '', ' ',
                                      'bad\0/input.zip', '\ud800/input.zip'])
def test_invalid_bundle_selector_fails_before_filesystem_access(tmp_path, monkeypatch, filename):
    module = importlib.import_module('specroad.query.bundle_source')
    monkeypatch.setattr(module, 'ProjectBoundary', lambda *a: pytest.fail('Invalid selector opened a root'))
    with no_write_attempts(), pytest.raises(ModelError):
        ComparisonSourceSnapshot(filename, kind='bundle')


@pytest.mark.parametrize('kind', ['document', 'release'])
@pytest.mark.parametrize('mode', ['direct', 'cli', 'structured'])
def test_public_diff_never_promotes_verified_partial_bundle(tmp_path, kind, mode):
    root = tmp_path / 'source'; partial_project(root, kind)
    bundle = prepare_partial_bundle(root, scope(kind))
    assert verify_bundle(bundle.source_bytes)['validation_scope'] == 'partial_payload_model'
    filename = tmp_path / 'input.zip'; filename.write_bytes(bundle.source_bytes)
    before = inventory(tmp_path)
    with no_write_attempts():
        if mode == 'direct':
            result = diff_project(root, str(filename), against_kind='bundle')
        elif mode == 'cli':
            result = dispatch_result(['diff', '--project', str(root), '--against', str(filename),
                                      '--against-kind', 'bundle'], cwd=tmp_path)
        else:
            result = execute_request({'command_id': 'diff', 'options': {'--project': str(root),
                '--against': filename.name, '--against-kind': 'bundle'}}, cwd=tmp_path).result
    assert result.exit_code == 3 and result.as_dict()['result'] is None
    assert any(d['rationale'] == 'comparison_full_project_required' for d in result.as_dict()['diagnostics'])
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('other_kind', ['local', 'git', 'bundle'])
def test_foreign_project_pairs_fail_in_both_directions(tmp_path, other_kind):
    root = tmp_path / 'source'; project(root)
    _, before = captured(root, tmp_path / 'input.zip')
    config = json.loads((root / 'specroad.json').read_bytes()); config['project_id'] = 'foreign'
    put(root, 'specroad.json', canonical_json_bytes(config))
    local = ComparisonSourceSnapshot(root)
    if other_kind == 'git':
        fixture = GitFixture(tmp_path / 'git')
        commit = fixture.commit(dict(local.resources))
        after = ComparisonSourceSnapshot(fixture.root, kind='git', reference=commit)
    elif other_kind == 'bundle':
        _, after = captured(root, tmp_path / 'foreign.zip')
    else:
        after = local
    original = inventory(tmp_path)
    with no_write_attempts():
        for left, right in ((before, after), (after, before)):
            with pytest.raises(ModelError) as failure:
                compare_sources(left, right)
            assert failure.value.reason == 'comparison_project_mismatch'
        result = diff_project(root, str(tmp_path / 'input.zip'), against_kind='bundle')
    assert result.exit_code == 3 and result.as_dict()['result'] is None
    assert inventory(tmp_path) == original


@pytest.mark.parametrize('fault', ['missing_attachment', 'missing_profile', 'missing_registry',
                                  'artifact_schema', 'configuration_schema', 'manifest_identity'])
def test_invalid_bundle_never_borrows_valid_nearby_project_files(tmp_path, monkeypatch, fault):
    root = tmp_path / 'source'; model = project(root)
    bundle = prepare_project_bundle(root)
    files = bundle.files
    metadata = bundle.manifest; metadata.pop('entries')
    if fault.startswith('missing_'):
        path = {'missing_attachment': 'attachments/owned.bin', 'missing_profile': 'profiles/core.json',
                'missing_registry': model.registry_path}[fault]
        del files[path]
    elif fault == 'artifact_schema':
        path = next(p for p in files if p.startswith('spec/requirements/'))
        value = json.loads(files[path]); value['schema_version'] = '99.0.0'
        files[path] = canonical_json_bytes(value)
    elif fault == 'configuration_schema':
        value = json.loads(files['specroad.json']); value['schema_version'] = '99.0.0'
        files['specroad.json'] = canonical_json_bytes(value)
        metadata['schema_version'] = '99.0.0'
    else:
        metadata['project_id'] = 'forged-foreign-manifest'
    raw = encode_archive('bundle-manifest.json', metadata, files)
    if fault not in ('configuration_schema', 'manifest_identity'):
        assert BundleContainer(raw).files == files  # Transport hashes are intact.
    filename = root / 'input.zip'; filename.write_bytes(raw)
    original = inventory(tmp_path)
    read = ProjectBoundary.read_bytes

    def explicit(boundary, name):
        assert boundary.root == root and name == filename.name
        return read(boundary, name)

    monkeypatch.setattr(ProjectBoundary, 'read_bytes', explicit)
    with no_write_attempts(), pytest.raises(BundleError) as failure:
        ComparisonSourceSnapshot(filename, kind='bundle')
    assert failure.value.exit_code == 3
    assert inventory(tmp_path) == original


def test_disappearance_after_first_bundle_read_is_an_observed_change(tmp_path, monkeypatch):
    root = tmp_path / 'source'; project(root)
    filename = tmp_path / 'input.zip'; captured(root, filename)
    read = ProjectBoundary.read_bytes

    def disappear(boundary, name):
        raw = read(boundary, name)
        if boundary.root == tmp_path and name == filename.name:
            filename.unlink()
        return raw

    monkeypatch.setattr(ProjectBoundary, 'read_bytes', disappear)
    with pytest.raises(ModelError) as failure:
        ComparisonSourceSnapshot(filename, kind='bundle')
    assert failure.value.reason == 'comparison_source_changed' and not filename.exists()


@pytest.mark.parametrize('missing_parent', [False, True])
def test_initially_missing_file_keeps_the_environment_failure_without_fallback(tmp_path, missing_parent):
    root = tmp_path / 'source'; project(root)
    filename = (tmp_path / 'absent' if missing_parent else root) / 'input.zip'
    original = inventory(tmp_path)
    with no_write_attempts():
        result = diff_project(root, str(filename), against_kind='bundle')
    assert result.exit_code == 5 and result.as_dict()['result'] is None
    assert inventory(tmp_path) == original


@pytest.mark.parametrize('stage', ['loaded', 'evaluated'])
@pytest.mark.parametrize('replacement', ['missing', 'malformed', 'foreign', 'partial', 'representation'])
def test_retained_diff_rejects_every_observed_bundle_replacement(tmp_path, stage, replacement):
    root = tmp_path / 'source'; project(root)
    filename = tmp_path / 'input.zip'; bundle, _ = captured(root, filename)
    if replacement == 'foreign':
        config = json.loads((root / 'specroad.json').read_bytes()); config['project_id'] = 'foreign'
        saved = (root / 'specroad.json').read_bytes()
        put(root, 'specroad.json', canonical_json_bytes(config))
        other = prepare_project_bundle(root).source_bytes
        put(root, 'specroad.json', saved)
    elif replacement == 'partial':
        other_root = tmp_path / 'partial'; partial_project(other_root)
        other = prepare_partial_bundle(other_root, scope()).source_bytes
    elif replacement == 'representation':
        files = bundle.files
        path = next(p for p in files if p.startswith('spec/requirements/'))
        files[path] += b'\n'
        other = rebind(bundle, files)
        assert verify_bundle(other)['manifest']['bundle_model_root_sha256'] == bundle.manifest['bundle_model_root_sha256']
    else:
        other = b'no valid bundle'
    work = _diff_steps(root, str(filename), against_kind='bundle')
    assert next(work) == 'loaded'
    if stage == 'evaluated':
        assert next(work) == 'evaluated'
    if replacement == 'missing':
        filename.unlink()
    else:
        filename.write_bytes(other)
    original = inventory(tmp_path)
    with no_write_attempts():
        if stage == 'loaded':
            assert next(work) == 'evaluated'
        with pytest.raises(StopIteration) as completed:
            next(work)
    result = completed.value.value
    assert result.exit_code == 6 and result.as_dict()['result'] is None
    assert any(d['rationale'] == 'comparison_source_changed' for d in result.as_dict()['diagnostics'])
    assert inventory(tmp_path) == original


def test_replaced_parent_is_not_reopened_as_a_new_source_even_with_identical_bytes(tmp_path):
    root = tmp_path / 'source'; project(root)
    parent = tmp_path / 'inputs'; parent.mkdir()
    filename = parent / 'input.zip'; bundle, _ = captured(root, filename)
    work = _diff_steps(root, str(filename), against_kind='bundle')
    assert next(work) == 'loaded' and next(work) == 'evaluated'
    parent.rename(tmp_path / 'original-inputs')
    parent.mkdir(); filename.write_bytes(bundle.source_bytes)
    original = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(StopIteration) as completed:
        next(work)
    assert completed.value.value.exit_code == 7
    assert completed.value.value.as_dict()['result'] is None
    assert inventory(tmp_path) == original


def test_bundle_is_rechecked_after_final_local_target_reads(tmp_path, monkeypatch):
    root = tmp_path / 'source'; project(root)
    filename = tmp_path / 'input.zip'; captured(root, filename)
    work = _diff_steps(root, str(filename), against_kind='bundle')
    assert next(work) == 'loaded' and next(work) == 'evaluated'
    read = ProjectBoundary.read_bytes

    def change_after_target_read(boundary, name):
        raw = read(boundary, name)
        if boundary.root == root and filename.exists():
            filename.unlink()
        return raw

    monkeypatch.setattr(ProjectBoundary, 'read_bytes', change_after_target_read)
    with pytest.raises(StopIteration) as completed:
        next(work)
    assert completed.value.value.exit_code == 6
    assert completed.value.value.as_dict()['result'] is None
    assert not filename.exists()
