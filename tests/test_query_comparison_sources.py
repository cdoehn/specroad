"""Same-project source comparisons and owned observations, without writes."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
from unittest.mock import patch
import json

import pytest

from specroad.cli.results import OperationFailure
from specroad.graph.comparison import ComparisonInputs
from specroad.graph.relations import SourceRelations
from specroad.model.configuration import ProjectConfiguration
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.query import ComparisonSourceSnapshot, compare_semantic, compare_sources
from specroad.security import SafetyViolation
from specroad.storage.project import ProjectSource
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.git_objects import GitFixture
from support.model import configuration_value, put
from support.read_only import inventory, no_write_attempts
from support.relations import aid


def source_files(*values, configuration=None, extra=None):
    config = configuration_value() if configuration is None else configuration
    result = {'specroad.json': json.dumps(config, ensure_ascii=False).encode()}
    result.update({artifact_path(v['artifact_type'], v['id'], config['id_prefix']): artifact_bytes(v)
                   for v in values})
    result.update(extra or {})
    return result


def source(root, kind, files):
    if kind == 'git':
        fixture = GitFixture(root)
        reference = fixture.commit(files)
    else:
        root.mkdir()
        for path, raw in files.items():
            put(root, path, raw)
        reference = None
    return root, dict(kind=kind, reference=reference)


def capture(location):
    root, options = location
    return ComparisonSourceSnapshot(root, **options)


def direct(values, configuration):
    return ComparisonInputs(configuration['project_id'], [SourceRelations(artifact_bytes(v)) for v in values])


@pytest.mark.parametrize('left_kind,right_kind', [('local', 'local'), ('local', 'git'), ('git', 'local'), ('git', 'git')])
def test_two_sources_equal_the_direct_data_comparison(tmp_path, left_kind, right_kind):
    before = [domain_value('requirement', id=aid(), statement='Old', timing='PT2S')]
    after = [domain_value('requirement', id=aid(), statement='New', timing='PT1S'),
             domain_value('goal', id=aid('goal'))]
    left_config = configuration_value(validation_policy={'fail_on': 'error'})
    right_config = configuration_value(validation_policy={'fail_on': 'warning'})
    left = source(tmp_path / 'before', left_kind, source_files(*before, configuration=left_config))
    right = source(tmp_path / 'after', right_kind, source_files(*after, configuration=right_config))
    original = inventory(tmp_path)
    a, b = capture(left), capture(right)
    result = compare_sources(a, b, timing_bounds={aid(): 'maximum'})
    expected = compare_semantic(direct(before, left_config), direct(after, right_config),
        before_configuration=ProjectConfiguration(left_config), after_configuration=ProjectConfiguration(right_config),
        timing_bounds={aid(): 'maximum'})
    assert result.data == expected.data and result.sha256 == expected.sha256
    assert result.data['inventory_delta']['added_ids'] == [aid('goal')]
    assert {'text_changed', 'timing_tightened', 'configuration_changed'} <= set(result.data['categories'])
    assert inventory(tmp_path) == original
    assert a.kind == left_kind and b.kind == right_kind
    assert (a.commit_id is not None) == (left_kind == 'git')


@pytest.mark.parametrize('kind', ['local', 'git'])
def test_identical_values_at_different_roots_keep_distinct_raw_bindings(tmp_path, kind):
    files = source_files(domain_value('requirement', id=aid()))
    differently_formatted = {path: json.dumps(json.loads(raw), indent=3).encode() + b'\r\n'
                            for path, raw in files.items()}
    before = capture(source(tmp_path / 'a', kind, files))
    after = capture(source(tmp_path / 'b', kind, differently_formatted))
    assert not compare_sources(before, after).data['changed']
    assert before.inputs.fingerprint == after.inputs.fingerprint
    assert before.sha256 != after.sha256
    assert before.resources == tuple(sorted(files.items()))
    assert before.binding['resources'] == [{'path': path, 'sha256': sha256(raw).hexdigest()}
                                           for path, raw in sorted(files.items())]


def test_empty_projects_still_compare_their_configuration(tmp_path):
    before = capture(source(tmp_path / 'a', 'local', source_files()))
    after = capture(source(tmp_path / 'b', 'git', source_files(
        configuration=configuration_value(validation_policy={'fail_on': 'warning'}))))
    result = compare_sources(before, after).data
    assert result['changed'] and result['changes'] == []
    assert result['categories'] == ['configuration_changed']


def test_captured_local_values_remain_owned_after_the_source_disappears(tmp_path):
    location = source(tmp_path / 'project', 'local', source_files(domain_value('requirement', id=aid())))
    snapshot = capture(location)
    original = snapshot.sha256
    (location[0] / 'specroad.json').unlink()
    snapshot.configuration.data['project_id'] = 'foreign'
    snapshot.inputs.records[0].data['statement'] = 'foreign'
    snapshot.binding['resources'].clear()
    with pytest.raises(FrozenInstanceError):
        snapshot.kind = 'git'
    assert snapshot.sha256 == original
    assert not compare_sources(snapshot, snapshot).data['changed']


def test_git_snapshot_never_uses_current_configuration_or_artifacts(tmp_path):
    files = source_files(domain_value('requirement', id=aid(), statement='Committed'))
    location = source(tmp_path / 'project', 'git', files)
    put(location[0], 'specroad.json', b'not valid current configuration')
    put(location[0], 'spec/requirements/' + aid() + '.json', b'not valid current artifact')
    put(location[0], '.specroad/transactions/pending/journal.json', b'current recovery blocker')
    original = inventory(tmp_path)
    snapshot = capture(location)
    assert snapshot.configuration.project_id == 'sample'
    assert snapshot.inputs.records[0].data['statement'] == 'Committed'
    assert snapshot.commit_id == location[1]['reference']
    assert inventory(tmp_path) == original


def test_local_source_is_read_only_and_has_no_git_dependency(tmp_path):
    location = source(tmp_path / 'project', 'local', source_files(domain_value('requirement', id=aid())))
    original = inventory(tmp_path)
    with no_write_attempts():
        snapshot = capture(location)
        result = compare_sources(snapshot, snapshot).data
    assert not result['changed'] and inventory(tmp_path) == original
    for key in ('full_semantic_validation', 'approval_granted', 'write_authorized'):
        assert snapshot.binding[key] is False and result[key] is False
    assert snapshot.binding['atomic_snapshot'] is False


def test_local_recovery_state_blocks_normal_source_acquisition(tmp_path):
    location = source(tmp_path / 'project', 'local', source_files())
    put(location[0], '.specroad/transactions/pending/journal.json', b'{}')
    original = inventory(tmp_path)
    with pytest.raises(OperationFailure) as caught:
        capture(location)
    assert caught.value.details['preflight']['reason'] == 'recovery_required'
    assert inventory(tmp_path) == original


def test_local_observed_artifact_change_is_not_a_mixed_snapshot(tmp_path):
    location = source(tmp_path / 'project', 'local', source_files(domain_value('requirement', id=aid())))
    target = 'spec/requirements/' + aid() + '.json'
    original_read = ProjectSource.read_normative
    changed = False

    def changing(reader, path, **options):
        nonlocal changed
        raw = original_read(reader, path, **options)
        if path == target and not changed:
            changed = True
            put(location[0], path, artifact_bytes(domain_value('requirement', id=aid(), statement='Changed')))
        return raw

    with patch.object(ProjectSource, 'read_normative', changing), pytest.raises(ModelError) as caught:
        capture(location)
    assert caught.value.reason == 'comparison_source_changed' and caught.value.path == target


@pytest.mark.parametrize('kind', ['local', 'git'])
def test_expected_project_identity_is_required_before_comparison(tmp_path, kind):
    root, options = source(tmp_path / 'project', kind, source_files())
    with pytest.raises(ModelError) as caught:
        ComparisonSourceSnapshot(root, **options, expected_project_id='foreign')
    assert caught.value.reason == 'project_identity_mismatch'


def test_different_projects_cannot_be_compared(tmp_path):
    before = capture(source(tmp_path / 'a', 'local', source_files()))
    after = capture(source(tmp_path / 'b', 'git', source_files(configuration=configuration_value(project_id='foreign'))))
    with pytest.raises(ModelError) as caught:
        compare_sources(before, after)
    assert caught.value.reason == 'comparison_project_mismatch'


@pytest.mark.parametrize('kind', ['local', 'git'])
def test_incompatible_configuration_is_rejected(tmp_path, kind):
    location = source(tmp_path / 'project', kind, source_files(configuration=configuration_value(schema_version='99.0.0')))
    with pytest.raises(ModelError) as caught:
        capture(location)
    assert caught.value.reason == 'unsupported_schema_version'


@pytest.mark.parametrize('kind', ['baseline', 'bundle'])
def test_reserved_source_kind_is_unavailable_without_reading_any_fallback(tmp_path, kind):
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        ComparisonSourceSnapshot(tmp_path / 'absent', kind=kind, reference='HEAD')
    assert caught.value.reason == 'comparison_source_unavailable'


@pytest.mark.parametrize('kind', ['local', 'git'])
def test_opaque_normative_resources_are_bound_but_deltas_need_later_semantics(tmp_path, kind):
    old = source_files(extra={'profiles/policy.json': b'{"owned":1}'})
    new = source_files(extra={'profiles/policy.json': b'{"owned":2}'})
    before = capture(source(tmp_path / 'a', kind, old))
    after = capture(source(tmp_path / 'b', kind, new))
    assert before.uncompared_resources == (('profiles/policy.json', b'{"owned":1}'),)
    assert before.binding['uncompared_resources'] == ['profiles/policy.json']
    assert not compare_sources(before, before).data['changed']
    with pytest.raises(ModelError) as caught:
        compare_sources(before, after)
    assert caught.value.reason == 'comparison_resource_semantics_unavailable'


@pytest.mark.parametrize('kind', ['local', 'git'])
def test_non_normative_bytes_do_not_become_artifacts(tmp_path, kind):
    location = source(tmp_path / 'project', kind, source_files(extra={
        'generated/untrusted.json': b'not json', 'attachments/untrusted.json': b'not json',
        'foreign/untrusted.json': b'not json', 'archive/untrusted.json': b'not json'}))
    snapshot = capture(location)
    assert snapshot.inputs.records == ()
    assert [path for path, _ in snapshot.resources] == ['specroad.json']


@pytest.mark.parametrize('kind', ['local', 'git'])
def test_unknown_stored_artifact_fields_fail_during_acquisition(tmp_path, kind):
    value = domain_value('requirement', id=aid(), made_up_field=True)
    location = source(tmp_path / 'project', kind, source_files(value))
    with pytest.raises(ModelError):
        capture(location)


@pytest.mark.parametrize('mode,data', [('100644', b'not a directory'), ('120000', b'foreign'), ('160000', '1' * 40)])
def test_git_managed_root_cannot_silently_become_an_empty_inventory(tmp_path, mode, data):
    location = source(tmp_path / 'project', 'git', source_files(extra={'spec': (mode, data)}))
    with pytest.raises((SafetyViolation, ModelError)):
        capture(location)


@pytest.mark.parametrize('kind', ['local', 'git'])
def test_unclassified_json_in_a_normative_tree_is_rejected(tmp_path, kind):
    location = source(tmp_path / 'project', kind, source_files(extra={'spec/unknown.json': b'{}'}))
    with pytest.raises(ModelError) as caught:
        capture(location)
    assert caught.value.reason == 'unclassified_normative_json'


@pytest.mark.parametrize('kind', ['local', 'git'])
def test_only_declared_managed_portions_are_compared(tmp_path, kind):
    value = domain_value('requirement', id=aid())
    goal = domain_value('goal', id=aid('goal'))
    config = configuration_value(managed_paths=['spec/requirements'])
    location = source(tmp_path / 'project', kind, source_files(value, goal, configuration=config))
    snapshot = capture(location)
    assert [r.identity.id for r in snapshot.inputs.records] == [aid()]


@pytest.mark.parametrize('kind', ['local', 'git'])
def test_missing_explicit_artifact_is_not_silently_omitted(tmp_path, kind):
    config = configuration_value(managed_paths=['spec/requirements/' + aid() + '.json'])
    location = source(tmp_path / 'project', kind, source_files(configuration=config))
    with pytest.raises((FileNotFoundError, ModelError)):
        capture(location)
