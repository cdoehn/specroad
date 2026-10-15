"""Bound configuration selection in real query, validation and seed adapters."""
import copy
from hashlib import sha256
import json
from unittest.mock import patch

import pytest

from specroad.cli.application import dispatch_result, execute_request
from specroad.configurations import resolve_configuration, validate_configured_model
from specroad.configurations.evaluation import ConfigurationEvaluationError
from specroad.graph.relations import SourceRelations
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_inputs import ScopeSeedInputs
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.query import NormalizedQuery, QueryWork, ReadCommandWork, query_project, query_records
from specroad.query.selection import select_query
from specroad.security import ProjectBoundary
from specroad.srx import LoadedGraph, SrxError
from specroad.storage.project import ProjectSource
from specroad.storage.read_only import validate_project_read_only
from specroad.storage.scope_seeds import read_artifact_scope_seeds
from specroad.validation import ModelGate
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.model_validation import doc, no_dependencies, profile
from support.portable import build_distribution
from support.processes import run_python
from support.production_validation import inputs, write_project
from support.profile_composition import lint
from support.read_only import inventory, make_project, no_write_attempts
from support.records import record_value
from support.relations import aid, edge
from support.scopes import descriptor
from support.srx import binary, expression_document, field, literal
from support.srx_graph import incoming, reach


def configuration(number=1, **changes):
    return record_value('configuration', id=aid('configuration', number), name='Variant ' + str(number), **changes)


def requirement(number=1, **changes):
    changes.setdefault('language', 'en')
    return domain_value('requirement', id=aid(number=number), **changes)


def condition(platform):
    return expression_document(binary('eq', field('/effective_values/platform', 'configuration'), literal(platform)))


def variants():
    return [configuration(), configuration(2, selection={'platform': 'windows'}), requirement(),
            requirement(2, applicability=condition('windows')), requirement(3, applicability=condition('linux'))]


def records(values):
    return tuple(SourceRelations(artifact_bytes(v), path=v['id'] + '.json') for v in values)


def query(**kwargs):
    kwargs.setdefault('filters', {'type': ['requirement']})
    return NormalizedQuery(**kwargs)


def ids(page):
    return [item['id'] for item in page['items']]


def project(path, values=None):
    path.mkdir(); return make_project(path, *(variants() if values is None else values))


def live_validation(root, data, selected=aid('configuration'), **kwargs):
    return validate_project_read_only(root, profile_resources=data.profiles, core_key=data.profiles[0].key,
        profile_paths={p.key: 'profiles/' + p.profile_id + '.json' for p in data.profiles},
        configuration_id=selected, **kwargs)


def configured_scope(kind, selector, *, wrapper=False, selected=aid('configuration')):
    base = descriptor(kind, selector)
    return ScopeDescriptor(descriptor('configuration', {'base_scope_descriptor': base}, configuration_id=selected)
        if wrapper else {**base, 'configuration_id': selected})


@pytest.mark.parametrize('offset,limit,expected', [(0, 1, [aid()]), (1, 1, [aid(number=3)]), (2, 1, []), (0, 0, [])])
def test_applicability_is_evaluated_before_exact_sort_and_page(offset, limit, expected):
    supplied = records(variants()); request = query(sort=['id'], offset=offset, limit=limit)
    page = query_records(supplied, request, project={}, configuration_id=aid('configuration'))
    assert ids(page.data) == expected and page.data['total'] == 2 and page.source_count == 5
    assert page.configuration_binding == resolve_configuration(supplied, aid('configuration')).binding
    assert set(page.data) == {'items', 'total', 'offset', 'limit', 'returned', 'truncated'}


def test_unselected_query_keeps_all_potential_variants_and_has_no_selected_binding():
    page = query_records(records(variants()), query(), project={})
    assert ids(page.data) == [aid(), aid(number=2), aid(number=3)]
    assert page.configuration_binding is None


def test_srx_query_receives_the_resolved_effective_configuration():
    supplied = records(variants()); request = query(srx_filters=[condition('windows')])
    assert not query_records(supplied, request, project={}, configuration_id=aid('configuration')).data['items']
    page = query_records(supplied, request, project={}, configuration_id=aid('configuration', 2))
    assert ids(page.data) == [aid(), aid(number=2)]


