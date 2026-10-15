"""Cross-adapter configuration bindings, source ownership and final currentness."""
from concurrent.futures import ThreadPoolExecutor
import json
from unittest.mock import patch

import pytest

from specroad.cli.application import dispatch_result
from specroad.configurations import resolve_configuration
from specroad.configurations.evaluation import ConfigurationEvaluationError
from specroad.graph.closure_inputs import ClosureBindings, artifact_node
from specroad.graph.relations import SourceRelations
from specroad.graph.scope_closure import resolve_scope_closure
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_hash import fingerprint_scope
from specroad.graph.scope_inputs import ScopeSeedInputs
from specroad.graph.scope_query_page import QuerySeedPage
from specroad.graph.scope_seeds import resolve_scope_seeds
from specroad.model.configuration import ProjectConfiguration
from specroad.model.errors import ModelError
from specroad.model.model_manifest import ProjectReadBinding
from specroad.model.paths import artifact_path
from specroad.query import NormalizedQuery, QueryWork, query_project, query_records
from specroad.security import ProjectBoundary
from specroad.srx import EvaluationContext
from specroad.storage.project import ProjectSource
from specroad.storage.read_only import validate_project_read_only
from specroad.storage.scope_seeds import read_artifact_scope_seeds
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.model import configuration_value
from support.portable import build_distribution
from support.processes import run_python
from support.production_validation import inputs, write_project
from support.read_only import make_project
from support.records import record_value
from support.relations import aid
from support.scopes import descriptor
from support.srx import binary, expression_document, field, literal


def configuration(number=1, **changes):
    return record_value('configuration', id=aid('configuration', number), name='Variant ' + str(number), **changes)


def values():
    condition = expression_document(binary('eq', field('/effective_values/platform', 'configuration'), literal('linux')))
    return [configuration(), configuration(2, parent=aid('configuration'), dimensions=[], selection={'platform': 'windows'}),
        domain_value('requirement', id=aid(), language='en', title='Z'),
        domain_value('requirement', id=aid(number=2), language='en', title='A', applicability=condition)]


def records(items):
    return tuple(SourceRelations(artifact_bytes(value), path=value['id'] + '.json') for value in items)


def query(**kwargs):
    return NormalizedQuery(filters={'type': ['requirement']}, **kwargs)


def page_ids(page):
    return [item['id'] for item in page['items']]


def project(root, items=None):
    root.mkdir(); return make_project(root, *(values() if items is None else items))


def validation(root, data, selected):
    return validate_project_read_only(root, profile_resources=data.profiles, core_key=data.profiles[0].key,
        profile_paths={p.key: 'profiles/' + p.profile_id + '.json' for p in data.profiles}, configuration_id=selected)


def query_scope(request, selected, wrapper=False):
    base = descriptor('query', {'query': request.data})
    return ScopeDescriptor(descriptor('configuration', {'base_scope_descriptor': base}, configuration_id=selected)
        if wrapper else {**base, 'configuration_id': selected})


@pytest.mark.parametrize('selected', [aid('configuration'), aid('configuration', 2)])
def test_native_adapters_publish_the_same_project_and_parent_chain_binding(tmp_path, selected):
    data = inputs(values()); root = tmp_path / 'project'; root.mkdir(); write_project(root, data)
    request = query(); queried = query_project(root, request, configuration_id=selected)
    validated = validation(root, data, selected)
    scope = read_artifact_scope_seeds(ProjectSource(root), query_scope(request, selected))
    expected = resolve_configuration(records(values()), selected).scope_sha256(ProjectConfiguration(data.configuration))
    assert queried.exit_code == 0 and validated.passed
    assert queried.details['configuration_scope_sha256'] == validated.data['configuration_scope_sha256'] == scope.selection.configuration_sha256 == expected
    assert queried.as_dict()['summary']['selected_configuration'] == validated.data['selected_configuration']


