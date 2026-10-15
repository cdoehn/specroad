"""Variant comparison reference cases, owned inputs and captured-source parity."""
from concurrent.futures import ThreadPoolExecutor
import copy
import json

import pytest

from specroad.cli.application import dispatch_result
from specroad.cli.result_schemas import validate_result_document
from specroad.configurations.evaluation import ConfigurationEvaluationError
from specroad.graph.comparison import ComparisonInputs
from specroad.graph.relations import SourceRelations
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.query import ComparisonSourceSnapshot, ReadCommandWork, compare_semantic, compare_sources, diff_project
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.git_objects import GitFixture
from support.read_only import inventory, make_project, no_write_attempts
from support.records import record_value
from support.relations import aid, edge
from support.srx import binary, expression_document, field, literal


SELECTED = aid('configuration', 3)


def condition(value):
    return expression_document(binary('eq', field('/effective_values/platform', 'configuration'), literal(value)))


def values():
    return [record_value('configuration', id=aid('configuration'), name='Root', selection={}),
        record_value('configuration', id=aid('configuration', 2), name='Middle', parent=aid('configuration'),
            dimensions=[{'name': 'edition', 'allowed_values': ['basic', 'pro'], 'default': 'basic'}], selection={}),
        record_value('configuration', id=SELECTED, name='Leaf', parent=aid('configuration', 2), dimensions=[],
            selection={'edition': 'pro'}),
        domain_value('requirement', id=aid(), language='en'),
        domain_value('requirement', id=aid(number=2), language='en', applicability=condition('linux')),
        domain_value('requirement', id=aid(number=3), language='en', applicability=condition('windows'))]


def model(items):
    return ComparisonInputs('sample', tuple(SourceRelations(artifact_bytes(v), path=v['id'] + '.json') for v in items))


def compare(old, new):
    return compare_semantic(model(old), model(new), before_configuration_id=SELECTED, after_configuration_id=SELECTED).data


def pair(tmp_path, old=None, new=None):
    old = values() if old is None else old
    if new is None:
        new = copy.deepcopy(old); new[1]['selection'] = {'platform': 'windows'}
    before, after = tmp_path / 'before', tmp_path / 'after'
    before.mkdir(); after.mkdir()
    return make_project(before, *old), make_project(after, *new)


def arguments(before):
    return {'against': str(before), 'against_kind': 'local', 'configuration_id': SELECTED}


def damaged(kind):
    result = values()
    if kind == 'invalid_value': result[2]['selection']['platform'] = 'unsupported'
    elif kind == 'unknown_dimension': result[2]['selection']['missing'] = 'linux'
    else: result[1]['parent'] = SELECTED
    return result


def test_nested_defaults_and_overrides_produce_exact_independent_side_memberships():
    old = values(); new = copy.deepcopy(old); new[1]['selection']['platform'] = 'windows'
    scope = compare(old, new)['configuration_scope']
    assert scope['before']['configuration']['effective_values'] == {'platform': 'linux', 'edition': 'pro'}
    assert scope['after']['configuration']['effective_values'] == {'platform': 'windows', 'edition': 'pro'}
    assert scope['before']['configuration']['configuration_id'] == scope['after']['configuration']['configuration_id'] == SELECTED
    assert scope['added_ids'] == [aid(number=3)] and scope['removed_ids'] == [aid(number=2)]


def test_parent_change_hidden_by_leaf_override_changes_binding_without_false_membership():
    old = values(); old[2]['selection']['platform'] = 'linux'
    new = copy.deepcopy(old); new[0]['selection']['platform'] = 'windows'
    scope = compare(old, new)['configuration_scope']
    assert scope['before']['configuration']['effective_values'] == scope['after']['configuration']['effective_values']
    assert scope['configuration_changed'] and not scope['membership_changed']
    assert scope['added_ids'] == scope['removed_ids'] == []


@pytest.mark.parametrize('side', ['before', 'after'])
@pytest.mark.parametrize('kind,reason', [('invalid_value', 'invalid_dimension_selection'),
    ('unknown_dimension', 'unknown_dimension'), ('cycle', 'configuration_parent_cycle')])
def test_bad_selected_chain_on_either_side_has_no_partial_diff(tmp_path, side, kind, reason):
    old, new = (damaged(kind), values()) if side == 'before' else (values(), damaged(kind))
    with pytest.raises(ConfigurationEvaluationError) as caught: compare(old, new)
    assert caught.value.code == 'SRV130' and caught.value.reason == reason
    before, after = pair(tmp_path, old, new)
    direct = diff_project(after, **arguments(before))
    with ReadCommandWork('diff', after, **arguments(before)) as work:
        while not work.advance(1): pass
        assert work.result.as_dict() == direct.as_dict()
    assert direct.exit_code == 3 and not direct.complete and direct.result is None
    assert direct.diagnostics[0].code == 'SRV130'


