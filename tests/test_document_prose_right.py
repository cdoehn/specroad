"""Container, syntax and security boundaries of the inert prose data API."""
import builtins
from pathlib import Path
import json

import pytest

from specroad.documents import ContentBlock, ProseError, parse_prose
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from test_document_prose import prose, text, paragraph


def quote(*children):
    return {'type': 'block_quote', 'children': list(children)}


def bullet(*items):
    return {'type': 'bullet_list', 'children': [
        {'type': 'list_item', 'children': list(children)} for children in items]}


CASES = [
    ('quote_lazy', '> quoted\nlazy\n> explicit', [quote(paragraph(text('quoted\nlazy\nexplicit')))]),
    ('nested_quote_lazy', '>>> nested\nlazy\n> continued', [
        quote(quote(quote(paragraph(text('nested\nlazy\ncontinued')))))]),
    ('quote_blank', '> quoted\n\noutside', [quote(paragraph(text('quoted'))), paragraph(text('outside'))]),
    ('quote_marked_blank', '> quoted\n>\noutside', [quote(paragraph(text('quoted'))), paragraph(text('outside'))]),
    ('quote_after_fence', '> ```\n> inert\n> ```\noutside', [
        quote({'type': 'code_block', 'info': '', 'text': 'inert\n'}), paragraph(text('outside'))]),
    ('quote_tab', '>\tquoted', [quote(paragraph(text('quoted')))]),
    ('list_lazy', '- first\nlazy\n- second', [bullet([paragraph(text('first\nlazy'))], [paragraph(text('second'))])]),
    ('list_tab', '-\tfirst\n\tcontinuation\n- next', [bullet([paragraph(text('first\ncontinuation'))], [paragraph(text('next'))])]),
    ('list_loose_tab', '-\tfirst\n\n\tsecond paragraph', [bullet([paragraph(text('first')), paragraph(text('second paragraph'))])]),
    ('list_empty', '-\n- second', [bullet([], [paragraph(text('second'))])]),
    ('list_after_fence', '- ```\n  inert\n  ```\noutside', [
        bullet([{'type': 'code_block', 'info': '', 'text': 'inert\n'}]), paragraph(text('outside'))]),
    ('empty_marker_in_paragraph', 'intro\n+', [paragraph(text('intro\n+'))]),
    ('noninitial_number_in_paragraph', 'intro\n2. continuation', [paragraph(text('intro\n2. continuation'))]),
    ('ordered_zero_prefix', 'intro\n01. step', [paragraph(text('intro')), {'type': 'ordered_list', 'start': 1,
        'children': [{'type': 'list_item', 'children': [paragraph(text('step'))]}]}]),
    ('four_space_padding', '-    first\n     continuation', [bullet([paragraph(text('first\ncontinuation'))])]),
    ('tabs_in_content', 'alpha\tbeta `x\ty`', [paragraph(text('alpha\tbeta '), {'type': 'code_span', 'text': 'x\ty'})]),
    ('soft_break_space', 'alpha \n  beta', [paragraph(text('alpha\nbeta'))]),
    ('soft_break_tab', 'alpha\t\n  beta', [paragraph(text('alpha\nbeta'))]),
    ('fence_tab_indentation', '  ```\n\talpha\tbeta\n  ```', [
        {'type': 'code_block', 'info': '', 'text': '  alpha\tbeta\n'}]),
    ('fence_indentation', '  ```` example\n    x\n ```\n  ````\n', [
        {'type': 'code_block', 'info': 'example', 'text': '  x\n```\n'}]),
    ('empty_fence', '~~~\n~~~', [{'type': 'code_block', 'info': '', 'text': ''}]),
    ('escaped_heading_and_html', r'\# literal \<script\>', [paragraph(text('# literal <script>'))]),
    ('comparison', '2 < 3 > 1', [paragraph(text('2 < 3 > 1'))]),
    ('unknown_entity', '&notanentity;', [paragraph(text('&notanentity;'))]),
    ('single_entity_decode', '&amp;lt;script&amp;gt;', [paragraph(text('&lt;script&gt;'))]),
    ('balanced_attachment_parentheses', '[file](attachments/a(b(c(d))).txt)', [paragraph({'type': 'link',
        'attachment_path': 'attachments/a(b(c(d))).txt', 'children': [text('file')]})]),
    ('escaped_attachment_parentheses', r'[file](attachments/a\(b\).txt)', [paragraph({'type': 'link',
        'attachment_path': 'attachments/a(b).txt', 'children': [text('file')]})]),
    ('encoded_attachment_space', '[file](attachments/a%20b.txt)', [paragraph({'type': 'link',
        'attachment_path': 'attachments/a b.txt', 'children': [text('file')]})]),
    ('escaped_entity_in_destination', r'[file](attachments/a\&amp;.txt)', [paragraph({'type': 'link',
        'attachment_path': 'attachments/a&amp;.txt', 'children': [text('file')]})]),
    ('code_label_precedence', '[`x]`](attachments/a.txt)', [paragraph({'type': 'link',
        'attachment_path': 'attachments/a.txt', 'children': [{'type': 'code_span', 'text': 'x]'}]})]),
]