@pytest.mark.parametrize('wrapper', [False, True])
def test_query_and_native_seed_adapters_produce_the_same_real_scope_root(tmp_path, wrapper):
    root = project(tmp_path / 'project'); source = ProjectSource(root); request = query(sort=['title'], limit=1)
    scope = query_scope(request, aid('configuration'), wrapper)
    native = read_artifact_scope_seeds(source, scope)
    observed = query_project(root, request, configuration_id=aid('configuration'))
    inventory = ScopeSeedInputs(source.configuration, records(values()))
    # This fixture has no resource uses, relations, reviews or attachments.
    # Real resource-complete operations must obtain these observations from providers.
    dependencies = ClosureBindings(inventory, uses={artifact_node(r.identity.id): () for r in inventory.records}, current_reviews={})
    page = QuerySeedPage(scope, inventory, page_ids(observed.as_dict()['result']), total=observed.result['total'])
    direct = resolve_scope_seeds(scope, inventory, query_page=page)
    binding = ProjectReadBinding(source.configuration.project_id, '/test-only/explicit', (1, 2))
    roots = [fingerprint_scope(source.configuration, binding,
        resolve_scope_closure(seeds, dependencies, query_page=page), dependencies, effective_profile={}, query_page=page)
        for seeds in (native.selection, direct)]
    assert roots[0].canonical_bytes == roots[1].canonical_bytes
    assert roots[0].scope_sha256 == roots[1].scope_sha256
    assert native.selection.artifact_ids == (aid(number=2),)


@pytest.mark.parametrize('change', ['parent_revision', 'parent_choice', 'project_semantics', 'selected_identity'])
def test_semantic_configuration_binding_changes_with_each_normative_input(change):
    items = values(); project_data = configuration_value(); selected = aid('configuration', 2)
    before = resolve_configuration(records(items), selected).scope_sha256(ProjectConfiguration(project_data))
    if change == 'parent_revision': items[0]['revision'] += 1
    elif change == 'parent_choice': items[0]['selection'] = {'platform': 'windows'}
    elif change == 'project_semantics': project_data['resource_limits'] = {'query_default_limit': 7}
    else: selected = aid('configuration')
    assert resolve_configuration(records(items), selected).scope_sha256(ProjectConfiguration(project_data)) != before


def test_semantic_binding_ignores_source_formatting_and_project_presentation():
    items = values(); first = resolve_configuration(records(items), aid('configuration', 2))
    second = resolve_configuration(tuple(SourceRelations(json.dumps(v, indent=4).encode()) for v in items), aid('configuration', 2))
    base = configuration_value(); shown = {**base, 'default_locale': 'de', 'generated_path': 'other-output'}
    assert first.scope_sha256(ProjectConfiguration(base)) == second.scope_sha256(ProjectConfiguration(shown))


def test_owned_srx_context_and_binding_do_not_expose_mutable_selected_values():
    effective = resolve_configuration(records(values()), aid('configuration'))
    context = effective.srx_context; context['effective_values']['platform'] = 'changed'
    binding = effective.binding; binding['sha256'] = '0' * 64
    assert effective.srx_context['effective_values']['platform'] == 'linux'
    assert effective.binding['sha256'] == effective.sha256 != binding['sha256']
    assert EvaluationContext({'artifact': {}, 'project': {}, 'configuration': effective.srx_context, 'relations': []}, rule_id='adapter').data['configuration'] == effective.srx_context


@pytest.mark.parametrize('project_value', [None, {}, 'project'])
def test_scope_binding_requires_real_project_configuration(project_value):
    with pytest.raises(ModelError) as caught:
        resolve_configuration(records(values()), aid('configuration')).scope_sha256(project_value)
    assert caught.value.reason == 'project_configuration_required'


@pytest.mark.parametrize('spooled', [False, True])
def test_configured_sort_uses_owned_source_identity_instead_of_forged_cached_identity(tmp_path, spooled):
    supplied = records(values()); request = query(sort=['title'], limit=1)
    expected = query_records(supplied, request, project={}, configuration_id=aid('configuration'))
    object.__setattr__(supplied[2], 'identity', supplied[3].identity)
    if spooled:
        root = project(tmp_path / 'project')
        with QueryWork(tmp_path / 'spool', supplied, request, project={}, configuration_id=aid('configuration'),
                       protected_roots=(ProjectBoundary(root),), batch_bytes=1) as work:
            while not work.advance(1)['complete']: pass
            actual = work.result
    else: actual = query_records(supplied, request, project={}, configuration_id=aid('configuration'))
    assert actual.data == expected.data and page_ids(actual.data) == [aid(number=2)]
    assert actual.inputs_sha256 == expected.inputs_sha256