def dependency_values(excluded):
    result = values()
    result[3]['relations'] = [edge('depends_on', aid(number=2)), edge('depends_on', aid(number=4), number=2)]
    result[4].pop('applicability')
    result[4]['relations'] = [edge('depends_on', aid(number=3), number=3)]
    result[5]['applicability'] = condition('windows' if excluded else 'linux')
    result.append(domain_value('requirement', id=aid(number=4), language='en',
        relations=[edge('depends_on', aid(number=3), number=4)]))
    return result


@pytest.mark.parametrize('old_excluded,new_excluded', [(True, False), (False, True), (True, True)])
def test_conflicts_keep_shortest_tie_broken_paths_and_the_actual_failing_side(tmp_path, old_excluded, new_excluded):
    before, after = pair(tmp_path, dependency_values(old_excluded), dependency_values(new_excluded))
    result = diff_project(after, **arguments(before)); scope = result.as_dict()['result']['configuration_scope']
    assert result.exit_code == 3 and result.complete
    expected_diagnostics = []
    for side, excluded in [('before', old_excluded), ('after', new_excluded)]:
        conflicts = scope[side]['inconsistent_dependencies']
        assert scope[side]['consistent'] is (not excluded)
        if not excluded:
            assert conflicts == []; continue
        assert [(c['source_id'], c['target_id'], c['distance']) for c in conflicts] == [
            (aid(), aid(number=3), 2), (aid(number=2), aid(number=3), 1), (aid(number=4), aid(number=3), 1)]
        assert [r['id'] for r in conflicts[0]['path']['artifacts']] == [aid(), aid(number=2), aid(number=3)]
        expected_diagnostics.extend((identity, 'configuration-diff-' + side) for identity in (aid(), aid(number=2), aid(number=4)))
    assert [(d.artifact_id, d.rule_id) for d in result.diagnostics] == sorted(expected_diagnostics)
    validate_result_document('artifact-diff-v1', result.as_dict()['result'])


@pytest.mark.parametrize('side', ['before', 'after', 'both'])
def test_original_bytes_override_forged_cached_identities_for_all_diff_classes(side):
    old = values(); new = copy.deepcopy(old); new[1]['selection']['platform'] = 'windows'; new[3]['title'] = 'Changed'
    expected = compare(old, new); left, right = model(old), model(new)
    for name, supplied in [('before', left), ('after', right)]:
        if side not in (name, 'both'): continue
        req = next(r for r in supplied.records if r.data['id'] == aid())
        other = next(r for r in supplied.records if r.data['id'] == SELECTED)
        object.__setattr__(req, 'identity', other.identity)
    actual = compare_semantic(left, right, before_configuration_id=SELECTED, after_configuration_id=SELECTED).data
    assert actual == expected
    assert next(c for c in actual['changes'] if c['artifact_id'] == aid())['fields'][0]['pointer'] == '/title'


@pytest.mark.parametrize('bad', [None, {}, 'record'])
def test_invalid_retained_comparison_record_is_a_model_error(bad):
    left, right = model(values()), model(values()); object.__setattr__(left, 'records', (bad,))
    with pytest.raises(ModelError) as caught:
        compare_semantic(left, right, before_configuration_id=SELECTED, after_configuration_id=SELECTED)
    assert caught.value.reason == 'source_relations_required'


def test_configured_inputs_revalidate_original_duplicate_identities():
    left, right = model(values()), model(values())
    object.__setattr__(left, 'records', left.records + left.records[:1])
    with pytest.raises(ModelError) as caught:
        compare_semantic(left, right, before_configuration_id=SELECTED, after_configuration_id=SELECTED)
    assert caught.value.reason == 'duplicate_artifact_id'


@pytest.mark.parametrize('side', ['before', 'after'])
@pytest.mark.parametrize('subject', ['parent', 'requirement'])
@pytest.mark.parametrize('advance', [1, 2])
def test_retained_local_work_checks_each_original_source_before_publication(tmp_path, side, subject, advance):
    before, after = pair(tmp_path)
    with ReadCommandWork('diff', after, **arguments(before)) as work:
        assert not work.advance(advance)
        root = before if side == 'before' else after
        kind, identity = ('configuration', aid('configuration')) if subject == 'parent' else ('requirement', aid())
        path = root / artifact_path(kind, identity, 'SR')
        value = json.loads(path.read_bytes()); value['revision'] += 1; path.write_bytes(artifact_bytes(value))
        while not work.advance(1): pass
        assert work.result.exit_code == 6 and work.result.result is None and not work.result.complete


