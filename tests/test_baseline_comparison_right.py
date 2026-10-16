"""Historical reader boundaries, late changes and exact shared-source behavior."""
import json
import os
import subprocess

import pytest

from specroad.archive import build_baseline_manifest, compare_baselines
from specroad.archive import materialization, verification
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.model.model_manifest import ProjectReadBinding
from specroad.model.paths import artifact_path
from specroad.query import ComparisonSourceSnapshot, compare_sources
from specroad.query import comparison_sources
from specroad.security import SafetyViolation
from support.domain import domain_value
from support.git_objects import GitFixture
from support.model import configuration_value, put
from support.read_only import inventory, no_write_attempts
from support.records import record_value, ref
from support.relations import aid
from support.scopes import descriptor
from test_baseline_comparison import stored_comparison, capture
from test_baseline_manifest import baseline_inputs
from test_baseline_verification import row_for, replace_object


def test_missing_selected_baseline_record_has_a_bound_diagnostic(tmp_path):
    root = tmp_path / 'archive'; record, _, _ = stored_comparison(root)
    path = artifact_path('baseline', record['id'], 'SR'); (root / path).unlink()
    before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        capture(root, record, form='id')
    assert error.value.reason == 'comparison_baseline_record_missing'
    assert error.value.path == path and inventory(root) == before


@pytest.mark.parametrize('moment', ['inputs', 'final_verification'])
@pytest.mark.parametrize('change', ['removed', 'changed'])
def test_native_record_is_rechecked_before_publishing_owned_inputs(tmp_path, monkeypatch, moment, change):
    root = tmp_path / 'archive'; record, _, _ = stored_comparison(root)
    path = artifact_path('baseline', record['id'], 'SR'); changed = False
    replacement = canonical_json_bytes({**record, 'title': 'Concurrent record'})
    def mutate():
        nonlocal changed
        changed = True
        if change == 'removed': (root / path).unlink()
        else: (root / path).write_bytes(replacement)
    if moment == 'inputs':
        original = comparison_sources.ComparisonInputs
        def inputs(*args, **kwargs):
            result = original(*args, **kwargs); mutate(); return result
        monkeypatch.setattr(comparison_sources, 'ComparisonInputs', inputs)
    else:
        original = verification.verify_baseline_snapshot; calls = 0
        def verify(*args, **kwargs):
            nonlocal calls
            result = original(*args, **kwargs); calls += 1
            if calls == 2: mutate()
            return result
        monkeypatch.setattr(verification, 'verify_baseline_snapshot', verify)
    with pytest.raises(ModelError) as error: capture(root, record, form='id')
    assert changed
    assert error.value.reason == ('comparison_baseline_record_missing' if change == 'removed'
                                  else 'comparison_source_changed')
    assert error.value.path == path
    assert not (root / path).exists() if change == 'removed' else (root / path).read_bytes() == replacement


@pytest.mark.parametrize('role', ['artifact', 'profile', 'rule', 'mapping', 'attachment',
                                  'semantic_configuration', 'effective_profile', 'model_manifest'])
def test_late_missing_objects_cannot_complete_an_already_parsed_comparison(tmp_path, monkeypatch, role):
    root = tmp_path / 'archive'; record, _, _ = stored_comparison(root)
    row = row_for(record, role); path = root / row['object_path']
    if 'source_path' in row: put(root, row['source_path'], path.read_bytes())
    original = comparison_sources.ComparisonInputs
    def inputs(*args, **kwargs):
        result = original(*args, **kwargs); path.unlink(); return result
    monkeypatch.setattr(comparison_sources, 'ComparisonInputs', inputs)
    with pytest.raises(ModelError) as error: capture(root, record)
    assert error.value.reason == 'snapshot_referenced_object_missing'
    assert error.value.path == row['object_path'] and not path.exists()


@pytest.mark.parametrize('moment,role', [('semantic_read', 'semantic_configuration'),
                                       ('owned_snapshot', 'artifact')])
def test_missing_bytes_between_verification_and_capture_keep_the_object_diagnostic(tmp_path, monkeypatch, moment, role):
    root = tmp_path / 'archive'; record, _, _ = stored_comparison(root)
    row = row_for(record, role); path = root / row['object_path']; removed = False
    module = verification if moment == 'semantic_read' else materialization
    original = module.verify_baseline_snapshot
    def verify(*args, **kwargs):
        nonlocal removed
        result = original(*args, **kwargs)
        if not removed: path.unlink(); removed = True
        return result
    monkeypatch.setattr(module, 'verify_baseline_snapshot', verify)
    with pytest.raises(ModelError) as error: capture(root, record)
    assert removed and error.value.reason == 'snapshot_referenced_object_missing'
    assert error.value.path == row['object_path']


