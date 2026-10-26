"""15.h.W: native verified bundles use the shared, read-only field comparison."""
from dataclasses import FrozenInstanceError
import json
import shutil
from unittest.mock import patch

import pytest

from specroad.bundles import BundleContainer, BundleError, prepare_project_bundle, prepare_partial_bundle
from specroad.cli.application import dispatch_result, execute_request
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.query import ComparisonSourceSnapshot, ReadCommandWork, compare_sources, diff_project
from specroad.query.project_diff import _diff_steps
from specroad.security import ProjectBoundary, SafetyViolation
from support.git_objects import GitFixture
from support.model import put
from support.read_only import inventory, no_write_attempts
from test_bundle_receipts import completed
from test_bundle_verification import rebind
from test_partial_bundle import scope, project as partial_project
from test_project_bundle import project, baseline_project


def captured(root, filename):
    bundle = prepare_project_bundle(root)
    filename.write_bytes(bundle.source_bytes)
    return bundle, ComparisonSourceSnapshot(filename, kind='bundle')


@pytest.mark.parametrize('fixture', ['project', 'baseline', 'initialized', 'receipts'])
def test_bundle_and_identical_local_project_have_the_same_field_comparison(tmp_path, fixture):
    root = tmp_path / 'source'
    if fixture == 'initialized':
        assert dispatch_result(['init', str(root)]).exit_code == 0
    else:
        {'project': project, 'baseline': baseline_project, 'receipts': completed}[fixture](root)
    bundle, snapshot = captured(root, tmp_path / 'source.zip')
    before = inventory(tmp_path)
    with no_write_attempts():
        local = ComparisonSourceSnapshot(root)
        actual = compare_sources(snapshot, local)
        expected = compare_sources(local, local)
    assert actual.data == expected.data and actual.sha256 == expected.sha256
    assert not actual.data['changed'] and snapshot.resources == local.resources
    binding = snapshot.binding
    assert binding['comparison_scope'] == 'project_configuration_and_artifacts'
    assert 'baseline' not in binding and binding['bundle']['manifest'] == bundle.manifest
    evidence = binding['bundle']
    assert evidence['file'] == {'sha256': bundle.sha256, 'size': len(bundle.source_bytes)}
    assert all(evidence[k] for k in ('container_verified', 'closure_verified', 'model_root_verified',
                                    'source_bytes_rechecked'))
    assert not any(evidence[k] for k in ('full_semantic_validation', 'creator_authenticated',
                                        'approval_granted', 'write_authorized', 'external_hash_verified'))
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('right_kind', ['local', 'git', 'bundle'])
def test_changed_bundle_pairs_equal_the_existing_local_comparison(tmp_path, right_kind):
    root = tmp_path / 'source'; project(root)
    _, before = captured(root, tmp_path / 'before.zip')
    local_before = ComparisonSourceSnapshot(root)
    path = next(p for p, _ in before.resources if p.startswith('spec/requirements/'))
    value = json.loads((root / path).read_bytes()); value['statement'] = 'Changed requirement'
    put(root, path, canonical_json_bytes(value))
    config = json.loads((root / 'specroad.json').read_bytes())
    config['validation_policy']['fail_on'] = 'warning'
    put(root, 'specroad.json', canonical_json_bytes(config))
    local_after = ComparisonSourceSnapshot(root)
    if right_kind == 'bundle':
        _, after = captured(root, tmp_path / 'after.zip')
    elif right_kind == 'git':
        fixture = GitFixture(tmp_path / 'git')
        commit = fixture.commit(dict(local_after.resources))
        after = ComparisonSourceSnapshot(fixture.root, kind='git', reference=commit)
    else:
        after = local_after
    original = inventory(tmp_path)
    with no_write_attempts():
        actual = compare_sources(before, after)
        expected = compare_sources(local_before, local_after)
    assert actual.data == expected.data and actual.sha256 == expected.sha256
    assert {'text_changed', 'configuration_changed'} <= set(actual.data['categories'])
    assert inventory(tmp_path) == original