@pytest.mark.parametrize('bad', [None, {}, 'record'])
def test_configured_paging_rejects_non_sources_as_bound_configuration_errors(bad):
    with pytest.raises(ConfigurationEvaluationError) as caught:
        query_records([bad], query(), project={}, configuration_id=aid('configuration'))
    assert caught.value.reason == 'configuration_source_required' and caught.value.code == 'SRV130'


@pytest.mark.parametrize('selected', ['', True, 1, 'Variant 1', aid('configuration', 99)])
def test_native_query_and_validation_do_not_invent_a_default_for_bad_selection(tmp_path, selected):
    data = inputs(values()); root = tmp_path / 'project'; root.mkdir(); write_project(root, data)
    queried = query_project(root, query(), configuration_id=selected); validated = validation(root, data, selected)
    assert queried.exit_code == validated.exit_code == 3
    assert queried.result is None and validated.data['validation'] is None
    assert queried.diagnostics[0].code == validated.data['diagnostics'][0]['code'] == 'SRV130'


def test_native_validation_checks_current_configuration_bytes_after_semantic_evaluation(tmp_path):
    import specroad.configurations as module
    data = inputs(values()); root = tmp_path / 'project'; root.mkdir(); write_project(root, data)
    original = module.validate_configured_model
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        path = root / artifact_path('configuration', aid('configuration'), 'SR')
        value = json.loads(path.read_bytes()); value['revision'] += 1; path.write_bytes(artifact_bytes(value))
        return result
    with patch.object(module, 'validate_configured_model', side_effect=changed):
        result = validation(root, data, aid('configuration'))
    assert result.exit_code == 5 and not result.passed and not result.data['freshness_verified']
    assert result.data['validation'] is None and 'configuration_scope_sha256' not in result.data


def test_omitted_configuration_keeps_the_existing_unconfigured_metadata_contract(tmp_path):
    data = inputs(values()); root = tmp_path / 'project'; root.mkdir(); write_project(root, data)
    queried = query_project(root, query()); validated = validation(root, data, None)
    for metadata in (queried.details, validated.data):
        assert 'configuration_scope_sha256' not in metadata and 'selected_configuration' not in metadata
    assert page_ids(queried.as_dict()['result']) == [aid(), aid(number=2)]


def test_cli_repeated_selection_is_usage_error_without_a_result(tmp_path):
    root = project(tmp_path / 'project')
    result = dispatch_result(['query', '--configuration', aid('configuration'), '--configuration', aid('configuration', 2),
                              '--project', str(root)])
    assert result.exit_code == 2 and result.result is None


def test_simultaneous_selected_queries_keep_distinct_owned_configuration_bindings(tmp_path):
    root = project(tmp_path / 'project')
    def evaluate(number): return query_project(root, query(), configuration_id=aid('configuration', number))
    with ThreadPoolExecutor(max_workers=2) as pool: first, second = list(pool.map(evaluate, (1, 2)))
    assert first.exit_code == second.exit_code == 0
    assert page_ids(first.as_dict()['result']) == [aid(), aid(number=2)]
    assert page_ids(second.as_dict()['result']) == [aid()]
    assert first.details['configuration_scope_sha256'] != second.details['configuration_scope_sha256']


def test_portable_cli_publishes_the_same_semantic_configuration_binding(tmp_path):
    root = project(tmp_path / 'project'); _, package = build_distribution(tmp_path / 'distribution')
    result = run_python(['-I', '-S', '-B', str(package), 'query', '--configuration', aid('configuration'),
        '--project', str(root), '--format=json'], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    expected = resolve_configuration(records(values()), aid('configuration')).scope_sha256(ProjectSource(root).configuration)
    assert json.loads(result.stdout)['summary']['configuration_scope_sha256'] == expected