def test_raw_srx_context_cannot_override_an_explicit_selected_configuration():
    with pytest.raises(ConfigurationEvaluationError) as caught:
        query_records(records(variants()), query(), project={}, configuration_id=aid('configuration'),
                      configuration={'configuration_id': 'forged', 'effective_values': {'platform': 'windows'}})
    assert caught.value.reason == 'query_configuration_context_conflict'


def test_relation_filters_do_not_count_edges_to_excluded_artifacts():
    values = variants(); values[2]['relations'] = [edge('depends_on', aid(number=2))]
    page = query_records(records(values), query(filters={'type': ['requirement'], 'has_relation': ['depends_on']}),
                         project={}, configuration_id=aid('configuration'))
    assert not page.data['items']


def test_srx_incoming_counts_ignore_excluded_origins():
    values = variants(); values[3]['relations'] = [edge('depends_on', aid())]
    request = query(filters={'owner': ['selected']}, srx_filters=[expression_document(binary('eq', incoming(), literal(0)))])
    values[2]['owner'] = 'selected'
    assert ids(query_records(records(values), request, project={}, configuration_id=aid('configuration')).data) == [aid()]
    assert query_records(records(values), request, project={}).data['items'] == []


def test_srx_reachability_does_not_traverse_an_excluded_intermediate():
    values = variants(); values[2].update(owner='start', relations=[edge('depends_on', aid(number=2))])
    values[3]['relations'] = [edge('depends_on', aid(number=3), number=2)]
    request = query(filters={'owner': ['start']}, srx_filters=[expression_document(reach(aid(number=3), depth=2))])
    assert ids(query_records(records(values), request, project={}).data) == [aid()]
    assert not query_records(records(values), request, project={}, configuration_id=aid('configuration')).data['items']


def test_selected_graph_preserves_original_records_while_restricting_adjacency():
    values = variants(); values[2]['relations'] = [edge('depends_on', aid(number=2))]; supplied = records(values)
    graph = LoadedGraph(supplied, rule_id='test', artifact_ids=[aid(), aid(number=3)])
    assert graph.artifact_ids == (aid(), aid(number=3))
    assert graph.artifact(aid(), rule_id='test') == values[2]
    assert graph.neighbours(aid(), 'both', '*') == ()
    with pytest.raises(SrxError): graph.artifact(aid(number=2), rule_id='test')
    assert supplied[2].data['relations'][0]['target'] == aid(number=2)


@pytest.mark.parametrize('selection', [[aid(), aid()], [aid(number=99)], 'ids', [1], {}])
def test_selected_graph_requires_a_distinct_subset_of_actual_loaded_ids(selection):
    with pytest.raises(SrxError) as caught:
        LoadedGraph(records(variants()), rule_id='test', artifact_ids=selection)
    assert caught.value.reason == 'graph_selection_invalid'


def test_invalid_excluded_source_cannot_be_hidden_by_applicability():
    values = variants(); values[3]['relations'] = [edge('depends_on', aid(number=99))]
    with pytest.raises(SrxError):
        query_records(records(values), query(), project={}, configuration_id=aid('configuration'))


def test_invalid_stored_derived_status_is_checked_even_on_excluded_records():
    values = variants(); values[3]['verification_result'] = 'passed'
    with pytest.raises(ModelError) as caught:
        query_records(records(values), query(), project={}, configuration_id=aid('configuration'))
    assert caught.value.reason == 'query_stored_verification_result'


def test_parent_revision_is_part_of_configuration_and_query_input_binding():
    values = [configuration(), configuration(2, parent=aid('configuration'), dimensions=[], selection={}), requirement()]
    first = query_records(records(values), query(), project={}, configuration_id=aid('configuration', 2))
    values[0]['revision'] += 1
    second = query_records(records(values), query(), project={}, configuration_id=aid('configuration', 2))
    assert first.data == second.data and first.query_sha256 == second.query_sha256
    assert first.inputs_sha256 != second.inputs_sha256
    assert first.configuration_binding['sha256'] != second.configuration_binding['sha256']


def test_external_query_work_has_the_same_filtered_page_and_configuration_binding(tmp_path):
    root = project(tmp_path / 'project'); supplied = records(variants()); request = query(offset=1, limit=1)
    expected = query_records(supplied, request, project={}, configuration_id=aid('configuration'))
    with QueryWork(tmp_path / 'spool', supplied, request, project={}, configuration_id=aid('configuration'),
                   protected_roots=(ProjectBoundary(root),), batch_bytes=1) as work:
        while not work.advance(1)['complete']: pass
        assert work.result.data == expected.data
        assert work.result.configuration_binding == expected.configuration_binding
        assert work.result.inputs_sha256 == expected.inputs_sha256