@pytest.mark.parametrize('mode', ['direct', 'cli_absolute', 'cli_relative', 'structured'])
def test_public_diff_accepts_explicit_bundle_files_and_keeps_the_existing_result(tmp_path, mode):
    root = tmp_path / 'source'; project(root)
    filename = tmp_path / 'input.zip'
    bundle, _ = captured(root, filename)
    before = tmp_path / 'before'; before.mkdir()
    for path, raw in bundle.files.items():
        put(before, path, raw)
    target = next(p for p in bundle.files if p.startswith('spec/requirements/'))
    value = json.loads(bundle.files[target]); value['statement'] = 'New statement'
    put(root, target, canonical_json_bytes(value))
    original = inventory(tmp_path)
    with no_write_attempts():
        expected = diff_project(root, str(before), against_kind='local')
        if mode == 'direct':
            actual = diff_project(root, str(filename), against_kind='bundle')
        elif mode == 'structured':
            actual = execute_request({'command_id': 'diff', 'options': {'--project': str(root),
                '--against': filename.name, '--against-kind': 'bundle'}}, cwd=tmp_path).result
        else:
            actual = dispatch_result(['diff', '--project', str(root), '--against-kind', 'bundle',
                '--against', filename.name if mode == 'cli_relative' else str(filename)], cwd=tmp_path)
    assert expected.exit_code == actual.exit_code == 0, actual.as_dict()
    assert actual.as_dict()['result'] == expected.as_dict()['result']
    assert actual.details['before_source']['kind'] == 'bundle'
    assert actual.details['before_source']['bundle']['file']['sha256'] == bundle.sha256
    assert inventory(tmp_path) == original


def test_bundle_capture_reads_only_the_explicit_file_and_owns_its_evidence(tmp_path):
    root = tmp_path / 'source'; project(root)
    bundle = prepare_project_bundle(root)
    filename = tmp_path / 'input.zip'; filename.write_bytes(bundle.source_bytes)
    shutil.rmtree(root)
    put(tmp_path, 'specroad.json', b'not a project')
    read = ProjectBoundary.read_bytes

    def explicit(boundary, name, **kwargs):
        assert boundary.root == tmp_path and name == filename.name
        return read(boundary, name, **kwargs)

    with no_write_attempts(), patch.object(ProjectBoundary, 'read_bytes', explicit):
        snapshot = ComparisonSourceSnapshot(filename, kind='bundle')
    binding = snapshot.binding; digest = snapshot.sha256
    filename.unlink()
    binding['bundle']['manifest']['project_id'] = 'foreign'
    binding['resources'].clear()
    with pytest.raises(FrozenInstanceError):
        snapshot.kind = 'local'
    with no_write_attempts():
        assert snapshot.sha256 == digest
        assert not compare_sources(snapshot, snapshot).data['changed']


def test_retained_diff_binds_the_bundle_path_before_the_first_work_unit(tmp_path, monkeypatch):
    root = tmp_path / 'source'; project(root)
    filename = tmp_path / 'input.zip'; bundle, _ = captured(root, filename)
    other = tmp_path / 'other'; other.mkdir()
    put(other, filename.name, b'not the selected source')
    monkeypatch.chdir(tmp_path)
    with ReadCommandWork('diff', root, against=filename.name, against_kind='bundle') as work:
        monkeypatch.chdir(other)
        original = inventory(tmp_path)
        with no_write_attempts():
            assert work.advance(3)
        assert work.result.exit_code == 0 and not work.result.result['changed']
        evidence = work.result.details['before_source']['bundle']
        assert evidence['file']['sha256'] == bundle.sha256
        assert inventory(tmp_path) == original


