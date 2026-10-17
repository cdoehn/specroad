"""Stable view ordering and real same-snapshot configuration/graph selection."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from specroad.changes import TargetModel
from specroad.configurations import resolve_configuration
from specroad.documents import ViewError, resolve_view
from specroad.graph.relations import SourceRelations
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.model.errors import ModelError
from specroad.query import NormalizedQuery, query_records
from specroad.validation import ModelDocument
from support.read_only import no_write_attempts
from support.records import record_value, ref
from support.srx import binary, expression_document, field, literal
from support.targets import model, SCOPE
from test_document_views import view_project, row_for, aid


def variant_project(platform='linux', *, declared=True):
    values = view_project(); cfg = record_value('configuration', selection={'platform': platform})
    values[1]['applicability'] = expression_document(binary('eq',
        field('/effective_values/platform', 'configuration'), literal('windows')))
    if declared: values[-1]['scope_descriptor']['configuration_id'] = cfg['id']
    return [*values, cfg]


@pytest.mark.parametrize('declared', [False, True])
@pytest.mark.parametrize(('platform', 'selected', 'targets'), [('linux', [4, 3, 1], []), ('windows', [4, 2, 3, 1], [2, 3])])
def test_declared_and_explicit_configuration_bind_the_same_native_rows_and_graph(declared, platform, selected, targets):
    values = variant_project(platform, declared=declared); supplied = model(values); before = supplied.source_files
    kwargs = {} if declared else {'configuration_id': ref('CFG')}
    with no_write_attempts(): resolved = resolve_view(supplied, ref('VIEW'), **kwargs)
    data = resolved.data
    assert [row['artifact_id'] for row in data['rows']] == [aid(number=n) for n in selected]
    assert row_for(data)['relation_projections'] == {'ids': [aid(number=n) for n in targets], 'count': len(targets)}
    records = [SourceRelations(d.content, path=d.path) for d in supplied.documents]
    configuration = resolve_configuration(records, ref('CFG'))
    page = query_records(records, NormalizedQuery.from_data(data['query_binding']['query']),
                         project=supplied.configuration.data, configuration_id=ref('CFG'))
    assert data['query_result'] == page.data
    assert data['query_binding']['configuration_binding'] == configuration.binding == page.configuration_binding
    assert data['query_binding']['inputs_sha256'] == page.inputs_sha256
    selected_scope = {**SCOPE, 'configuration_id': ref('CFG')}
    assert data['selection_scope_descriptor'] == selected_scope
    assert data['selection_scope_descriptor_sha256'] == ScopeDescriptor(selected_scope).sha256
    assert data['view']['scope_descriptor'] == values[-2]['scope_descriptor']
    assert data['scope_descriptor'] == SCOPE
    assert data['model_root_sha256'] == supplied.manifest(supplied.artifacts, SCOPE).sha256
    assert supplied.source_files == before


@pytest.mark.parametrize('direction', ['asc', 'desc'])
@pytest.mark.parametrize('rotation', range(6))
def test_equal_sort_keys_always_use_ascending_id_ties_within_the_selected_variant(direction, rotation):
    values = variant_project('windows'); values[-2]['sort'] = [{'key': 'title', 'direction': direction}]
    for artifact in values[:4]: artifact['title'] = 'é' if artifact['revision'] % 2 else 'e\u0301'
    expected = resolve_view(model(values), ref('VIEW')).data
    assert [row['artifact_id'] for row in expected['rows']] == [aid(number=n) for n in range(1, 5)]
    rotated = values[rotation:] + values[:rotation]
    assert resolve_view(model(rotated), ref('VIEW')).data == expected


def test_explicit_id_sort_direction_is_respected_instead_of_replaced_by_default_ties():
    values = variant_project('windows'); values[-2]['sort'] = [{'key': 'id', 'direction': 'desc'}]
    data = resolve_view(model(values), ref('VIEW')).data
    assert [row['artifact_id'] for row in data['rows']] == [aid(number=n) for n in (4, 3, 2, 1)]


@pytest.mark.parametrize('platform', ['linux', 'windows'])
def test_filtered_out_applicable_nodes_remain_available_but_excluded_nodes_block_traversal(platform):
    values = variant_project(platform); values[-2]['filter'] = expression_document(binary('eq', field('/id'), literal(aid(number=1))))
    data = resolve_view(model(values), ref('VIEW')).data
    assert [row['artifact_id'] for row in data['rows']] == [aid(number=1)]
    assert row_for(data)['relation_projections']['ids'] == ([] if platform == 'linux' else [aid(number=2), aid(number=3)])


@pytest.mark.parametrize('platform', ['linux', 'windows'])
def test_srx_graph_filter_and_relation_projection_use_the_same_configured_graph(platform):
    values = variant_project(platform); view = values[-2]
    view['filter']['expression'] = {'op': 'and', 'args': [view['filter']['expression'],
        {'op': 'has_relation', 'direction': 'outgoing', 'types': ['depends_on']}]}
    data = resolve_view(model(values), ref('VIEW')).data
    assert [row['artifact_id'] for row in data['rows']] == ([aid(number=3)] if platform == 'linux' else [aid(number=n) for n in (2, 3, 1)])
    assert all(row['relation_projections']['count'] > 0 for row in data['rows'])


def test_no_configuration_keeps_potential_variants_without_inventing_a_default():
    values = variant_project(declared=False); supplied = model(values)
    data = resolve_view(supplied, ref('VIEW')).data
    assert data['query_binding']['configuration_binding'] is None
    assert data['selection_scope_descriptor']['configuration_id'] is None
    assert [row['artifact_id'] for row in data['rows']] == [aid(number=n) for n in (4, 2, 3, 1)]
    assert row_for(data)['relation_projections']['ids'] == [aid(number=2), aid(number=3)]


def test_parent_selection_and_revision_are_bound_without_rewriting_view_or_row_sources():
    values = variant_project(); parent = deepcopy(values[-1]); parent['id'] = ref('CFG', '1'); parent['name'] = 'Parent variant'
    values[-1].update(parent=parent['id'], selection={}); values.append(parent)
    first = resolve_view(model(values), ref('VIEW')); before = first.data
    values[-1]['selection']['platform'] = 'windows'; values[-1]['revision'] += 1
    second = resolve_view(model(values), ref('VIEW'))
    assert first.view_source_bytes == second.view_source_bytes
    assert before['query_binding']['configuration_binding'] != second.data['query_binding']['configuration_binding']
    assert before['input_sha256'] != second.data['input_sha256']
    assert before['model_root_sha256'] != second.data['model_root_sha256']
    assert before['row_count'] == 3 and second.data['row_count'] == 4
    assert row_for(before)['source_sha256'] == row_for(second.data)['source_sha256']
    assert first.data == before


def test_configuration_byte_formatting_rebinds_inputs_without_changing_canonical_selection():
    supplied = model(variant_project()); first = resolve_view(supplied, ref('VIEW'))
    original = next(d for d in supplied.documents if json.loads(d.content)['id'] == ref('CFG'))
    raw = (json.dumps(json.loads(original.content), indent=3) + '\n').encode()
    documents = [ModelDocument(d.path, raw if d.path == original.path else d.content) for d in supplied.documents]
    changed = TargetModel(supplied.configuration_bytes, supplied.binding, documents,
                          profile=supplied.profile, resource_files=supplied.resource_files)
    second = resolve_view(changed, ref('VIEW'))
    assert first.data['rows'] == second.data['rows'] and first.data['groups'] == second.data['groups']
    assert first.data['model_root_sha256'] == second.data['model_root_sha256']
    assert first.data['input_sha256'] != second.data['input_sha256']
    assert first.data['query_binding']['inputs_sha256'] != second.data['query_binding']['inputs_sha256']
    assert first.data['query_binding']['configuration_binding'] == second.data['query_binding']['configuration_binding']
    assert changed.source_files[original.path] == raw and sha256(raw).hexdigest() != sha256(original.content).hexdigest()


def test_conflicting_explicit_and_declared_configuration_is_not_silently_overridden():
    values = variant_project(); extra = deepcopy(values[-1]); extra['id'] = ref('CFG', '1'); extra['name'] = 'Alternate variant'; values.append(extra)
    supplied = model(values); before = supplied.source_files
    with no_write_attempts(), pytest.raises(ViewError) as caught:
        resolve_view(supplied, ref('VIEW'), configuration_id=extra['id'])
    assert caught.value.reason == 'view_configuration_conflict'
    assert supplied.source_files == before


@pytest.mark.parametrize('case', ['missing', 'missing_parent', 'bad_value', 'invalid_applicability'])
def test_missing_or_invalid_configuration_inputs_never_produce_partial_view_success(case):
    values = variant_project()
    if case == 'missing': values.pop()
    elif case == 'missing_parent': values[-1]['parent'] = ref('CFG', '1')
    elif case == 'bad_value': values[-1]['selection']['platform'] = 'undeclared'
    else: values[1]['applicability'] = expression_document(literal('not boolean'))
    supplied = model(values); before = supplied.source_files
    with no_write_attempts(), pytest.raises(ModelError): resolve_view(supplied, ref('VIEW'))
    assert supplied.source_files == before