def test_query_api_cli_and_request_share_the_exact_selected_variant(tmp_path):
    root = project(tmp_path / 'project'); request = query(offset=1, limit=1)
    direct = query_project(root, request, configuration_id=aid('configuration'))
    cli = dispatch_result(['query', '--type', 'requirement', '--offset', '1', '--limit', '1',
        '--configuration', aid('configuration'), '--project', str(root), '--format=json'])
    structured = execute_request({'command_id': 'query', 'options': {'--type': ['requirement'],
        '--offset': '1', '--limit': '1', '--configuration': aid('configuration'), '--project': str(root)}}).result
    for result in (direct, cli, structured):
        assert result.exit_code == 0 and ids(result.as_dict()['result']) == [aid(number=3)]
        assert result.as_dict()['summary']['selected_configuration'] == resolve_configuration(records(variants()), aid('configuration')).binding
    assert direct.as_dict()['result'] == cli.as_dict()['result'] == structured.as_dict()['result']


def test_missing_query_configuration_has_srv130_and_no_partial_page(tmp_path):
    root = project(tmp_path / 'project')
    result = query_project(root, configuration_id=aid('configuration', 99))
    assert result.exit_code == 3 and not result.complete and result.result is None
    assert result.diagnostics[0].code == 'SRV130' and result.diagnostics[0].rationale == 'configuration_missing'


def test_query_rejects_changed_configuration_after_evaluation(tmp_path):
    root = project(tmp_path / 'project')
    with ReadCommandWork('query', root, query=query(), configuration_id=aid('configuration')) as work:
        assert not work.advance(2)
        path = root / artifact_path('configuration', aid('configuration'), 'SR')
        value = json.loads(path.read_bytes()); value['revision'] += 1; path.write_bytes(artifact_bytes(value))
        assert work.advance(1) and work.result.exit_code == 6 and work.result.result is None


@pytest.mark.parametrize('wrapper', [False, True])
def test_native_query_scope_page_matches_live_query_after_configuration_filtering(tmp_path, wrapper):
    root = project(tmp_path / 'project'); request = query(offset=1, limit=1)
    scope = configured_scope('query', {'query': request.data}, wrapper=wrapper)
    seeds = read_artifact_scope_seeds(ProjectSource(root), scope)
    result = query_project(root, request, configuration_id=aid('configuration'))
    assert seeds.selection.artifact_ids == tuple(ids(result.as_dict()['result'])) == (aid(number=3),)
    assert seeds.binding.sha256 == result.as_dict()['summary']['observation_sha256']
    effective = resolve_configuration(records(variants()), aid('configuration'))
    model = ProjectSource(root); loaded = ScopeSeedInputs(model.configuration, records(variants()))
    assert seeds.selection.configuration_sha256 == canonical_json_sha256({
        'project_configuration_sha256': loaded.configuration_sha256, 'selected_configuration_sha256': effective.sha256})
    assert not seeds.atomic_snapshot and not seeds.selection.closure_complete


@pytest.mark.parametrize('wrapper', [False, True])
def test_native_explicit_scope_filters_without_copying_or_filling_excluded_ids(tmp_path, wrapper):
    root = project(tmp_path / 'project')
    scope = configured_scope('explicit', {'artifact_ids': [aid(), aid(number=2), aid(number=3)],
                                         'resource_ids': []}, wrapper=wrapper)
    assert read_artifact_scope_seeds(ProjectSource(root), scope).selection.artifact_ids == (aid(), aid(number=3))


@pytest.mark.parametrize('kind', ['document', 'release'])
def test_existing_native_artifact_scope_selectors_accept_explicit_configuration(tmp_path, kind):
    value = record_value(kind, id=aid(kind), applicability=condition('windows')) if kind == 'document' else domain_value(
        kind, id=aid(kind), applicability=condition('windows'))
    root = project(tmp_path / 'project', [configuration(), value])
    scope = configured_scope(kind, {kind + '_id': value['id']})
    assert read_artifact_scope_seeds(ProjectSource(root), scope).selection.artifact_ids == ()


