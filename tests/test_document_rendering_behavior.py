"""Renderer admission and forbidden effects; no rendered output is an oracle."""
from copy import deepcopy

import pytest

from specroad.documents import (RenderError, compose_document, render_document,
                               render_view, resolve_view)
from specroad.model.errors import ModelError
from support.domain import domain_value
from support.read_only import no_write_attempts
from support.records import block_value, record_value, ref
from support.targets import model
from test_document_includes import edge, include_project
from test_document_tables import table_project
from test_document_views import view_project
from test_document_view_variants_right import nested_project


def composed_values(block, *other):
    return [record_value('document', relations=[edge('contains', ref('SEC'), 9000)]),
            record_value('section', relations=[edge('contains', block['id'], 9001)]),
            block, *other]


def render_project(kind):
    if kind == 'include':
        return include_project()
    if kind == 'query':
        block, *other = table_project()
        return composed_values(block, *other)
    mode = kind if kind in ('full', 'summary', 'link') else None
    block = block_value('artifact_ref' if mode else kind)
    if mode:
        block['payload']['render_mode'] = mode
        return composed_values(block, domain_value('requirement'))
    if kind == 'prose':
        block['payload']['markdown'] = ('*emphasis* **strong** `inert`  \nnext\n\n'
            '- item\n- second\n\n3. third\n4. fourth\n\n> quote\n\n---\n\n'
            '```python\nimport os; os.system("do-not-execute")\n```')
    return composed_values(block)


@pytest.mark.parametrize('output_format', ['markdown', 'html'])
@pytest.mark.parametrize('kind', ['prose', 'admonition', 'page_break', 'table', 'query',
                                 'full', 'summary', 'link', 'include'])
def test_document_rendering_cannot_write_execute_or_mutate_owned_sources(kind, output_format):
    supplied = model(render_project(kind))
    before = supplied.source_files
    with no_write_attempts():
        render_document(supplied, ref('DOC'), output_format=output_format)
    assert supplied.source_files == before
    assert supplied.snapshot()._sources_sha256 == supplied._sources_sha256


@pytest.mark.parametrize('output_format', ['markdown', 'html'])
@pytest.mark.parametrize('nested', [False, True])
def test_view_rendering_cannot_write_execute_or_mutate_projected_sources(nested, output_format):
    values = nested_project() if nested else view_project()
    values[-1]['formats'] = ['markdown', 'html']
    supplied = model(values)
    before = supplied.source_files
    projected_before = resolve_view(supplied, ref('VIEW')).data
    with no_write_attempts():
        render_view(supplied, ref('VIEW'), output_format=output_format)
    assert supplied.source_files == before
    assert resolve_view(supplied, ref('VIEW')).data == projected_before


@pytest.mark.parametrize('operation', [render_document, render_view])
@pytest.mark.parametrize('output_format', ['json', 'csv', '', None, [], 0])
def test_unsupported_format_is_a_structured_admission_error(operation, output_format):
    with no_write_attempts(), pytest.raises(RenderError) as caught:
        operation(None, 'unused', output_format=output_format)
    assert caught.value.diagnostic()['reason'] == 'render_format_not_supported'
    assert caught.value.pointer == '/output_format' and caught.value.exit_code == 3


@pytest.mark.parametrize('operation', [render_document, render_view])
def test_renderer_requires_the_native_owned_model(operation):
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        operation({'records': []}, 'unused')
    assert caught.value.diagnostic()['reason'] == 'document_target_model_required'


@pytest.mark.parametrize('output_format', ['markdown', 'html'])
@pytest.mark.parametrize('markdown', ['[manual](attachments/manual.pdf)',
                                    '![diagram](attachments/diagram.png)'])
def test_attachment_declaration_never_starts_implicit_file_loading(markdown, output_format):
    block = block_value('prose')
    block['payload']['markdown'] = markdown
    supplied = model(composed_values(block))
    with no_write_attempts(), pytest.raises(RenderError) as caught:
        render_document(supplied, ref('DOC'), output_format=output_format)
    assert caught.value.diagnostic()['reason'] == 'render_attachment_provider_required'
    assert caught.value.pointer == '/payload/markdown'
    assert caught.value.path.endswith('/' + ref('BLOCK') + '.json')


def test_nonempty_render_policy_is_not_treated_as_an_executable_template():
    values = render_project('prose')
    values[0]['render_policy'] = {'template': 'arbitrary-command'}
    supplied = model(values)
    with no_write_attempts(), pytest.raises(RenderError) as caught:
        render_document(supplied, ref('DOC'))
    assert caught.value.diagnostic()['reason'] == 'render_policy_provider_required'
    assert caught.value.pointer == '/render_policy'


@pytest.mark.parametrize('output_format', ['markdown', 'html'])
def test_view_format_must_be_declared_by_the_bound_view(output_format):
    values = view_project()
    values[-1]['formats'] = ['json']
    supplied = model(values)
    with no_write_attempts(), pytest.raises(RenderError) as caught:
        render_view(supplied, ref('VIEW'), output_format=output_format)
    assert caught.value.diagnostic()['reason'] == 'render_view_format_not_declared'
    assert caught.value.pointer == '/formats'


@pytest.mark.parametrize('case', ['include_cycle', 'missing_document', 'view_provider'])
def test_native_data_service_failures_propagate_without_partial_success(case):
    if case == 'view_provider':
        values = view_project()
        values[-1]['columns'][0]['format'] = 'executable-template'
        native, renderer, identifier = resolve_view, render_view, ref('VIEW')
    else:
        values = include_project()
        if case == 'include_cycle':
            values[4]['relations'][0]['target'] = ref('DOC')
        native, renderer = compose_document, render_document
        identifier = ref('DOC', '9') if case == 'missing_document' else ref('DOC')
    supplied = model(deepcopy(values))
    with no_write_attempts(), pytest.raises(ModelError) as expected:
        native(supplied, identifier)
    with no_write_attempts(), pytest.raises(type(expected.value)) as caught:
        renderer(supplied, identifier)
    assert caught.value.diagnostic() == expected.value.diagnostic()


def test_composed_table_keeps_the_native_row_width_error():
    block = block_value('table')
    block['payload']['rows'][0].append('undeclared cell')
    supplied = model(composed_values(block))
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        render_document(supplied, ref('DOC'))
    assert caught.value.diagnostic()['reason'] == 'table_row_width'
    assert caught.value.pointer == '/payload/rows/0'
