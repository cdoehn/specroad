"""Literal domain facts, explicit absence and order/cache-independent impact."""
from copy import deepcopy
from unittest.mock import patch
import importlib

import pytest

from specroad.cli.application import dispatch_result
from specroad.cli.commands import builtin_registry
from specroad.cli.result_schemas import validate_result_document
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.model.schema_catalog import SchemaCatalog
from specroad.query import impact_artifact
from support.artifacts import artifact_bytes
from support.domain import domain_value, waiver
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.relations import aid, edge, rid
from test_query_impact import project, mixed_graph
from test_relation_review_status import review

impact_module = importlib.import_module('specroad.query.impact')


def graph():
    return [domain_value('requirement', id=aid(), relations=[
                edge('derived_from', aid('need'), 1), edge('allocated_to', aid('component'), 2)]),
            domain_value('need', id=aid('need'), relations=[edge('addresses', aid('goal'), 3)]),
            domain_value('component', id=aid('component'), relations=[]),
            domain_value('requirement', id=aid(number=2), relations=[edge('depends_on', aid(), 4)]),
            domain_value('goal', id=aid('goal'), relations=[])]


def observed(data):
    rows = data['artifact_observations']
    assert [row['artifact_id'] for row in rows] == sorted({row['artifact_id'] for row in rows})
    return {row['artifact_id']: row for row in rows}


def test_observations_cover_exactly_the_start_and_all_direct_endpoints(tmp_path):
    root = project(tmp_path / 'project', graph()); outcome = impact_artifact(root, aid())
    assert outcome.exit_code == 0 and outcome.complete
    data = outcome.as_dict()['result']; rows = observed(data)
    assert set(rows) == {aid(), aid(number=2), aid('need'), aid('component')}
    assert aid('goal') not in rows
    for name in (aid(), aid(number=2)):
        assert rows[name] == {'artifact_id': name, 'present': True, 'artifact_type': 'requirement',
            'fields': {'priority': {'state': 'present', 'value': 'mandatory'},
                       'verification_plan_status': {'state': 'present', 'value': 'not_planned'}},
            'verification_assessment': {'state': 'not_performed'}}
    for name, kind in ((aid('need'), 'need'), (aid('component'), 'component')):
        assert rows[name] == {'artifact_id': name, 'present': True, 'artifact_type': kind,
            'fields': {'priority': {'state': 'missing'}, 'verification_plan_status': {'state': 'missing'}},
            'verification_assessment': {'state': 'not_performed'}}


@pytest.mark.parametrize('priority', ['mandatory', 'high', 'medium', 'low'])
def test_only_the_actual_declared_priority_is_reported_without_ranking_neighbours(tmp_path, priority):
    values = graph(); values[1]['priority'] = priority
    root = project(tmp_path / 'project', values)
    data = impact_artifact(root, aid()).as_dict()['result']; rows = observed(data)
    assert rows[aid('need')]['fields']['priority'] == {'state': 'present', 'value': priority}
    assert rows[aid('component')]['fields']['priority'] == {'state': 'missing'}
    assert {g['relation_type']: g['artifact_ids'] for g in data['groups']} == {
        'allocated_to': [aid('component')], 'depends_on': [aid(number=2)], 'derived_from': [aid('need')]}
    assert all('rank' not in row and 'verification_result' not in row for row in rows.values())


@pytest.mark.parametrize('status', ['not_planned', 'planned', 'running', 'waived', 'not_applicable'])
def test_declared_verification_workflow_never_becomes_a_verification_result(tmp_path, status):
    values = graph(); values[0]['verification_plan_status'] = status
    if status == 'waived':
        values[0]['verification_waiver'] = waiver()
    root = project(tmp_path / 'project', values)
    outcome = impact_artifact(root, aid()); assert outcome.exit_code == 0
    row = observed(outcome.as_dict()['result'])[aid()]
    assert row['fields']['verification_plan_status'] == {'state': 'present', 'value': status}
    assert row['verification_assessment'] == {'state': 'not_performed'}
    assert 'verification_result' not in row and 'passed' not in row


