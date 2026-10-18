"""Explicit graph boundaries and inert title data, without source-text oracles."""
import builtins
import io
import os
import webbrowser

import pytest

from specroad.documents import DiagramError, render_diagram, resolve_diagram
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.srx.errors import SrxError
from support.read_only import no_write_attempts
from support.relations import aid, edge, rid
from support.targets import model
from test_document_diagrams import architecture, chain, ids, releases, relation_ids, resolve


def options():
    return dict(start_id=aid(), direction='both', max_depth=20,
                max_nodes=20, max_edges=20)


def test_explicit_nodes_are_an_admission_boundary_not_additional_traversal_roots():
    data = resolve(chain(), artifact_ids=[aid(), aid(number=3), aid(number=4)],
                   max_depth=20, max_nodes=1, max_edges=0).data
    assert ids(data) == {aid()} and relation_ids(data) == set()
    assert data['selection']['artifact_ids'] == [aid(), aid(number=3), aid(number=4)]
    assert data['selection']['eligible_ids_sha256'] == canonical_json_sha256(
        [aid(), aid(number=3), aid(number=4)])


@pytest.mark.parametrize('direction,start', [('outgoing', 1), ('incoming', 3), ('both', 2)])
def test_selected_chain_keeps_normative_directions_and_never_expands_past_boundary(direction, start):
    data = resolve(chain(), start_id=aid(number=start), direction=direction,
        artifact_ids=[aid(number=n) for n in (1, 2, 3)], relation_types=['depends_on'],
        max_depth=50, max_nodes=3, max_edges=2).data
    assert ids(data) == {aid(number=n) for n in (1, 2, 3)}
    assert relation_ids(data) == {rid(1), rid(2)}
    assert [(row['source'], row['target']) for row in data['edges']] == [
        (aid(), aid(number=2)), (aid(number=2), aid(number=3))]


@pytest.mark.parametrize('direction,start', [('outgoing', 1), ('incoming', 2), ('both', 2)])
def test_relation_filter_uses_stored_types_also_for_derived_inverse_views(direction, start):
    values = chain()
    values[0]['relations'].append(edge('supersedes', aid(number=2), number=9))
    data = resolve(values, start_id=aid(number=start), direction=direction,
        relation_types=['supersedes'], max_depth=20, max_nodes=2, max_edges=1).data
    assert ids(data) == {aid(), aid(number=2)} and relation_ids(data) == {rid(9)}
    assert data['edges'][0]['type'] == 'supersedes'
    assert data['edges'][0]['source'] == aid() and data['edges'][0]['target'] == aid(number=2)
    assert data['selection']['relation_types'] == ['supersedes']


@pytest.mark.parametrize('types', [[], (), ['references']])
def test_empty_or_nonmatching_relation_selection_never_falls_back_to_all_edges(types):
    data = resolve(chain(), relation_types=types, max_depth=20, max_nodes=1, max_edges=0).data
    assert ids(data) == {aid()} and data['edges'] == []
    assert data['selection']['relation_types'] == list(types)


def test_only_admitted_relations_count_towards_limits():
    values = chain()
    values[0]['relations'].append(edge('conflicts_with', aid(number=2), number=9))
    data = resolve(values, artifact_ids=[aid(), aid(number=2)], relation_types=['conflicts_with'],
                   direction='both', max_depth=20, max_nodes=2, max_edges=1).data
    assert ids(data) == {aid(), aid(number=2)} and relation_ids(data) == {rid(9)}


@pytest.mark.parametrize('limits,reason', [
    ({'max_nodes': 1}, 'diagram_node_limit_exceeded'),
    ({'max_edges': 0}, 'diagram_edge_limit_exceeded')])
def test_explicit_filters_do_not_weaken_count_overflow_errors(limits, reason):
    with no_write_attempts(), pytest.raises(DiagramError) as caught:
        resolve(chain(), artifact_ids=[aid(), aid(number=2)], relation_types=['depends_on'], **limits)
    assert caught.value.reason == reason and caught.value.exit_code == 3


@pytest.mark.parametrize('kind,values,start,selected,relations', [
    ('architecture', architecture(), aid('component'), [aid('component'), aid('interface')], [3]),
    ('release', releases(), aid('release'), [aid('release'), aid('milestone'), aid('task')], [1, 2])])
def test_family_scope_can_be_narrowed_without_adding_members(kind, values, start, selected, relations):
    data = resolve(values, kind, start_id=start, direction='both', artifact_ids=selected,
                   relation_types=['part_of'], max_depth=20, max_nodes=len(selected),
                   max_edges=len(relations)).data
    assert ids(data) == set(selected) and relation_ids(data) == {rid(n) for n in relations}


