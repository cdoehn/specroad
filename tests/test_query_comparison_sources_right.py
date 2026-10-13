"""Adversarial source identity, completeness and final operational observations."""
from hashlib import sha1
import importlib
import json

import pytest

from specroad.cli.results import OperationFailure
from specroad.model.errors import ModelError
from specroad.query import ComparisonSourceSnapshot, compare_sources
from specroad.security import SafetyViolation
from specroad.storage.project import ProjectSource
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.model import configuration_value, put
from support.read_only import inventory
from support.records import record_value
from support.relations import aid
from test_query_comparison_sources import capture, source, source_files

module = importlib.import_module('specroad.query.comparison_sources')
ARTIFACT = 'spec/requirements/' + aid() + '.json'


@pytest.mark.parametrize('identity', ['', ' ', True, 5, b'sample', [], {}, 'bad\0id', '\ud800'])
def test_invalid_expected_identity_fails_before_any_source_discovery(tmp_path, monkeypatch, identity):
    def forbidden(*args, **kwargs):
        pytest.fail('Invalid selection must not open a project or discover Git')
    monkeypatch.setattr(module, 'ProjectSource', forbidden)
    monkeypatch.setattr(module, 'GitObjectSource', forbidden)
    for kind in ('local', 'git'):
        with pytest.raises(ModelError):
            ComparisonSourceSnapshot(tmp_path / 'absent', kind=kind, reference=None,
                                     expected_project_id=identity)


@pytest.mark.parametrize('kind', [None, True, b'local', [], 'unknown'])
def test_invalid_kind_has_no_implicit_local_source(tmp_path, monkeypatch, kind):
    monkeypatch.setattr(module, 'ProjectSource', lambda *a, **k: pytest.fail('Implicit fallback'))
    with pytest.raises(ModelError) as caught:
        ComparisonSourceSnapshot(tmp_path / 'absent', kind=kind)
    assert caught.value.reason == 'comparison_source_kind_invalid'


@pytest.mark.parametrize('opaque_delta', [False, True])
def test_prefix_identity_mismatch_precedes_unavailable_resource_semantics(tmp_path, opaque_delta):
    before = capture(source(tmp_path / 'a', 'local', source_files(
        extra={'rules/r.json': b'old'})))
    after = capture(source(tmp_path / 'b', 'git', source_files(
        configuration=configuration_value(id_prefix='OTHER'),
        extra={'rules/r.json': b'new' if opaque_delta else b'old'})))
    with pytest.raises(ModelError) as caught:
        compare_sources(before, after)
    assert caught.value.reason == 'comparison_project_mismatch'


def test_recovery_appearing_during_final_byte_recheck_blocks_publication(tmp_path, monkeypatch):
    location = source(tmp_path / 'project', 'local', source_files(domain_value('requirement', id=aid())))
    original = ProjectSource.read_normative
    calls = 0

    def read(reader, path, **options):
        nonlocal calls
        raw = original(reader, path, **options)
        if path == ARTIFACT:
            calls += 1
            if calls == 2:
                put(location[0], '.specroad/transactions/pending/journal.json', b'owned pending transaction')
        return raw

    monkeypatch.setattr(ProjectSource, 'read_normative', read)
    with pytest.raises(OperationFailure) as caught:
        capture(location)
    assert calls == 2
    assert caught.value.details['preflight']['reason'] == 'recovery_required'
    assert (location[0] / '.specroad/transactions/pending/journal.json').read_bytes() == b'owned pending transaction'


@pytest.mark.parametrize('change', ['add', 'remove'])
def test_local_inventory_changes_are_rejected_without_repair(tmp_path, monkeypatch, change):
    location = source(tmp_path / 'project', 'local', source_files(domain_value('requirement', id=aid())))
    original = ProjectSource.read_normative
    changed = False
    added = 'spec/requirements/' + aid(number=2) + '.json'

    def read(reader, path, **options):
        nonlocal changed
        raw = original(reader, path, **options)
        if path == ARTIFACT and not changed:
            changed = True
            if change == 'add':
                put(location[0], added, artifact_bytes(domain_value('requirement', id=aid(number=2))))
            else:
                (location[0] / ARTIFACT).unlink()
        return raw

    monkeypatch.setattr(ProjectSource, 'read_normative', read)
    with pytest.raises(ModelError) as caught:
        capture(location)
    assert caught.value.reason == 'comparison_source_membership_changed'
    assert (location[0] / added).exists() == (change == 'add')
    assert (location[0] / ARTIFACT).exists() == (change == 'add')


def test_changed_local_configuration_cannot_complete_an_earlier_capture(tmp_path, monkeypatch):
    location = source(tmp_path / 'project', 'local', source_files(domain_value('requirement', id=aid())))
    original = ProjectSource.read_normative
    changed = False
    replacement = json.dumps(configuration_value(project_id='foreign')).encode()

    def read(reader, path, **options):
        nonlocal changed
        raw = original(reader, path, **options)
        if path == ARTIFACT and not changed:
            changed = True
            put(location[0], 'specroad.json', replacement)
        return raw

    monkeypatch.setattr(ProjectSource, 'read_normative', read)
    with pytest.raises(ModelError) as caught:
        capture(location)
    assert caught.value.reason == 'configuration_changed'
    assert (location[0] / 'specroad.json').read_bytes() == replacement


@pytest.mark.parametrize('case,reason', [('missing', 'git_path_missing'),
    ('schema', 'unsupported_schema_version'), ('foreign', 'project_identity_mismatch')])
