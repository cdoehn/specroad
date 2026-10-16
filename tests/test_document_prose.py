"""Prose semantic nodes, original source ownership and forbidden effects."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.documents import ContentBlock, ProseContent, ProseError, parse_prose
from specroad.model.canonical import canonical_json_sha256
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import block_value


def prose(markdown, kind='prose', **payload):
    value = block_value(kind)
    value['payload'].update(markdown=markdown, **payload)
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
    return ContentBlock(raw, path='provided-prose.json')


def text(value):
    return {'type': 'text', 'text': value}


def paragraph(*children):
    return {'type': 'paragraph', 'children': list(children)}


@pytest.mark.parametrize(('source', 'expected'), [
    ('A plain paragraph.', [paragraph(text('A plain paragraph.'))]),
    ('first\nline\n\nsecond', [paragraph(text('first\nline')), paragraph(text('second'))]),
    ('*focus* and **strong**', [paragraph({'type': 'emphasis', 'children': [text('focus')]},
        text(' and '), {'type': 'strong', 'children': [text('strong')]})]),
    ('_focus_ and __strong__', [paragraph({'type': 'emphasis', 'children': [text('focus')]},
        text(' and '), {'type': 'strong', 'children': [text('strong')]})]),
    ('**outer _inner_**', [paragraph({'type': 'strong', 'children': [text('outer '),
        {'type': 'emphasis', 'children': [text('inner')]}]})]),
    ('***both***', [paragraph({'type': 'emphasis', 'children': [
        {'type': 'strong', 'children': [text('both')]}]})]),
    ('part_of_word', [paragraph(text('part_of_word'))]),
    ('`<script>never execute</script>`', [paragraph({'type': 'code_span',
        'text': '<script>never execute</script>'})]),
    ('`` `inner` ``', [paragraph({'type': 'code_span', 'text': '`inner`'})]),
    ('`a\nb`', [paragraph({'type': 'code_span', 'text': 'a b'})]),
    ('```python\nprint("inert")\n```', [{'type': 'code_block', 'info': 'python', 'text': 'print("inert")\n'}]),
    ('~~~\n<script>alert(1)</script>\n~~~', [{'type': 'code_block', 'info': '', 'text': '<script>alert(1)</script>\n'}]),
    ('```\nunclosed', [{'type': 'code_block', 'info': '', 'text': 'unclosed'}]),
    ('- first\n- second', [{'type': 'bullet_list', 'children': [
        {'type': 'list_item', 'children': [paragraph(text('first'))]},
        {'type': 'list_item', 'children': [paragraph(text('second'))]}]}]),
    ('3. third\n4. fourth', [{'type': 'ordered_list', 'start': 3, 'children': [
        {'type': 'list_item', 'children': [paragraph(text('third'))]},
        {'type': 'list_item', 'children': [paragraph(text('fourth'))]}]}]),
    ('> quoted\n> continuation', [{'type': 'block_quote', 'children': [paragraph(text('quoted\ncontinuation'))]}]),
    ('---', [{'type': 'thematic_break'}]),
    ('[manual](attachments/manual.pdf)', [paragraph({'type': 'link',
        'attachment_path': 'attachments/manual.pdf', 'children': [text('manual')]})]),
    ('![diagram](attachments/diagram.png "Diagram")', [paragraph({'type': 'image',
        'attachment_path': 'attachments/diagram.png', 'title': 'Diagram', 'children': [text('diagram')]})]),
    ('[**manual**](<attachments/user manual.pdf>)', [paragraph({'type': 'link',
        'attachment_path': 'attachments/user manual.pdf', 'children': [
            {'type': 'strong', 'children': [text('manual')]}]})]),
    (r'\*literal\* &amp; &#233;', [paragraph(text('*literal* & é'))]),
    ('a  \nb', [paragraph(text('a'), {'type': 'line_break'}, text('b'))]),
    ('a\\\nb', [paragraph(text('a'), {'type': 'line_break'}, text('b'))]),
    ('', []),
])
def test_allowed_prose_constructs_produce_inert_semantic_nodes(source, expected):
    with no_write_attempts(): parsed = parse_prose(prose(source))
    assert parsed.data['content'] == {'type': 'document', 'children': expected}


def test_nested_lists_quotes_and_fences_have_no_executable_node_type():
    source = '- outer\n  - nested\n\n  > quoted\n\n  ```shell\n  exit 99\n  ```\n- final'
    with no_write_attempts(): content = parse_prose(prose(source)).data['content']
    first, last = content['children'][0]['children']
    assert [node['type'] for node in first['children']] == ['paragraph', 'bullet_list', 'block_quote', 'code_block']
    assert first['children'][1]['children'][0]['children'] == [paragraph(text('nested'))]
    assert first['children'][2]['children'] == [paragraph(text('quoted'))]
    assert first['children'][3] == {'type': 'code_block', 'info': 'shell', 'text': 'exit 99\n'}
    assert last['children'] == [paragraph(text('final'))]


@pytest.mark.parametrize('level', ['note', 'tip', 'important', 'warning', 'caution'])
def test_admonitions_use_the_same_prose_nodes_and_keep_title_as_plain_data(level):
    with no_write_attempts():
        block = prose('**careful**', 'admonition', level=level, title='Plain *title*')
        parsed = parse_prose(block)
    assert parsed.data['content'] == {'type': 'admonition', 'level': level,
        'title': 'Plain *title*', 'children': [paragraph({'type': 'strong', 'children': [text('careful')]})]}
    assert parsed.source_bytes == block.source_bytes


@pytest.mark.parametrize('ending', ['\n', '\r\n', '\r'])
def test_line_endings_normalize_without_rewriting_the_original_record(ending):
    source = 'ä\u2028文' + ending + ending + '**next**'
    block = prose(source); original = block.source_bytes
    with no_write_attempts(): parsed = parse_prose(block)
    reference = parse_prose(prose(source.replace(ending, '\n'))).data
    data = parsed.data
    assert parsed.source_bytes == original and block.payload['markdown'] == source
    assert data['content'] == reference['content']
    assert data['content']['children'][0] == paragraph(text('ä\u2028文'))
    assert data['normalized_markdown_sha256'] == reference['normalized_markdown_sha256']
    assert data['block']['source_sha256'] == sha256(original).hexdigest()
    assert data['nodes_sha256'] == canonical_json_sha256(data['content'])


@pytest.mark.parametrize(('source', 'reason'), [
    ('<script>alert(1)</script>', 'prose_raw_html_or_autolink_forbidden'),
    ('<img src="remote" onerror="execute()">', 'prose_raw_html_or_autolink_forbidden'),
    ('<!-- include remote -->', 'prose_raw_html_or_autolink_forbidden'),
    ('# heading', 'prose_heading_forbidden'),
    ('heading\n===', 'prose_heading_forbidden'),
    ('heading\n---', 'prose_heading_forbidden'),
    ('[ref]: attachments/manual.pdf', 'prose_reference_definition_forbidden'),
    ('&lt;script&gt;', 'prose_active_entity'),
    ('    indented code', 'prose_indented_code_forbidden'),
    ('[remote](https://invalid.example/manual.pdf)', 'prose_attachment_path_required'),
    ('![data](data:image/svg+xml,payload)', 'prose_attachment_path_required'),
    ('[escape](attachments/../secret)', 'prose_attachment_path_required'),
    ('[absolute](/attachments/a.pdf)', 'prose_attachment_path_required'),
    ('[encoded](attachments/%2e%2e/secret)', 'prose_attachment_path_required'),
    ('nul\x00byte', 'prose_control_character_forbidden'),
])
def test_forbidden_semantics_are_rejected_before_a_prose_value_is_returned(source, reason):
    block = prose(source)
    with no_write_attempts(), pytest.raises(ProseError) as caught: parse_prose(block)
    assert caught.value.reason == reason and caught.value.path == block.path
    assert caught.value.pointer == '/payload/markdown'
    assert block.payload['markdown'] == source


def test_prose_values_are_owned_detached_and_do_not_claim_attachment_or_rendering_approval():
    block = prose('[missing](attachments/missing.pdf)'); parsed = parse_prose(block)
    expected = parsed.data; expected_sha = parsed.sha256
    changed = parsed.data; changed['content']['children'].clear(); changed['block'].clear()
    assert parsed.data == expected and parsed.sha256 == expected_sha
    assert parsed.data['block'] == block.binding
    assert parsed.data['validation_scope'] == 'owned_prose_nodes'
    assert parsed.data['prose_parsed']
    assert not any(parsed.data[key] for key in ('attachments_resolved', 'project_files_verified',
        'full_validation_passed', 'rendering_performed', 'write_authorized', 'approval_granted'))
    with pytest.raises(FrozenInstanceError): parsed.source_bytes = b'{}'
    with pytest.raises(TypeError): bool(parsed)
    with pytest.raises(TypeError): ProseContent()


@pytest.mark.parametrize('kind', ['artifact_ref', 'query', 'table', 'page_break', 'include_document'])
def test_other_content_kinds_cannot_be_parsed_as_prose(kind):
    raw = json.dumps(block_value(kind)).encode()
    with no_write_attempts(), pytest.raises(ProseError) as caught:
        parse_prose(ContentBlock(raw))
    assert caught.value.reason == 'prose_block_kind_required'
    assert caught.value.pointer == '/block_kind'


def test_owned_sources_are_used_after_the_real_record_is_removed_and_no_attachment_is_read(tmp_path):
    block = prose('[local](attachments/absent.pdf)'); path = tmp_path / 'block.json'
    path.write_bytes(block.source_bytes); owned = ContentBlock(path.read_bytes(), path=str(path))
    before = inventory(tmp_path)
    with no_write_attempts(): parsed = parse_prose(owned)
    assert inventory(tmp_path) == before
    path.unlink()
    with no_write_attempts(): again = parse_prose(owned)
    assert again.data == parsed.data and not path.exists()


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_prose_nodes_and_refusals_match_in_isolated_core_and_pyz(tmp_path, mode):
    sources = [prose('**prose**\n\n> [file](attachments/manual.pdf)').source_bytes,
               prose('`<script>`', 'admonition', level='warning').source_bytes,
               prose('![remote](https://invalid.example/a.png)').source_bytes]
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
