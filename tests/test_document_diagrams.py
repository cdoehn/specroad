"""Native graph identities, source bindings and effects, never diagram layout."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.changes import TargetModel
from specroad.documents import DiagramData, DiagramError, render_diagram, resolve_diagram
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.srx.errors import SrxError
from specroad.validation import ModelDocument
from support.domain import domain_value
from support.read_only import no_write_attempts
from support.relations import aid, edge, rid
from support.targets import model, SCOPE


def chain():
    return [domain_value('requirement', id=aid(number=n), title='Node ' + str(n),
        relations=[edge('depends_on', aid(number=n + 1), number=n)] if n < 4 else [])
        for n in range(1, 5)]


def resolve(values, kind='trace', **options):
    selected = {'start_id': aid(number=1), 'direction': 'outgoing', 'max_depth': 2,
                'max_nodes': 20, 'max_edges': 20, **options}
    return resolve_diagram(model(values), kind, **selected)


def ids(data):
    return {node['artifact_id'] for node in data['nodes']}


def relation_ids(data):
    return {edge['relation_id'] for edge in data['edges']}


@pytest.mark.parametrize('direction,depth,numbers,relations', [
    ('incoming', 0, [2], []), ('outgoing', 0, [2], []), ('both', 0, [2], []),
    ('incoming', 1, [1, 2], [1]), ('outgoing', 1, [2, 3], [2]), ('both', 1, [1, 2, 3], [1, 2]),
    ('incoming', 2, [1, 2], [1]), ('outgoing', 2, [2, 3, 4], [2, 3]),
    ('both', 2, [1, 2, 3, 4], [1, 2, 3])])
def test_trace_keeps_exact_selected_nodes_and_stored_edges(direction, depth, numbers, relations):
    data = resolve(chain(), start_id=aid(number=2), direction=direction, max_depth=depth).data
    assert ids(data) == {aid(number=n) for n in numbers}
    assert relation_ids(data) == {rid(n) for n in relations}
    assert data['node_count'] == len(numbers) and data['edge_count'] == len(relations)
    for stored in data['edges']:
        n = next(n for n in relations if rid(n) == stored['relation_id'])
        assert (stored['source'], stored['target']) == (aid(number=n), aid(number=n + 1))
        assert stored['type'] == 'depends_on'
        assert stored['stored_relation'] == edge('depends_on', aid(number=n + 1), number=n)
        assert stored['relation_sha256'] == canonical_json_sha256(stored['stored_relation'])


def test_graph_values_bind_owned_bytes_and_do_not_claim_validation_or_approval():
    supplied = model(chain()); before = supplied.source_files
    with no_write_attempts():
        result = resolve_diagram(supplied, 'trace', start_id=aid(), direction='both',
                                 max_depth=2, max_nodes=3, max_edges=2)
    data = result.data
    assert data['model_root_sha256'] == supplied.manifest(supplied.artifacts, SCOPE).sha256
    assert data['input_sha256'] == supplied._sources_sha256
    assert data['generated'] and data['normative'] is False
    assert data['validation_scope'] == 'supplied_snapshot_relation_projection'
    assert data['selection'] == {'start_id': aid(), 'direction': 'both', 'max_depth': 2,
        'max_nodes': 3, 'max_edges': 2, 'scope': {'kind': 'supplied_project_relations'},
        'eligible_ids_sha256': canonical_json_sha256([aid(number=n) for n in range(1, 5)])}
    assert not any(data[k] for k in ('project_files_verified', 'full_validation_passed',
                                    'rendering_performed', 'write_authorized', 'approval_granted'))
    for node in data['nodes']:
        document = next(d for d in supplied.documents if json.loads(d.content)['id'] == node['artifact_id'])
        value = json.loads(document.content)
        assert node['title'] == value['title'] and node['revision'] == value['revision']
        assert node['source_sha256'] == sha256(document.content).hexdigest()
        assert node['record_sha256'] == canonical_json_sha256(value)
    assert supplied.source_files == before
    assert result.sha256 == canonical_json_sha256(data)


def test_cycles_parallel_relations_and_inverse_views_keep_one_normative_identity_each():
    values = chain()[:3]; values[-1]['relations'] = [edge('depends_on', aid(), number=3)]
    values[0]['relations'].append(edge('conflicts_with', aid(number=2), number=9))
    data = resolve(values, direction='both', max_depth=1000, max_nodes=3, max_edges=4).data
    assert ids(data) == {aid(number=n) for n in (1, 2, 3)}
    assert relation_ids(data) == {rid(n) for n in (1, 2, 3, 9)}
    assert len({row['diagram_id'] for row in data['nodes']}) == 3
    assert len({row['diagram_id'] for row in data['edges']}) == 4
    assert {n['artifact_id']: n['distance'] for n in data['nodes']} == {
        aid(): 0, aid(number=2): 1, aid(number=3): 1}


def architecture():
    return [
        domain_value('component', id=aid('component', 1), relations=[
            edge('depends_on', aid('component', 2), number=1),
            edge('depends_on', aid(number=1), number=2)]),
        domain_value('component', id=aid('component', 2)),
        domain_value('interface', id=aid('interface'), source_component=aid('component', 1),
            target_component=aid('component', 2), relations=[
                edge('part_of', aid('component', 1), number=3)]),
        domain_value('requirement', id=aid(), relations=[
            edge('allocated_to', aid('component', 2), number=4)])]


def test_architecture_uses_component_interface_scope_without_invented_field_edges():
    data = resolve(architecture(), 'architecture', start_id=aid('component'),
                   direction='both', max_depth=3).data
    assert ids(data) == {aid('component', 1), aid('component', 2), aid('interface')}
    assert relation_ids(data) == {rid(1), rid(3)}
    assert {row['artifact_type'] for row in data['nodes']} == {'component', 'interface'}
    assert data['selection']['scope'] == {'kind': 'architecture_relations'}


def releases():
    return [domain_value('release', id=aid('release', n)) for n in (1, 2)] + [
        domain_value('milestone', id=aid('milestone'), relations=[
            edge('part_of', aid('release', 1), number=1)]),
        domain_value('task', id=aid('task', 1), relations=[
            edge('part_of', aid('milestone'), number=2),
            edge('depends_on', aid('task', 2), number=3)]),
        domain_value('requirement', id=aid(), relations=[
            edge('scheduled_for', aid('release', 1), number=4)]),
        domain_value('task', id=aid('task', 2), relations=[
            edge('scheduled_for', aid('release', 2), number=5)])]


@pytest.mark.parametrize('depth,expected_nodes,expected_edges', [
    (0, [('release', 1)], []),
    (1, [('release', 1), ('milestone', 1), ('requirement', 1)], [1, 4]),
    (2, [('release', 1), ('milestone', 1), ('requirement', 1), ('task', 1)], [1, 2, 4]),
    (20, [('release', 1), ('milestone', 1), ('requirement', 1), ('task', 1)], [1, 2, 4])])
def test_release_uses_native_membership_without_expanding_into_other_releases(depth, expected_nodes, expected_edges):
    data = resolve(releases(), 'release', start_id=aid('release'), direction='both', max_depth=depth).data
    assert ids(data) == {aid(kind, number) for kind, number in expected_nodes}
    assert relation_ids(data) == {rid(n) for n in expected_edges}
    scope = data['selection']['scope']
    assert scope['kind'] == 'release_seed_relations'
    assert scope['descriptor']['selector'] == {'release_id': aid('release')}


@pytest.mark.parametrize('rotation', range(4))
def test_source_order_cannot_change_projection_membership_order_or_binding(rotation):
    values = chain(); expected = resolve(values).data
    assert resolve(values[rotation:] + values[:rotation]).data == expected
    assert [n['artifact_id'] for n in expected['nodes']] == sorted(ids(expected))
    assert [e['relation_id'] for e in expected['edges']] == sorted(relation_ids(expected))


def test_titles_and_revision_changes_preserve_ids_and_rebind_values():
    values = chain(); before = resolve(values).data
    values[1].update(title='Other title', revision=2)
    after = resolve(values).data
    assert [n['diagram_id'] for n in before['nodes']] == [n['diagram_id'] for n in after['nodes']]
    assert [e['diagram_id'] for e in before['edges']] == [e['diagram_id'] for e in after['edges']]
    assert before['model_root_sha256'] != after['model_root_sha256']
    assert before['input_sha256'] != after['input_sha256']
    assert next(n for n in after['nodes'] if n['artifact_id'] == aid(number=2))['title'] == 'Other title'


def test_original_byte_change_rebinds_source_without_changing_semantic_graph():
    supplied = model(chain()); options = dict(start_id=aid(), direction='outgoing', max_depth=1,
                                           max_nodes=2, max_edges=1)
    before = resolve_diagram(supplied, 'trace', **options).data
    changed = TargetModel(supplied.configuration_bytes, supplied.binding,
        [ModelDocument(d.path, (json.dumps(json.loads(d.content), indent=3) + '\n').encode())
         for d in supplied.documents], profile=supplied.profile, resource_files=supplied.resource_files)
    after = resolve_diagram(changed, 'trace', **options).data
    assert ids(before) == ids(after) and before['edges'] == after['edges']
    assert before['model_root_sha256'] == after['model_root_sha256']
    assert before['input_sha256'] != after['input_sha256']
    assert before['nodes'][0]['record_sha256'] == after['nodes'][0]['record_sha256']
    assert before['nodes'][0]['source_sha256'] != after['nodes'][0]['source_sha256']


def test_machine_result_is_detached_and_cannot_be_used_as_an_approval_boolean():
    resolved = resolve(chain()); expected = resolved.data
    changed = resolved.data; changed['nodes'].clear(); changed['edges'][0]['stored_relation'].clear()
    assert resolved.data == expected
    with pytest.raises(TypeError): bool(resolved)
    with pytest.raises(TypeError): DiagramData()
    with pytest.raises(FrozenInstanceError): resolved._encoded = b'{}'


@pytest.mark.parametrize('options,reason,pointer', [
    ({'start_id': None}, 'diagram_start_id_required', '/start_id'),
    ({'start_id': aid(number=99)}, 'diagram_start_not_found', '/start_id'),
    ({'start_id': 'Node 1'}, 'diagram_start_not_found', '/start_id'),
    ({'direction': 'reverse'}, 'diagram_direction_required', '/direction'),
    ({'direction': None}, 'diagram_direction_required', '/direction'),
    ({'max_depth': -1}, 'diagram_limit_required', '/max_depth'),
    ({'max_depth': True}, 'diagram_limit_required', '/max_depth'),
    ({'max_depth': 1.0}, 'diagram_limit_required', '/max_depth'),
    ({'max_nodes': 0}, 'diagram_limit_required', '/max_nodes'),
    ({'max_nodes': True}, 'diagram_limit_required', '/max_nodes'),
    ({'max_nodes': '2'}, 'diagram_limit_required', '/max_nodes'),
    ({'max_edges': -1}, 'diagram_limit_required', '/max_edges'),
    ({'max_edges': False}, 'diagram_limit_required', '/max_edges'),
    ({'max_edges': None}, 'diagram_limit_required', '/max_edges')])
def test_invalid_selection_never_returns_a_partial_success(options, reason, pointer):
    with no_write_attempts(), pytest.raises(DiagramError) as caught:
        resolve(chain(), **options)
    assert caught.value.reason == reason and caught.value.pointer == pointer


@pytest.mark.parametrize('options,reason', [
    ({'max_nodes': 2}, 'diagram_node_limit_exceeded'),
    ({'max_edges': 1}, 'diagram_edge_limit_exceeded'),
    ({'max_edges': 0}, 'diagram_edge_limit_exceeded')])
def test_count_overflow_fails_instead_of_claiming_a_truncated_graph(options, reason):
    with no_write_attempts(), pytest.raises(DiagramError) as caught: resolve(chain(), **options)
    assert caught.value.reason == reason


def test_zero_depth_needs_only_one_node_and_zero_edges_even_with_outgoing_relations():
    data = resolve(chain(), max_depth=0, max_nodes=1, max_edges=0).data
    assert ids(data) == {aid()} and data['edges'] == []


@pytest.mark.parametrize('kind', ['', None, [], 'component'])
def test_unknown_diagram_kind_is_a_usage_error(kind):
    with pytest.raises(DiagramError) as caught: resolve(chain(), kind)
    assert caught.value.reason == 'diagram_kind_not_supported' and caught.value.exit_code == 2


@pytest.mark.parametrize('kind,reason', [('architecture', 'diagram_start_outside_scope'),
                                       ('release', 'diagram_release_start_required')])
def test_kind_specific_roots_are_not_guessed_from_titles(kind, reason):
    with pytest.raises(DiagramError) as caught: resolve(chain(), kind)
    assert caught.value.reason == reason


@pytest.mark.parametrize('case', ['missing_target', 'duplicate_relation', 'invalid_pair', 'noncanonical_symmetric'])
def test_invalid_unvisited_graph_prevents_a_successful_diagram(case):
    values = chain()
    if case == 'missing_target': values[-1]['relations'] = [edge('depends_on', aid(number=99), number=9)]
    elif case == 'duplicate_relation': values[-1]['relations'] = [edge('depends_on', aid(), number=1)]
    elif case == 'invalid_pair': values[-1]['relations'] = [edge('allocated_to', aid(), number=9)]
    else: values[-1]['relations'] = [edge('conflicts_with', aid(), number=9)]
    with no_write_attempts(), pytest.raises((ModelError, SrxError)):
        resolve(values, max_depth=0)


@pytest.mark.parametrize('output_format', ['mermaid', 'dot'])
@pytest.mark.parametrize('kind', ['trace', 'architecture', 'release'])
def test_source_generation_has_no_file_process_or_network_effects(kind, output_format):
    values, start = ((chain(), aid()) if kind == 'trace' else
                     (architecture(), aid('component')) if kind == 'architecture' else
                     (releases(), aid('release')))
    supplied = model(values); before = supplied.source_files
    with no_write_attempts():
        source = render_diagram(supplied, kind, start_id=start, direction='both',
            max_depth=2, max_nodes=20, max_edges=20, output_format=output_format)
    assert type(source) is bytes
    assert supplied.source_files == before


@pytest.mark.parametrize('output_format', ['html', 'svg', 'png', '', None, []])
def test_no_implicit_external_renderer_for_unsupported_formats(output_format):
    with no_write_attempts(), pytest.raises(DiagramError) as caught:
        render_diagram(model(chain()), 'trace', start_id=aid(), direction='both',
            max_depth=2, max_nodes=20, max_edges=20, output_format=output_format)
    assert caught.value.reason == 'diagram_format_not_supported' and caught.value.exit_code == 2


@pytest.mark.parametrize('supplied', [None, {}, [], 'project/path'])
def test_caller_containers_and_paths_cannot_replace_the_owned_model(supplied):
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_diagram(supplied, 'trace', start_id=aid(), direction='both',
                        max_depth=2, max_nodes=20, max_edges=20)
    assert caught.value.reason == 'document_target_model_required'