def test_invalid_committed_configuration_is_never_replaced_by_current_valid_data(tmp_path, case, reason):
    files = source_files(domain_value('requirement', id=aid()))
    if case == 'missing':
        del files['specroad.json']
    elif case == 'schema':
        files['specroad.json'] = json.dumps(configuration_value(schema_version='99.0.0')).encode()
    else:
        files['specroad.json'] = json.dumps(configuration_value(project_id='foreign')).encode()
    root, options = source(tmp_path / 'project', 'git', files)
    put(root, 'specroad.json', json.dumps(configuration_value()).encode())
    original = inventory(tmp_path)
    with pytest.raises(ModelError) as caught:
        ComparisonSourceSnapshot(root, **options, expected_project_id='sample')
    assert caught.value.reason == reason
    assert inventory(tmp_path) == original


def test_missing_committed_blob_is_not_replaced_by_current_artifact(tmp_path):
    files = source_files(domain_value('requirement', id=aid()))
    location = source(tmp_path / 'project', 'git', files)
    raw = files[ARTIFACT]
    oid = sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw, usedforsecurity=False).hexdigest()
    (location[0] / '.git/objects' / oid[:2] / oid[2:]).unlink()
    put(location[0], ARTIFACT, raw)
    original = inventory(tmp_path)
    with pytest.raises(ModelError) as caught:
        capture(location)
    assert caught.value.reason == 'git_object_read_failed'
    assert inventory(tmp_path) == original


def test_uncommitted_artifact_never_expands_the_selected_commit_inventory(tmp_path):
    location = source(tmp_path / 'project', 'git', source_files())
    put(location[0], ARTIFACT, artifact_bytes(domain_value('requirement', id=aid())))
    original = inventory(tmp_path)
    snapshot = capture(location)
    assert snapshot.inputs.records == ()
    assert [path for path, _ in snapshot.resources] == ['specroad.json']
    assert inventory(tmp_path) == original


@pytest.mark.parametrize('kind', ['local', 'git'])
def test_incompatible_artifact_schema_is_rejected_even_with_valid_configuration(tmp_path, kind):
    value = domain_value('requirement', id=aid(), schema_version='99.0.0')
    location = source(tmp_path / 'project', kind, source_files(value))
    with pytest.raises(ModelError) as caught:
        capture(location)
    assert caught.value.reason == 'unsupported_schema_version'


@pytest.mark.parametrize('kind', ['local', 'git'])
def test_artifact_content_identity_must_match_its_path(tmp_path, kind):
    files = source_files(domain_value('requirement', id=aid()))
    files[ARTIFACT] = artifact_bytes(domain_value('requirement', id=aid(number=2)))
    location = source(tmp_path / 'project', kind, files)
    with pytest.raises(ModelError) as caught:
        capture(location)
    assert caught.value.reason == 'artifact_path_identity_mismatch'
    assert caught.value.path == ARTIFACT


@pytest.mark.parametrize('kind', ['local', 'git'])
def test_nested_project_inside_managed_inventory_is_not_combined(tmp_path, kind):
    files = source_files(extra={'spec/requirements/specroad.json': json.dumps(configuration_value()).encode()})
    location = source(tmp_path / 'project', kind, files)
    with pytest.raises(SafetyViolation):
        capture(location)


@pytest.mark.parametrize('kind', ['local', 'git'])
def test_case_colliding_non_json_children_in_managed_trees_are_not_ignored(tmp_path, kind):
    files = source_files(extra={'spec/notes.txt': b'a', 'spec/NOTES.txt': b'b'})
    location = source(tmp_path / 'project', kind, files)
    with pytest.raises(SafetyViolation):
        capture(location)


@pytest.mark.parametrize('kind', ['local', 'git'])
def test_non_json_symlink_in_managed_inventory_is_never_followed(tmp_path, kind):
    foreign = tmp_path / 'foreign';foreign.write_bytes(b'foreign bytes')
    files = source_files()
    if kind == 'git':
        files['spec/notes.txt'] = ('120000', str(foreign).encode())
    location = source(tmp_path / 'project', kind, files)
    if kind == 'local':
        (location[0] / 'spec').mkdir()
        (location[0] / 'spec/notes.txt').symlink_to(foreign)
    original = inventory(tmp_path)
    with pytest.raises(SafetyViolation):
        capture(location)
    assert inventory(tmp_path) == original and foreign.read_bytes() == b'foreign bytes'


@pytest.mark.parametrize('kind', ['local', 'git'])
def test_ancestor_file_cannot_hide_a_configured_subtree(tmp_path, kind):
    files = source_files(configuration=configuration_value(managed_paths=['spec/requirements']),
                         extra={'spec': b'not a directory'})
    location = source(tmp_path / 'project', kind, files)
    with pytest.raises(SafetyViolation):
        capture(location)


@pytest.mark.parametrize('kind', ['local', 'git'])
def test_typed_record_artifacts_share_the_snapshot_without_authenticating_their_status(tmp_path, kind):
    values = [record_value(name) for name in ('configuration', 'document', 'evidence', 'baseline', 'relation_review')]
    location = source(tmp_path / 'project', kind, source_files(*values))
    snapshot = capture(location)
    assert {record.identity.id for record in snapshot.inputs.records} == {v['id'] for v in values}
    assert {record.identity.id: record.data for record in snapshot.inputs.records} == {v['id']: v for v in values}
    result = compare_sources(snapshot, snapshot).data
    assert not result['changed'] and not result['approval_granted']
    assert snapshot.binding['full_semantic_validation'] is False


def test_source_snapshot_contract_is_required_instead_of_implicit_live_inputs(tmp_path):
    snapshot = capture(source(tmp_path / 'project', 'local', source_files()))
    for foreign in (None, {}, snapshot.inputs, snapshot.configuration, tmp_path):
        with pytest.raises(ModelError) as caught:
            compare_sources(foreign, snapshot)
        assert caught.value.reason == 'comparison_source_snapshot_required'