@pytest.mark.parametrize('hint', ['statement', 'title', 'extension'])
def test_text_and_extensions_cannot_fill_missing_domain_fields(tmp_path, hint):
    values = graph()
    if hint == 'extension':
        values[1]['extensions'] = {'org.example': {'priority': 'mandatory', 'verification_result': 'passed'}}
    else:
        values[1][hint] = 'Priority mandatory: verified, passed, approved, MUST.'
    root = project(tmp_path / 'project', values)
    row = observed(impact_artifact(root, aid()).as_dict()['result'])[aid('need')]
    assert row['fields'] == {'priority': {'state': 'missing'}, 'verification_plan_status': {'state': 'missing'}}
    assert row['verification_assessment'] == {'state': 'not_performed'}


def test_missing_target_is_unavailable_without_inferred_artifact_type_or_priority(tmp_path):
    start = domain_value('requirement', id=aid(), relations=[edge('derived_from', aid('need', 999))])
    root = project(tmp_path / 'project', [start]); outcome = impact_artifact(root, aid())
    assert outcome.exit_code == 1 and outcome.complete
    rows = observed(outcome.as_dict()['result'])
    assert set(rows) == {aid(), aid('need', 999)}
    assert rows[aid('need', 999)] == {'artifact_id': aid('need', 999), 'present': False,
        'artifact_type': None, 'fields': {'priority': {'state': 'unavailable'},
                                        'verification_plan_status': {'state': 'unavailable'}},
        'verification_assessment': {'state': 'not_performed'}}
    assert rows[aid()]['present']


def test_current_relation_review_never_certifies_the_subject_verification(tmp_path):
    start = domain_value('requirement', id=aid(), verification_plan_status='planned',
                         relations=[edge('addresses', aid('goal'))])
    target = domain_value('goal', id=aid('goal'), relations=[])
    record = review(start, target)
    root = project(tmp_path / 'project', [start, target, record])
    outcome = impact_artifact(root, aid()); assert outcome.exit_code == 0
    data = outcome.as_dict()['result']
    assert data['review_groups']['current']['relation_ids'] == [rid()]
    rows = observed(data)
    assert aid('relation_review', 20) not in rows
    assert rows[aid()]['fields']['verification_plan_status'] == {'state': 'present', 'value': 'planned'}
    assert all(row['verification_assessment'] == {'state': 'not_performed'} for row in rows.values())
    assert outcome.as_dict()['summary']['approval_granted'] is False


@pytest.mark.parametrize('field,bad', [('priority', None), ('priority', 'urgent'),
                                     ('verification_plan_status', None), ('verification_plan_status', 'passed')])
def test_invalid_declared_values_are_model_errors_instead_of_missing_defaults(tmp_path, field, bad):
    values = graph(); values[0][field] = bad
    root = project(tmp_path / 'project', values); outcome = impact_artifact(root, aid())
    assert outcome.exit_code == 3 and not outcome.complete and outcome.as_dict()['result'] is None


@pytest.mark.parametrize('mode', ['reverse_sources', 'reverse_relations', 'both'])
def test_order_changes_preserve_all_affected_sets_facts_and_review_selection(tmp_path, mode):
    values = mixed_graph(); root = project(tmp_path / 'project', values)
    before = impact_artifact(root, aid()).as_dict()['result']
    changed = deepcopy(values[::-1] if mode in ('reverse_sources', 'both') else values)
    for value in changed:
        if mode in ('reverse_relations', 'both'):
            value['relations'].reverse()
        put(root, artifact_path(value['artifact_type'], value['id'], 'SR'), artifact_bytes(value))
    outcome = impact_artifact(root, aid()); assert outcome.exit_code == 1 and outcome.complete
    after = outcome.as_dict()['result']
    assert {k: v for k, v in after.items() if k != 'coverage'} == {
        k: v for k, v in before.items() if k != 'coverage'}
    by_source = {value['id']: value for value in changed}
    for diagnostic in outcome.diagnostics:
        position = int(diagnostic.location['pointer'].rsplit('/', 1)[-1])
        relation = by_source[diagnostic.artifact_id]['relations'][position]
        assert relation['relation_id'] == diagnostic.related_ids[0]