@pytest.mark.parametrize(('name', 'source', 'expected'), CASES, ids=[row[0] for row in CASES])
def test_container_and_inline_edge_cases_preserve_the_declared_semantic_structure(name, source, expected):
    with no_write_attempts(): parsed = parse_prose(prose(source))
    assert parsed.data['content'] == {'type': 'document', 'children': expected}


UNSAFE = [
    ('<SCRIPT>execute()</SCRIPT>', 'prose_raw_html_or_autolink_forbidden'),
    ('<?xml version="1.0"?>', 'prose_raw_html_or_autolink_forbidden'),
    ('<!DOCTYPE html>', 'prose_raw_html_or_autolink_forbidden'),
    ('<iframe src="remote"></iframe>', 'prose_raw_html_or_autolink_forbidden'),
    ('[run](javascript:alert(1))', 'prose_attachment_path_required'),
    ('[run](java&#x73;cript:alert(1))', 'prose_attachment_path_required'),
    ('[run](d&#97;ta:text/plain,code)', 'prose_attachment_path_required'),
    ('[run](file:///outside/project)', 'prose_attachment_path_required'),
    (r'[run](C:\outside\project)', 'prose_attachment_path_required'),
    ('[run](//invalid.example/a)', 'prose_attachment_path_required'),
    ('[file](attachments/%5c..%5csecret)', 'prose_attachment_path_required'),
    ('[file](attachments/a?query=1)', 'prose_attachment_path_required'),
    ('[file](attachments/a#fragment)', 'prose_attachment_path_required'),
    ('[file](attachments/%252e%252e/secret)', 'prose_attachment_path_required'),
    ('[file](attachments/.git/config)', 'prose_attachment_path_required'),
    ('[file](attachments/CON.txt)', 'prose_attachment_path_required'),
    ('[file](attachments/a.)', 'prose_attachment_path_required'),
    ('[file](attachments/%00x)', 'prose_attachment_path_required'),
    ('[file](attachments/%ff)', 'prose_attachment_path_required'),
    ('[file](attachments/a%zz)', 'prose_attachment_path_required'),
    ('[file](attachments/a%3Fquery)', 'prose_attachment_path_required'),
    ('&#x3c;svg&gt;', 'prose_active_entity'),
    ('&#10;', 'prose_active_entity'),
    ('&Tab;', 'prose_active_entity'),
    ('[split\nlabel]: attachments/a.txt', 'prose_reference_definition_forbidden'),
    ('> ## hidden heading', 'prose_heading_forbidden'),
    ('-     indented code', 'prose_indented_code_forbidden'),
    ('[outer [inner](attachments/a.txt)](attachments/b.txt)', 'prose_nested_link_forbidden'),
]