@pytest.mark.parametrize('kind,values,start,extra', [
    ('architecture', architecture(), aid('component'), aid()),
    ('release', releases(), aid('release'), aid('release', 2)),
    ('release', releases(), aid('release'), aid('task', 2))])
def test_explicit_ids_cannot_enlarge_the_family_scope(kind, values, start, extra):
    with no_write_attempts(), pytest.raises(DiagramError) as caught:
        resolve(values, kind, start_id=start, artifact_ids=[start, extra])
    assert caught.value.reason == 'diagram_artifact_outside_scope'
    assert caught.value.pointer == '/artifact_ids' and caught.value.exit_code == 3


@pytest.mark.parametrize('selected,reason', [
    ([aid(), aid(number=99)], 'diagram_artifact_not_found'),
    ([aid(), 'Node 2'], 'diagram_artifact_not_found'),
    ([aid(number=2)], 'diagram_start_outside_scope'),
    ([], 'diagram_start_outside_scope')])
def test_unknown_ids_and_excluded_start_are_not_silently_repaired(selected, reason):
    with no_write_attempts(), pytest.raises(DiagramError) as caught:
        resolve(chain(), artifact_ids=selected)
    assert caught.value.reason == reason and caught.value.exit_code == 3


@pytest.mark.parametrize('name,bad,reason', [
    ('artifact_ids', aid(), 'diagram_artifact_selection_invalid'),
    ('artifact_ids', {aid()}, 'diagram_artifact_selection_invalid'),
    ('artifact_ids', {}, 'diagram_artifact_selection_invalid'),
    ('artifact_ids', True, 'diagram_artifact_selection_invalid'),
    ('artifact_ids', [aid(), aid()], 'diagram_artifact_selection_invalid'),
    ('artifact_ids', [aid(), []], 'diagram_artifact_selection_invalid'),
    ('artifact_ids', [False], 'diagram_artifact_selection_invalid'),
    ('relation_types', 'depends_on', 'diagram_relation_types_invalid'),
    ('relation_types', {'depends_on'}, 'diagram_relation_types_invalid'),
    ('relation_types', {}, 'diagram_relation_types_invalid'),
    ('relation_types', [True], 'diagram_relation_types_invalid'),
    ('relation_types', [[]], 'diagram_relation_types_invalid'),
    ('relation_types', ['depends_on', 'depends_on'], 'diagram_relation_types_invalid'),
    ('relation_types', ['*'], 'diagram_relation_types_invalid'),
    ('relation_types', ['superseded_by'], 'diagram_relation_types_invalid'),
    ('relation_types', ['unknown'], 'diagram_relation_types_invalid')])
def test_selection_contract_rejects_coercions_duplicates_and_nonstored_types(name, bad, reason):
    with no_write_attempts(), pytest.raises(DiagramError) as caught:
        resolve(chain(), **{name: bad})
    assert caught.value.reason == reason and caught.value.pointer == '/' + name
    assert caught.value.exit_code == 2


def test_selection_order_and_caller_mutation_cannot_change_frozen_machine_values():
    selected = [aid(number=3), aid(), aid(number=2)]
    types = ['supersedes', 'depends_on']
    result = resolve(chain(), artifact_ids=selected, relation_types=types)
    expected = result.data
    assert resolve(chain()[::-1], artifact_ids=selected[::-1], relation_types=types[::-1]).data == expected
    assert expected['selection']['artifact_ids'] == sorted(selected)
    assert expected['selection']['relation_types'] == sorted(types)
    selected.clear(); types.clear()
    detached = result.data; detached['selection']['artifact_ids'].clear()
    assert result.data == expected and result.sha256 == canonical_json_sha256(expected)


def test_explicit_selection_binds_intent_even_when_traversed_graph_is_unchanged():
    implicit = resolve(chain()).data
    explicit = resolve(chain(), artifact_ids=[aid(number=n) for n in range(1, 5)],
                       relation_types=['depends_on']).data
    assert explicit['nodes'] == implicit['nodes'] and explicit['edges'] == implicit['edges']
    assert explicit['model_root_sha256'] == implicit['model_root_sha256']
    assert explicit['input_sha256'] == implicit['input_sha256']
    assert canonical_json_sha256(explicit) != canonical_json_sha256(implicit)