def test_comparison_source_snapshots_keep_their_owned_capture_after_disk_changes(tmp_path):
    before, after = pair(tmp_path); left, right = ComparisonSourceSnapshot(before), ComparisonSourceSnapshot(after)
    expected = compare_sources(left, right, before_configuration_id=SELECTED, after_configuration_id=SELECTED)
    path = after / artifact_path('configuration', aid('configuration'), 'SR')
    value = json.loads(path.read_bytes()); value['revision'] += 1; path.write_bytes(artifact_bytes(value))
    actual = compare_sources(left, right, before_configuration_id=SELECTED, after_configuration_id=SELECTED)
    assert actual.data == expected.data and actual.sha256 == expected.sha256


def test_git_local_source_api_cli_and_retained_work_share_the_pinned_variant_delta(tmp_path):
    repo = GitFixture(tmp_path / 'project'); old = values(); new = copy.deepcopy(old)
    new[1]['selection']['platform'] = 'windows'; make_project(repo.root, *old)
    names = ['specroad.json', *(artifact_path(v['artifact_type'], v['id'], 'SR') for v in old)]
    files = {str(name): (repo.root / name).read_bytes() for name in names}; commit = repo.commit(files)
    make_project(repo.root, *new); captured = repo.capture()
    expected = compare_sources(ComparisonSourceSnapshot(repo.root, kind='git', reference=commit),
        ComparisonSourceSnapshot(repo.root), before_configuration_id=SELECTED, after_configuration_id=SELECTED)
    options = {'against': commit, 'configuration_id': SELECTED}
    direct = diff_project(repo.root, **options)
    cli = dispatch_result(['diff', '--project', str(repo.root), '--against', commit, '--configuration', SELECTED, '--format=json'])
    with ReadCommandWork('diff', repo.root, **options) as work:
        while not work.advance(1): pass
        assert work.result.as_dict() == direct.as_dict()
    assert direct.exit_code == cli.exit_code == 0
    assert direct.as_dict()['result'] == cli.as_dict()['result'] == expected.data
    assert direct.details['base_commit'] == commit and repo.capture() == captured


def test_moving_git_reference_does_not_retarget_already_captured_configuration(tmp_path):
    repo = GitFixture(tmp_path / 'project'); old = values(); new = copy.deepcopy(old); new[1]['selection']['platform'] = 'windows'
    make_project(repo.root, *old)
    names = ['specroad.json', *(artifact_path(v['artifact_type'], v['id'], 'SR') for v in old)]
    files = {str(name): (repo.root / name).read_bytes() for name in names}; commit = repo.commit(files)
    make_project(repo.root, *new)
    with ReadCommandWork('diff', repo.root, against='main', configuration_id=SELECTED) as work:
        assert not work.advance(2)
        repo.commit({str(name): (repo.root / name).read_bytes() for name in names}, parent=commit)
        assert work.advance(1)
        assert work.result.exit_code == 0 and work.result.details['base_commit'] == commit
        assert work.result.as_dict()['result']['configuration_scope']['added_ids'] == [aid(number=3)]


def test_concurrent_selection_pairs_keep_independent_membership_and_input_hashes():
    supplied = model(values()); pairs = [(SELECTED, aid('configuration')), (aid('configuration'), SELECTED)] * 6
    def run(pair):
        return compare_semantic(supplied, supplied, before_configuration_id=pair[0], after_configuration_id=pair[1]).data
    expected = [run(pair) for pair in pairs]
    with ThreadPoolExecutor(max_workers=4) as pool: actual = list(pool.map(run, pairs))
    assert actual == expected
    assert actual[0]['input_sha256'] != actual[1]['input_sha256']
    assert all(item['configuration_scope']['added_ids'] == item['configuration_scope']['removed_ids'] == [] for item in actual)


@pytest.mark.parametrize('kind', ['valid', 'invalid_value', 'cycle', 'conflict'])
def test_success_and_model_failure_variants_remain_read_only(tmp_path, kind):
    old = dependency_values(False) if kind == 'conflict' else values()
    new = dependency_values(True) if kind == 'conflict' else (values() if kind == 'valid' else damaged(kind))
    before, after = pair(tmp_path, old, new); captured = inventory(before), inventory(after)
    with no_write_attempts(): result = diff_project(after, **arguments(before))
    assert result.exit_code == (0 if kind == 'valid' else 3)
    assert (inventory(before), inventory(after)) == captured


def test_configuration_selection_does_not_certify_an_unavailable_baseline_source(tmp_path):
    root = tmp_path / 'project'; root.mkdir(); make_project(root, *values())
    result = diff_project(root, 'baseline-1', against_kind='baseline', configuration_id=SELECTED)
    assert result.exit_code != 0 and result.result is None and not result.complete
    assert result.diagnostics[0].rationale == 'comparison_source_unavailable'