def test_native_query_scope_final_currentness_rejects_late_source_changes(tmp_path):
    import specroad.storage.scope_seeds as module
    root = project(tmp_path / 'project'); original = module.resolve_scope_seeds
    scope = configured_scope('query', {'query': query().data})
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        path = root / artifact_path('requirement', aid(), 'SR'); value = json.loads(path.read_bytes()); value['revision'] += 1
        path.write_bytes(artifact_bytes(value)); return result
    with patch.object(module, 'resolve_scope_seeds', side_effect=changed), pytest.raises(ModelError) as caught:
        read_artifact_scope_seeds(ProjectSource(root), scope)
    assert caught.value.reason == 'relation_index_source_changed'


def test_resource_complete_scopes_still_require_their_real_providers(tmp_path):
    root = project(tmp_path / 'project')
    with pytest.raises(ModelError) as caught:
        read_artifact_scope_seeds(ProjectSource(root), ScopeDescriptor(descriptor('project', configuration_id=aid('configuration'))))
    assert caught.value.reason == 'specialized_scope_provider_required'


def test_live_validation_and_query_publish_the_same_effective_configuration_binding(tmp_path):
    data = inputs(variants()); root = tmp_path / 'project'; root.mkdir(); write_project(root, data)
    observed = live_validation(root, data); queried = query_project(root, query(), configuration_id=aid('configuration'))
    assert observed.passed and observed.data['freshness_verified'] and observed.data['resource_files_verified']
    assert observed.data['selected_configuration'] == queried.as_dict()['summary']['selected_configuration']
    assert observed.data['configuration_sha256'] == sha256(data.configuration_bytes).hexdigest()


def test_production_profile_srx_uses_the_selected_configuration(tmp_path):
    rule = lint('local:variant', severity='error'); rule['program'] = condition('linux')
    data = inputs(variants(), rules=[rule]); root = tmp_path / 'project'; root.mkdir(); write_project(root, data)
    linux = live_validation(root, data); windows = live_validation(root, data, aid('configuration', 2))
    assert linux.passed and not windows.passed
    findings = windows.data['validation']['source_report']['stages']
    assert any(s['stage'] == 'profile_lint' and s['status'] == 'failed' for s in findings)
    assert windows.data['selected_configuration']['configuration_id'] == aid('configuration', 2)


def test_registered_validation_gates_receive_owned_selected_configuration_data():
    seen = []
    def check(context):
        value = context.configuration_data; seen.append(copy.deepcopy(value)); value['effective_values']['platform'] = 'changed'
        assert context.configuration_data['effective_values']['platform'] == 'linux'
        return context.result()
    gate = ModelGate('extension:configuration-observer', '1', no_dependencies, check)
    validate_configured_model(tuple(doc(v) for v in variants()), configuration_id=aid('configuration'),
                              profile=profile(), gates=(gate,))
    assert seen[0]['configuration_id'] == aid('configuration') and seen[0]['configuration_revision'] == 1


def test_query_validation_and_native_scope_do_not_attempt_project_writes(tmp_path):
    data = inputs(variants()); root = tmp_path / 'project'; root.mkdir(); write_project(root, data); before = inventory(root)
    scope = configured_scope('query', {'query': query().data})
    with no_write_attempts():
        assert query_project(root, query(), configuration_id=aid('configuration')).exit_code == 0
        assert live_validation(root, data).passed
        assert read_artifact_scope_seeds(ProjectSource(root), scope).selection.artifact_ids == (aid(), aid(number=3))
    assert inventory(root) == before


def test_live_validation_does_not_default_an_unknown_explicit_configuration(tmp_path):
    data = inputs(variants()); root = tmp_path / 'project'; root.mkdir(); write_project(root, data)
    result = live_validation(root, data, aid('configuration', 99))
    assert result.exit_code == 3 and not result.passed and result.data['validation'] is None
    assert result.data['diagnostics'][0]['code'] == 'SRV130'


def test_portable_cli_uses_real_configuration_filtering(tmp_path):
    root = project(tmp_path / 'project'); _, package = build_distribution(tmp_path / 'distribution')
    result = run_python(['-I', '-S', '-B', str(package), 'query', '--type', 'requirement',
        '--configuration', aid('configuration'), '--project', str(root), '--format=json'], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert ids(json.loads(result.stdout)['result']) == [aid(), aid(number=3)]