@pytest.mark.parametrize('version', ['0.1.0', '99.0.0'])
@pytest.mark.parametrize('role', ['record', 'semantic_configuration', 'artifact', 'profile'])
def test_unsupported_historical_schemas_are_not_reinterpreted_as_current_data(tmp_path, role, version):
    root = tmp_path / 'archive'; record, _, _ = stored_comparison(root)
    if role == 'record': record['schema_version'] = version
    else:
        row = row_for(record, role); value = json.loads((root / row['object_path']).read_bytes())
        value['schema_version'] = version; replace_object(root, row, canonical_json_bytes(value))
        if role == 'semantic_configuration': record['configuration_hash'] = row['sha256']
    before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as error: capture(root, record)
    expected = 'profile_unsupported_schema' if role == 'profile' else 'unsupported_schema_version'
    assert error.value.reason == expected and inventory(root) == before


@pytest.mark.parametrize('entrypoint', ['pair', 'snapshots'])
def test_distinct_archived_project_ids_cannot_be_compared(tmp_path, entrypoint):
    left = tmp_path / 'left'; first, _, _ = stored_comparison(left)
    right = tmp_path / 'right'; right.mkdir()
    args = baseline_inputs(configuration=configuration_value(project_id='foreign'),
        values=[domain_value('requirement', id=aid())], scope=descriptor('project'))
    args['binding'] = ProjectReadBinding('foreign', '/test/foreign-baseline', (1, 2))
    snapshot = build_baseline_manifest(**args, baseline_id=ref('BASE', '1'))
    second = record_value('baseline', id=ref('BASE', '1'), **{k: snapshot.data[k] for k in (
        'scope_descriptor', 'manifest', 'model_root_sha256', 'configuration_hash', 'profiles', 'tool_version')})
    for item in snapshot.objects: put(right, item.reference.path, item.content)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        if entrypoint == 'pair':
            compare_baselines(left, canonical_json_bytes(first), right, canonical_json_bytes(second))
        else: compare_sources(capture(left, first), capture(right, second))
    assert error.value.reason == ('project_identity_mismatch' if entrypoint == 'pair' else 'comparison_project_mismatch')
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('target,kind', [('record', 'symlink'), ('object', 'symlink'), ('object', 'hardlink')])
def test_unsafe_historical_paths_do_not_become_comparison_sources(tmp_path, target, kind):
    root = tmp_path / 'archive'; record, _, _ = stored_comparison(root)
    name = artifact_path('baseline', record['id'], 'SR') if target == 'record' else row_for(record, 'attachment')['object_path']
    path = root / name; outside = tmp_path / 'outside'; outside.write_bytes(path.read_bytes()); path.unlink()
    if kind == 'symlink': path.symlink_to(outside)
    else: os.link(outside, path)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(SafetyViolation): capture(root, record, form='id')
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('target', ['record', 'object'])
def test_host_access_denial_is_not_converted_into_missing_or_success(tmp_path, monkeypatch, target):
    root = tmp_path / 'archive'; record, _, _ = stored_comparison(root)
    leaf = record['id'] + '.json' if target == 'record' else row_for(record, 'attachment')['sha256']
    original = os.open
    def opened(path, flags, *args, **kwargs):
        if path == leaf: raise PermissionError('archive access denied')
        return original(path, flags, *args, **kwargs)
    monkeypatch.setattr(os, 'open', opened)
    with no_write_attempts(), pytest.raises(PermissionError): capture(root, record, form='id')


def test_baseline_and_git_sources_compare_owned_history_without_working_tree_or_checkout(tmp_path, monkeypatch):
    root = tmp_path / 'archive'; record, _, _ = stored_comparison(root, attachment=None)
    baseline = capture(root, record)
    git_root = tmp_path / 'git'; fixture = GitFixture(git_root)
    commit = fixture.commit(dict(baseline.resources))
    put(git_root, 'specroad.json', b'uncommitted invalid configuration')
    put(git_root, artifact_path('requirement', aid(), 'SR'), b'uncommitted invalid artifact')
    before = inventory(tmp_path)
    original = subprocess.run; commands = []
    def read_only_git(argv, **kwargs):
        arguments = iter(argv[1:])
        for argument in arguments:
            if argument == '-c': next(arguments)
            elif not argument.startswith('-'):
                commands.append(argument); break
        assert commands[-1] in ('rev-parse', 'cat-file', 'ls-tree')
        assert kwargs['shell'] is False and 'protocol.allow=never' in argv
        return original(argv, **kwargs)
    monkeypatch.setattr(subprocess, 'run', read_only_git)
    committed = ComparisonSourceSnapshot(git_root, kind='git', reference=commit)
    assert commands
    with no_write_attempts():
        assert not compare_sources(baseline, committed).data['changed']
        assert not compare_sources(committed, baseline).data['changed']
    assert inventory(tmp_path) == before