@pytest.mark.parametrize('fault', ['container', 'model', 'attachment'])
def test_invalid_transport_or_model_cannot_become_a_comparison_source(tmp_path, fault):
    root = tmp_path / 'source'; project(root)
    bundle = prepare_project_bundle(root)
    if fault == 'container':
        raw = bundle.source_bytes[:-1]
    elif fault == 'model':
        raw = rebind(bundle, bundle_model_root_sha256='a' * 64, origin_model_root_sha256='a' * 64)
    else:
        files = bundle.files; files['attachments/owned.bin'] = b'wrong bytes'
        raw = rebind(bundle, files)
    if fault != 'container':
        assert BundleContainer(raw).manifest  # Transport integrity alone is insufficient.
    filename = tmp_path / 'input.zip'; filename.write_bytes(raw)
    original = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(BundleError):
        ComparisonSourceSnapshot(filename, kind='bundle')
    assert inventory(tmp_path) == original


@pytest.mark.parametrize('kind', ['document', 'release'])
def test_partial_bundle_is_not_promoted_to_full_comparison_input(tmp_path, kind):
    root = tmp_path / 'source'; partial_project(root, kind)
    bundle = prepare_partial_bundle(root, scope(kind))
    filename = tmp_path / 'partial.zip'; filename.write_bytes(bundle.source_bytes)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        ComparisonSourceSnapshot(filename, kind='bundle', allow_partial=True)
    assert error.value.reason == 'comparison_full_project_required'


def test_expected_project_identity_still_rejects_a_verified_foreign_bundle(tmp_path):
    root = tmp_path / 'source'; project(root)
    filename = tmp_path / 'input.zip'; captured(root, filename)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        ComparisonSourceSnapshot(filename, kind='bundle', expected_project_id='foreign')
    assert error.value.reason == 'project_identity_mismatch'


def test_explicit_bundle_symlink_is_not_followed(tmp_path):
    root = tmp_path / 'source'; project(root)
    filename = tmp_path / 'input.zip'; captured(root, filename)
    link = tmp_path / 'link.zip'; link.symlink_to(filename)
    with no_write_attempts(), pytest.raises(SafetyViolation):
        ComparisonSourceSnapshot(link, kind='bundle')


def test_changed_file_during_capture_cannot_return_a_mixed_source(tmp_path):
    root = tmp_path / 'source'; project(root)
    filename = tmp_path / 'input.zip'; captured(root, filename)
    read = ProjectBoundary.read_bytes
    changed = False

    def change(boundary, name, **kwargs):
        nonlocal changed
        raw = read(boundary, name, **kwargs)
        if boundary.root == tmp_path and name == filename.name and not changed:
            changed = True
            filename.write_bytes(b'replaced')
        return raw

    with patch.object(ProjectBoundary, 'read_bytes', change), pytest.raises(ModelError) as error:
        ComparisonSourceSnapshot(filename, kind='bundle')
    assert error.value.reason == 'comparison_source_changed'


@pytest.mark.parametrize('stage', ['loaded', 'evaluated'])
def test_diff_rechecks_the_actual_bundle_before_returning_success(tmp_path, stage):
    root = tmp_path / 'source'; project(root)
    filename = tmp_path / 'input.zip'; captured(root, filename)
    work = _diff_steps(root, str(filename), against_kind='bundle')
    assert next(work) == 'loaded'
    if stage == 'evaluated':
        assert next(work) == 'evaluated'
    target = next(root.glob('spec/requirements/*.json'))
    value = json.loads(target.read_bytes()); value['statement'] = 'Changed source'
    target.write_bytes(canonical_json_bytes(value))
    filename.write_bytes(prepare_project_bundle(root).source_bytes)
    if stage == 'loaded':
        assert next(work) == 'evaluated'
    with pytest.raises(StopIteration) as end:
        next(work)
    assert end.value.value.exit_code == 6
    assert end.value.value.as_dict()['result'] is None


def test_changed_opaque_resources_still_require_their_own_comparison_semantics(tmp_path):
    root = tmp_path / 'source'; project(root)
    _, before = captured(root, tmp_path / 'input.zip')
    path = 'mappings/export.json'
    put(root, path, (root / path).read_bytes() + b'\n')
    after = ComparisonSourceSnapshot(root)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        compare_sources(before, after)
    assert error.value.reason == 'comparison_resource_semantics_unavailable'