@pytest.mark.parametrize('kind', ['prose', 'admonition'])
@pytest.mark.parametrize(('source', 'reason'), UNSAFE)
def test_obfuscated_active_or_foreign_inputs_are_refused_in_both_prose_payloads(kind, source, reason):
    block = prose(source, kind)
    with no_write_attempts(), pytest.raises(ProseError) as caught: parse_prose(block)
    assert caught.value.reason == reason and caught.value.pointer == '/payload/markdown'
    assert caught.value.path == block.path and block.payload['markdown'] == source


@pytest.mark.parametrize('directive', ['{{include https://invalid.example/code}}',
    '!include /outside/project', '{% include "remote" %}', '@include(https://invalid.example/code)'])
def test_foreign_include_syntax_is_literal_text_without_extension_or_loader_semantics(directive, tmp_path, monkeypatch):
    block = prose(directive); marker = tmp_path / 'marker'; marker.write_bytes(b'unchanged')
    before = inventory(tmp_path)
    def forbidden(*args, **kwargs): raise AssertionError('Parser attempted a source or attachment read')
    with no_write_attempts(), monkeypatch.context() as patch:
        patch.setattr(builtins, 'open', forbidden); patch.setattr(Path, 'read_bytes', forbidden)
        content = parse_prose(block).data['content']
    assert content == {'type': 'document', 'children': [paragraph(text(directive))]}
    assert inventory(tmp_path) == before


@pytest.mark.parametrize(('source', 'reason'), [
    ('x' * 1_048_577, 'prose_size_limit'),
    ('> ' * 66 + 'nested', 'prose_nesting_limit'),
    ('*' * 140 + 'nested' + '*' * 140, 'prose_nesting_limit'),
    ('[' * 8000, 'prose_complexity_limit'),
], ids=['bytes', 'containers', 'emphasis', 'work'])
def test_untrusted_parser_resources_fail_with_structured_errors_before_result_creation(source, reason):
    with no_write_attempts(), pytest.raises(ProseError) as caught: parse_prose(prose(source))
    assert caught.value.reason == reason
    assert caught.value.pointer == '/payload/markdown'


@pytest.mark.parametrize('value', [None, {}, b'{}', 'prose', True, 1])
def test_non_native_blocks_cannot_supply_custom_parser_or_loading_behavior(value):
    with no_write_attempts(), pytest.raises(ProseError) as caught: parse_prose(value)
    assert caught.value.reason == 'prose_content_block_required'


def test_html_in_code_and_plain_admonition_titles_never_becomes_an_active_node(tmp_path):
    path = tmp_path / 'marker'; path.write_bytes(b'untouched'); before = inventory(tmp_path)
    block = prose('```html\n<script>execute()</script>\n```', 'admonition', title='<img onerror="execute()">')
    with no_write_attempts(): result = parse_prose(block)
    assert result.data['content'] == {'type': 'admonition', 'level': block.payload['level'],
        'title': '<img onerror="execute()">', 'children': [
            {'type': 'code_block', 'info': 'html', 'text': '<script>execute()</script>\n'}]}
    assert inventory(tmp_path) == before and not result.data['rendering_performed']


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_completed_container_semantics_and_security_errors_run_in_isolated_core_and_pyz(tmp_path, mode):
    sources = [prose('> quote\nlazy\n\n-\titem\n\tcontinued').source_bytes,
        prose('![foreign](attachments/%252e%252e/a)').source_bytes,
        prose('&notanentity; &amp;lt;script&amp;gt;').source_bytes]
    expected = []
    for raw in sources:
        try: expected.append(parse_prose(ContentBlock(raw)).data)
        except ProseError as error: expected.append(error.diagnostic())
    body = 'import json\nfrom specroad.documents import ContentBlock, ProseError, parse_prose\n'
    body += 'sources=' + repr(sources) + '\n'
    body += '''results=[]
for raw in sources:
 try: results.append(parse_prose(ContentBlock(raw)).data)
 except ProseError as error: results.append(error.diagnostic())
print(json.dumps(results,sort_keys=True))
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