@pytest.mark.parametrize('cache', ['malformed', 'claimed_complete', 'stale_status', 'symlink'])
def test_cache_state_cannot_change_direct_scope_review_status_or_missing_facts(tmp_path, cache):
    root = project(tmp_path / 'project', graph())
    before = impact_artifact(root, aid()).as_dict()['result']
    path = root / '.specroad/cache/relation-index-v1.json'; path.parent.mkdir(parents=True)
    if cache == 'symlink':
        outside = tmp_path / 'untrusted-cache.json'; outside.write_bytes(b'{"priority":"mandatory"}')
        path.symlink_to(outside)
    else:
        path.write_bytes({'malformed': b'{', 'claimed_complete': b'{"complete":true,"relations":[]}',
                          'stale_status': b'{"status":"current","verification_result":"passed"}'}[cache])
    files = inventory(root)
    with no_write_attempts():
        outcome = impact_artifact(root, aid())
    assert outcome.exit_code == 0 and outcome.as_dict()['result'] == before
    assert inventory(root) == files


def test_cache_claim_cannot_replace_unreadable_normative_artifacts(tmp_path):
    root = project(tmp_path / 'project', graph())
    put(root, '.specroad/cache/relation-index-v1.json', b'{"complete":true,"relations":[]}')
    put(root, artifact_path('requirement', aid(), 'SR'), b'{broken')
    outcome = impact_artifact(root, aid())
    assert outcome.exit_code == 3 and not outcome.complete and outcome.as_dict()['result'] is None


@pytest.mark.parametrize('kind', ['priority', 'review'])
def test_changes_during_fact_projection_block_the_whole_answer(tmp_path, kind):
    values = mixed_graph(); root = project(tmp_path / 'project', values)
    original = impact_module._artifact_observations

    def alter(records, start, groups):
        rows = original(records, start, groups)
        value = deepcopy(values[1] if kind == 'priority' else values[-1])
        value['priority' if kind == 'priority' else 'reason'] = 'high' if kind == 'priority' else 'Changed review.'
        put(root, artifact_path(value['artifact_type'], value['id'], 'SR'), artifact_bytes(value))
        return rows

    with patch.object(impact_module, '_artifact_observations', alter):
        outcome = impact_artifact(root, aid())
    assert outcome.exit_code == 6 and not outcome.complete and outcome.as_dict()['result'] is None


def test_fact_projection_is_owned_and_minor_version_matches_schema_metadata(tmp_path):
    root = project(tmp_path / 'project', graph()); before = inventory(root)
    with no_write_attempts():
        outcome = impact_artifact(root, aid())
        cli = dispatch_result(['impact', aid(), '--project', str(root)])
    assert outcome.exit_code == cli.exit_code == 0
    expected = outcome.as_dict()['result']; data = deepcopy(expected)
    assert data['format_version'] == '1.1.0'
    rows = observed(data); rows[aid()]['fields']['priority']['value'] = 'low'
    assert outcome.as_dict()['result'] == expected == cli.as_dict()['result']
    assert inventory(root) == before
    resource = SchemaCatalog(builtin_registry()).show('artifact-impact-v1')
    assert resource['metadata']['version'] == '1.1.0'
    assert resource['schema']['properties']['format_version']['const'] == '1.1.0'
    broken = deepcopy(expected); observed(broken)[aid('need')]['fields']['priority']['value'] = 'mandatory'
    with pytest.raises(ModelError):
        validate_result_document('artifact-impact-v1', broken)