@pytest.mark.parametrize('case', ['missing_target', 'duplicate_relation', 'invalid_pair', 'noncanonical_symmetric'])
def test_empty_traversal_cannot_hide_invalid_excluded_graph(case):
    values = chain()
    if case == 'missing_target': values[-1]['relations'] = [edge('depends_on', aid(number=99), number=9)]
    elif case == 'duplicate_relation': values[-1]['relations'] = [edge('depends_on', aid(), number=1)]
    elif case == 'invalid_pair': values[-1]['relations'] = [edge('allocated_to', aid(), number=9)]
    else: values[-1]['relations'] = [edge('conflicts_with', aid(), number=9)]
    with no_write_attempts(), pytest.raises((ModelError, SrxError)):
        resolve(values, artifact_ids=[aid()], relation_types=[], max_depth=0, max_nodes=1, max_edges=0)


TITLES = [
    'Änderung 日本語 العربية 🧭',
    '"]\nclick attacker "https://example.invalid"\nattacker["payload',
    '%%{init: {"securityLevel": "loose"}}%%',
    '<img src="https://example.invalid" onerror="alert(1)"><script>run()</script>',
    '#34; &#34; &quot; `markdown` **bold** $$formula$$',
    '\\N \\G \\L \\n \\l \\r \\"; injected -> other; //',
    'First\nSecond\r\nThird\t\x01\x1b\x7f\x85',
    '{{ __import__("os").system("forbidden") }} $(forbidden) `forbidden`',
]


@pytest.mark.parametrize('output_format', ['mermaid', 'dot'])
@pytest.mark.parametrize('title', TITLES, ids=[f'title-{n}' for n in range(len(TITLES))])
def test_title_text_is_inert_and_original_values_and_ids_are_preserved(title, output_format, monkeypatch):
    values = chain(); original_ids = resolve(values).data
    values[0]['title'] = title
    supplied = model(values); before = supplied.source_files
    attempts = []
    def forbidden(*args, **kwargs):
        attempts.append((args, kwargs))
        raise AssertionError('Unexpected input discovery or browser execution')
    with no_write_attempts(), monkeypatch.context() as guard:
        for owner, name in ((builtins, 'open'), (io, 'open'), (os, 'open'),
                            (webbrowser, 'open'), (webbrowser, 'open_new'), (webbrowser, 'open_new_tab')):
            guard.setattr(owner, name, forbidden)
        data = resolve_diagram(supplied, 'trace', **options()).data
        source = render_diagram(supplied, 'trace', **options(), label_mode='title', output_format=output_format)
    assert attempts == [] and type(source) is bytes
    assert supplied.source_files == before
    assert data['nodes'][0]['title'] == title
    assert {n['artifact_id']: n['diagram_id'] for n in data['nodes'] if n['distance'] <= 2} == {
        n['artifact_id']: n['diagram_id'] for n in original_ids['nodes']}
    assert data['edges'][:2] == original_ids['edges']
    assert not any(data[k] for k in ('rendering_performed', 'full_validation_passed',
                                    'write_authorized', 'approval_granted'))


@pytest.mark.parametrize('output_format', ['mermaid', 'dot'])
@pytest.mark.parametrize('kind,values,start', [
    ('trace', chain(), aid()), ('architecture', architecture(), aid('component')),
    ('release', releases(), aid('release'))])
def test_source_api_honours_explicit_selection_without_external_rendering(kind, values, start, output_format):
    supplied = model(values)
    with no_write_attempts():
        source = render_diagram(supplied, kind, start_id=start, direction='both', max_depth=20,
            max_nodes=1, max_edges=0, artifact_ids=[start], relation_types=[],
            output_format=output_format, label_mode='title')
    assert type(source) is bytes


@pytest.mark.parametrize('output_format', ['mermaid', 'dot'])
@pytest.mark.parametrize('bad', ['html', 'markdown', '', None, [], True])
def test_unknown_label_policy_does_not_run_a_template_or_renderer(output_format, bad):
    with no_write_attempts(), pytest.raises(DiagramError) as caught:
        render_diagram(model(chain()), 'trace', **options(), output_format=output_format, label_mode=bad)
    assert caught.value.reason == 'diagram_label_mode_not_supported'
    assert caught.value.pointer == '/label_mode' and caught.value.exit_code == 2


@pytest.mark.parametrize('output_format', ['mermaid', 'dot'])
def test_source_api_rejects_an_invalid_selection_instead_of_falling_back(output_format):
    with no_write_attempts(), pytest.raises(DiagramError) as caught:
        render_diagram(model(chain()), 'trace', **options(), output_format=output_format,
                       label_mode='title', relation_types=['superseded_by'])
    assert caught.value.reason == 'diagram_relation_types_invalid'
