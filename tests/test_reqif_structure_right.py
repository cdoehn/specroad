"""14.i.R: identity, native graphs and exact inert XHTML boundary behavior."""
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch
from xml.sax.saxutils import escape, quoteattr

import pytest

from specroad.documents import ContentBlock, parse_prose
from specroad.exchange import ReqIFError, decode_reqif_structure, encode_reqif
from specroad.mappings import ExchangeMapping
from support.artifacts import artifact_bytes
from support.domain import domain_value, relation as native_relation
from support.exchange_mappings import mapping_value
from support.read_only import no_write_attempts
from support.records import record_value, ref
from support.reqif_objects import LIMITS, spec_object
from support.reqif_structure import attachment, hierarchy, relation, specification, structured, xdocument, XHTML
from support.targets import model


def read(raw):
    return decode_reqif_structure(raw, limits=LIMITS)


def text(value):
    return {'type': 'text', 'text': value}


def paragraph(value):
    return {'type': 'paragraph', 'children': [text(value)]}


def native(markdown):
    block = ContentBlock(artifact_bytes(record_value('content_block', payload={'markdown': markdown})))
    return parse_prose(block).data['content']


def inverse(doc, markdown, **kwargs):
    return doc.export_xhtml('object', 'field', markdown, expected_source_sha256=doc.source_sha256, **kwargs)


@pytest.mark.parametrize('space', ['\u00a0', '\u1680', '\u2003', '\u202f', '\u3000'])
def test_unicode_space_between_blocks_is_content_not_xml_indentation(space):
    raw = xdocument('<p>before</p>' + space + '<p>after</p>')
    doc = read(raw)
    with no_write_attempts():
        result = doc.project_xhtml('object', 'field')
        roundtrip = read(encode_reqif(doc))
    expected = {'type': 'document', 'children': [paragraph('before'), paragraph(space), paragraph('after')]}
    assert result['content'] == native(result['markdown']) == expected
    assert roundtrip.project_xhtml('object', 'field')['content'] == expected
    assert inverse(doc, result['markdown'])['xml_bytes'] == raw


@pytest.mark.parametrize('space', ['\u00a0', '\u2003', '\u3000'])
@pytest.mark.parametrize('place', ['list', 'value-wrapper', 'reqif-container'])
def test_non_xml_whitespace_is_not_silently_dropped_from_element_only_containers(space, place):
    raw = xdocument('<ul>' + space + '<li>one</li></ul>') if place == 'list' else xdocument('<p>one</p>')
    if place == 'value-wrapper': raw = raw.replace(b'<THE-VALUE>', b'<THE-VALUE>' + space.encode())
    if place == 'reqif-container': raw = raw.replace(b'<SPEC-OBJECTS>', b'<SPEC-OBJECTS>' + space.encode())
    with pytest.raises(ReqIFError) as exc: read(raw)
    assert exc.value.exit_code == 3 and exc.value.pointer


@pytest.mark.parametrize('space', [' ', '\t', '\r\n', ' \n\t'])
def test_xml_structural_whitespace_is_distinct_from_inline_text(space):
    doc = read(xdocument('<div>' + space + '<p>a<span> b</span> c</p>' + space + '<p>d</p>' + space + '</div>'))
    assert doc.project_xhtml('object', 'field')['content'] == {
        'type': 'document', 'children': [paragraph('a b c'), paragraph('d')]}


@pytest.mark.parametrize('content', [' ', '  ', '`', '``', 'a``b`c', ' padded ', ' ` ', '\u00a0', '日本語 & <x>'])
def test_code_delimiters_and_all_space_spans_preserve_exact_native_text(content):
    doc = read(xdocument('<p><code>' + escape(content) + '</code></p>'))
    result = doc.project_xhtml('object', 'field')
    expected = {'type': 'document', 'children': [{'type': 'paragraph', 'children': [{'type': 'code_span', 'text': content}]}]}
    assert result['content'] == native(result['markdown']) == expected
    changed = inverse(read(xdocument('<p>old</p>')), result['markdown'])
    assert read(changed['xml_bytes']).project_xhtml('object', 'field')['content'] == expected


@pytest.mark.parametrize('content', ['```\n', '  α\n\tβ\n', '\n\n', '<script>&text\n', '~`~`````\n'])
def test_pre_text_is_not_trimmed_or_interpreted(content):
    doc = read(xdocument('<pre>' + escape(content) + '</pre>'))
    result = doc.project_xhtml('object', 'field')
    assert result['content'] == native(result['markdown']) == {
        'type': 'document', 'children': [{'type': 'code_block', 'text': content, 'info': ''}]}
    assert inverse(doc, result['markdown'])['xml_bytes'] == doc.source_bytes


@pytest.mark.parametrize('body', ['<p> leading</p>', '<p>trailing </p>', '<p>a\n b</p>',
    '<p><code>a\nb</code></p>', '<p><code/></p>', '<pre>no final newline</pre>',
    '<p><em> leading</em></p>', '<p><strong>trailing </strong></p>'])
def test_nonrepresentable_whitespace_never_succeeds_with_changed_text(body):
    doc = read(xdocument(body))
    result = doc.project_record('object', xhtml=True)
    assert not result['representable'] and not result['fields']
    assert result['unrepresentable'][0]['reason'] == 'reqif_xhtml_prose_roundtrip_loss'
    assert doc.source_bytes == xdocument(body)
    with pytest.raises(ReqIFError) as exc: doc.project_xhtml('object', 'field')
    assert exc.value.object_id == 'object' and exc.value.definition_id == 'field' and exc.value.pointer


@pytest.mark.parametrize('body', ['<span><ul><li>x</li></ul></span>', '<p><blockquote>x</blockquote></p>',
    '<li>orphan</li>', '<ul>text<li>x</li></ul>', '<ol><div><li>x</li></div></ol>',
    '<pre>text<code>x</code></pre>', '<pre><code>x</code><code>y</code></pre>',
    '<p><code><span>x</span></code></p>', '<p><a href="one"><span><a href="two">x</a></span></a></p>',
    '<br> </br>', '<hr>\n</hr>'])
def test_profile_invalid_nesting_lists_and_text_only_shapes_are_not_repaired(body):
    with no_write_attempts(), pytest.raises(ReqIFError) as exc: read(xdocument(body))
    assert exc.value.exit_code == 3 and exc.value.pointer


@pytest.mark.parametrize('body', ['<p xmlns="urn:foreign">kept</p>', '<p xmlns="">kept</p>',
    '<p xml:lang="de">kept</p>', '<p dir="rtl">kept</p>', '<ol start="2"><li>kept</li></ol>',
    '<object data="doc.pdf" type="application/pdf"><div><p>kept fallback</p></div></object>',
    '<object data="a.png" type="image/png"><span>kept fallback</span></object>',
    '<table><tr><td><p>kept</p></td></tr></table>'])
@pytest.mark.parametrize('original', [False, True])
def test_unknown_namespaces_attributes_and_object_fallbacks_keep_source_without_plaintext(body, original):
    raw = xdocument('<p>safe</p>' if original else body, original=body if original else None)
    doc = read(raw)
    assert doc.source_bytes == raw and doc.unsupported
    result = doc.project_record('object', xhtml=True)
    assert not result['representable'] and result['fields'] == {}
    assert result['unrepresentable'][0]['definition_id'] == 'field'
    with pytest.raises(ReqIFError): inverse(doc, 'replacement')
    assert doc.source_bytes == raw


def test_prefix_spelling_is_not_xhtml_identity():
    plain = xdocument('<p>safe</p>')
    prefixed = plain.replace(('<div xmlns="' + XHTML + '">').encode(),
                            ('<x:div xmlns:x="' + XHTML + '">').encode()).replace(b'</div>', b'</x:div>')
    prefixed = prefixed.replace(b'<p>', b'<x:p>').replace(b'</p>', b'</x:p>')
    first, second = read(plain), read(prefixed)
    assert first.project_xhtml('object', 'field')['content'] == second.project_xhtml('object', 'field')['content']
    assert encode_reqif(first) == encode_reqif(second)
    assert inverse(second, 'safe')['xml_bytes'] == prefixed


@pytest.mark.parametrize('flag', [None, 'false', '0'])
@pytest.mark.parametrize('default', [False, True])
def test_original_reference_requires_real_binding_and_unchanged_default_keeps_flag_presence(flag, default):
    raw = xdocument('<p>current</p>', original='<p><a href="manual.txt">original</a></p>', simplified=flag, default=default)
    doc = read(raw)
    assert not doc.project_record('object', xhtml=True)['representable']
    with pytest.raises(ReqIFError) as exc: doc.project_xhtml('object', 'field')
    assert exc.value.reason == 'reqif_attachment_unresolved' and 'THE-ORIGINAL-VALUE' in exc.value.pointer
    bindings = [attachment('manual.txt', 'attachments/manual.txt', b'manual', 'text/plain')]
    assert doc.project_xhtml('object', 'field', attachments=bindings)['content'] == {'type': 'document', 'children': [paragraph('current')]}
    assert inverse(doc, 'current', attachments=bindings)['xml_bytes'] == raw
    updated = inverse(doc, 'new', attachments=bindings)['xml_bytes']
    assert ('IS-SIMPLIFIED' in updated.decode()) == (flag is not None)
    assert b'THE-ORIGINAL-VALUE' in updated and b'manual.txt' in updated


@pytest.mark.parametrize('flag', ['true', '1'])
def test_simplified_values_keep_original_and_flag_without_fidelity_or_inverse_pass(flag):
    raw = xdocument('<p>current</p>', original='<p>original</p>', simplified=flag)
    doc = read(raw)
    assert read(encode_reqif(doc)).objects[0].values[0].lexical.simplified
    with pytest.raises(ReqIFError) as exc: inverse(doc, 'current')
    assert exc.value.exit_code == 6 and exc.value.reason == 'reqif_xhtml_source_simplified'
    assert doc.source_bytes == raw


@pytest.mark.parametrize('markdown,reason', [('2. start at two', 'reqif_xhtml_list_start_not_representable'),
    ('```python\npass\n```', 'reqif_xhtml_code_info_not_representable'),
    ('[missing](attachments/absent.txt)', 'reqif_attachment_inverse_ambiguous')])
def test_inverse_never_guesses_list_language_or_attachment_bindings(markdown, reason):
    doc = read(xdocument('<p>old</p>'))
    with no_write_attempts(), pytest.raises(ReqIFError) as exc: inverse(doc, markdown)
    assert exc.value.exit_code == 6 and exc.value.reason == reason
    assert doc.project_xhtml('object', 'field')['content'] == {'type': 'document', 'children': [paragraph('old')]}


@pytest.mark.parametrize('reference', ['', '/etc/x', '//host/x', 'file:///x', 'data:image/png,x',
    'javascript:x', 'https://example.invalid/x', 'C:/x', 'C:\\x', '\\host\\x', 'a\\b',
    './x', '../x', 'a/../x', 'a//b', 'a/', 'a?x', 'a#x', '%2e%2e/x', '%2Fetc/x',
    'a%5Cb', 'a%3Ab', 'a%3Fb', 'a%23b', 'a%00b', 'a%7Fb', '%252e%252e/x',
    'a%25b', '%ff', '%c0%af', 'x%', 'x%2', 'x%GG'])
def test_relative_references_cannot_escape_by_percent_unicode_or_path_syntax(reference):
    raw = xdocument('<p><a href=' + quoteattr(reference) + '>secret payload</a></p>')
    with no_write_attempts(), pytest.raises(ReqIFError) as exc: read(raw)
    assert exc.value.exit_code == 7 and exc.value.reason == 'reqif_attachment_reference_unsafe'
    assert exc.value.diagnostic()['line'] >= 1 and exc.value.diagnostic()['position'] >= 0
    assert 'secret payload' not in str(exc.value.diagnostic())


@pytest.mark.parametrize('reference', ['manual/a%20b.txt', 'manual/%E6%97%A5.txt', 'a%2Fb.txt'])
def test_safe_decoded_reference_keeps_original_exact_binding_key(reference):
    doc = read(xdocument('<p><a href=' + quoteattr(reference) + '>manual</a></p>'))
    binding = attachment(reference, 'attachments/manual.txt', b'owned', 'text/plain')
    with no_write_attempts(): result = doc.project_xhtml('object', 'field', attachments=[binding])
    assert result['content']['children'][0]['children'][0]['attachment_path'] == 'attachments/manual.txt'
    from urllib.parse import unquote
    other = replace(binding, reference=unquote(reference))
    with pytest.raises(ReqIFError) as exc: doc.project_xhtml('object', 'field', attachments=[other])
    assert exc.value.reason == 'reqif_attachment_unresolved'


@pytest.mark.parametrize('changed', ['bytes', 'media'])
@pytest.mark.parametrize('reverse', [False, True])
def test_aliases_cannot_bind_one_native_target_to_competing_bytes_or_media(changed, reverse):
    bindings = [attachment('first.txt', 'attachments/a.txt', b'one', 'text/plain'),
                attachment('second.txt', 'attachments/a.txt', b'two' if changed == 'bytes' else b'one',
                           'application/json' if changed == 'media' else 'text/plain')]
    if reverse: bindings.reverse()
    doc = read(xdocument('<p><a href="first.txt">one</a></p>'))
    with pytest.raises(ReqIFError) as exc: doc.project_xhtml('object', 'field', attachments=bindings)
    assert exc.value.exit_code == 6 and exc.value.reason == 'reqif_attachment_target_conflict'


def test_equal_byte_aliases_preserve_unchanged_reference_but_cannot_guess_new_inverse():
    binding = attachment('first.txt', 'attachments/a.txt', b'one', 'text/plain')
    bindings = [binding, replace(binding, reference='second.txt')]
    doc = read(xdocument('<p><a href="first.txt">one</a></p>'))
    markdown = doc.project_xhtml('object', 'field', attachments=bindings)['markdown']
    assert inverse(doc, markdown, attachments=bindings)['xml_bytes'] == doc.source_bytes
    with pytest.raises(ReqIFError) as exc: inverse(doc, markdown + '\n\nnew', attachments=bindings)
    assert exc.value.exit_code == 6 and exc.value.reason == 'reqif_attachment_inverse_ambiguous'


@pytest.mark.parametrize('change', ['hash', 'size', 'content'])
def test_attachment_integrity_is_rechecked_at_each_projection(change):
    binding = attachment()
    if change == 'content': object.__setattr__(binding, 'content', b'changed')
    else: object.__setattr__(binding.descriptor, 'sha256' if change == 'hash' else 'size', '0'*64 if change == 'hash' else 0)
    doc = read(xdocument('<p><object type="image/png" data="pictures/a.png">alt</object></p>'))
    with no_write_attempts(), pytest.raises(ReqIFError) as exc: doc.project_xhtml('object', 'field', attachments=[binding])
    assert exc.value.exit_code == 6 and exc.value.reason == 'reqif_attachment_bytes_changed'


@pytest.mark.parametrize('original', [False, True])
@pytest.mark.parametrize('content,media', [(b'not a PNG', 'image/png'), (b'\x89PNG\r\n\x1a\nowned', 'text/plain')])
def test_claimed_mime_or_png_signature_alone_is_insufficient(content, media, original):
    image = '<p><object type="image/png" data="pictures/a.png">alt</object></p>'
    doc = read(xdocument('<p>safe</p>' if original else image, original=image if original else None))
    with pytest.raises(ReqIFError) as exc:
        doc.project_xhtml('object', 'field', attachments=[attachment(content=content, media_type=media)])
    assert exc.value.reason == 'reqif_attachment_image_type_mismatch' and exc.value.exit_code == 3


@pytest.mark.parametrize('body', ['<style>p {background:url(https://never.invalid)}</style>',
    '<unknown><style>p {color:red}</style></unknown>', '<p xmlns:e="urn:x" e:onclick="run">x</p>',
    '<p xmlns:e="urn:x" e:href="https://never.invalid">x</p>', '<iframe/>', '<embed/>',
    '<object type="application/pdf" data="local.pdf"><div><script/></div></object>',
    '<include/>', '<p xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="x y"/>',
    '<x:include xmlns:x="http://www.w3.org/2001/XInclude" href="local"/>'])
@pytest.mark.parametrize('place', ['value', 'original', 'extension'])
def test_security_checks_cover_unknown_fallback_original_and_extension_subtrees(body, place):
    raw = xdocument(body if place == 'value' else '<p>safe</p>', original=body if place == 'original' else None)
    if place == 'extension':
        raw = raw.replace(b'</REQ-IF>', ('<TOOL-EXTENSIONS><div xmlns="' + XHTML + '">' + body + '</div></TOOL-EXTENSIONS></REQ-IF>').encode())
    with no_write_attempts(), pytest.raises(ReqIFError) as exc: read(raw)
    assert exc.value.exit_code == 7


@pytest.mark.parametrize('prefix', ['<!DOCTYPE REQ-IF>', '<!DOCTYPE REQ-IF SYSTEM "file:///never">',
    '<!DOCTYPE REQ-IF [<!ENTITY x "expanded">]>', '<?xml-stylesheet href="file:///never"?>'])
def test_no_dtd_entity_or_processing_instruction_fallback(prefix):
    raw = xdocument('<p>safe</p>').replace(b'?>\n', b'?>\n' + prefix.encode(), 1)
    with no_write_attempts(), pytest.raises(ReqIFError) as exc: read(raw)
    assert exc.value.exit_code == 7


@pytest.mark.parametrize('limit,reason', [('max_bytes', 'xml_byte_limit'), ('max_depth', 'xml_depth_limit'),
    ('max_elements', 'xml_element_limit'), ('max_text_chars', 'xml_text_limit'),
    ('max_attributes_per_element', 'xml_attribute_limit'), ('max_name_chars', 'xml_name_limit'),
    ('max_expanded_name_chars', 'xml_expanded_name_limit')])
def test_every_explicit_xml_resource_limit_applies_to_structure_mode(limit, reason):
    with pytest.raises(ReqIFError) as exc:
        decode_reqif_structure(xdocument('<p>safe</p>'), limits=replace(LIMITS, **{limit: 1}))
    assert exc.value.exit_code == 7 and exc.value.reason == reason


def test_xml_byte_budget_is_inclusive_and_utf8_bytes_are_counted():
    raw = xdocument('<p>日本語</p>')
    assert decode_reqif_structure(raw, limits=replace(LIMITS, max_bytes=len(raw))).source_bytes == raw
    with pytest.raises(ReqIFError) as exc:
        decode_reqif_structure(raw, limits=replace(LIMITS, max_bytes=len(raw)-1))
    assert exc.value.reason == 'xml_byte_limit'


@pytest.mark.parametrize('kind', ['size', 'nesting'])
def test_actual_prose_resource_limits_are_safety_errors_not_mapped_losses(kind):
    body = '<p>' + 'x'*1_048_577 + '</p>' if kind == 'size' else '<blockquote>'*70 + '<p>x</p>' + '</blockquote>'*70
    doc = read(xdocument(body))
    with pytest.raises(ReqIFError) as exc: doc.project_record('object', xhtml=True)
    assert exc.value.exit_code == 7 and exc.value.reason == 'reqif_prose_' + kind + '_limit'
    assert doc.source_bytes == xdocument(body)


@pytest.mark.parametrize('markdown,kind', [('x'*1_048_577, 'size'), ('> '*70 + 'x', 'nesting'), ('['*4000, 'complexity')],
                         ids=['size', 'nesting', 'complexity'])
def test_inverse_actual_prose_budgets_are_not_conflicts_or_replacement_passes(markdown, kind):
    doc = read(xdocument('<p>old</p>'))
    with pytest.raises(ReqIFError) as exc: inverse(doc, markdown)
    assert exc.value.exit_code == 7 and exc.value.reason == 'reqif_prose_' + kind + '_limit'
    assert doc.source_bytes == xdocument('<p>old</p>')


@pytest.mark.parametrize('operation', ['read', 'project', 'inverse', 'encode'])
@pytest.mark.parametrize('failure', [MemoryError, RecursionError, OSError])
def test_real_resource_and_io_failures_escape_unchanged(operation, failure):
    doc = read(xdocument('<p>safe</p>'))
    target = {'read': 'specroad.exchange.reqif.read_bounded_xml', 'project': 'specroad.exchange._reqif_xhtml._parse_markdown',
              'inverse': 'specroad.exchange._reqif_xhtml._parse_markdown', 'encode': 'specroad.exchange.reqif._serialize'}[operation]
    error = failure('host failure')
    with patch(target, side_effect=error), pytest.raises(failure) as exc:
        if operation == 'read': read(doc.source_bytes)
        elif operation == 'project': doc.project_record('object', xhtml=True)
        elif operation == 'inverse': inverse(doc, 'new')
        else: encode_reqif(doc)
    assert exc.value is error


@pytest.mark.parametrize('kind', ['owner-cycle', 'two-owners', 'spec-occurrence-collision', 'relation-collision',
                                  'missing-object', 'wrong-source', 'wrong-target'])
def test_source_ownership_and_typed_reference_errors_cannot_be_complete_structures(kind):
    raw = structured()
    if kind == 'owner-cycle': raw = structured(children=hierarchy('h1', 'a', hierarchy('h1', 'b')))
    elif kind == 'two-owners': raw = raw.replace(specification('empty').encode(), specification('empty', hierarchy('h2')).encode())
    elif kind == 'spec-occurrence-collision': raw = raw.replace(b'IDENTIFIER="h1"', b'IDENTIFIER="spec"')
    elif kind == 'relation-collision': raw = raw.replace(b'IDENTIFIER="edge"', b'IDENTIFIER="h1"')
    elif kind == 'missing-object': raw = raw.replace(b'<SPEC-OBJECT-REF>b</SPEC-OBJECT-REF>', b'<SPEC-OBJECT-REF>missing</SPEC-OBJECT-REF>')
    elif kind == 'wrong-source': raw = raw.replace(b'<SOURCE><SPEC-OBJECT-REF>a', b'<SOURCE><SPEC-OBJECT-REF>spec')
    else: raw = raw.replace(b'<TARGET><SPEC-OBJECT-REF>b', b'<TARGET><SPEC-OBJECT-REF>type')
    with no_write_attempts(), pytest.raises(ReqIFError) as exc: read(raw)
    assert exc.value.exit_code == 3 and exc.value.pointer


def edge(kind, target, token, **extra):
    return {**native_relation(kind, target), 'relation_id': 'REL-' + token*26, **extra}


def bound_graph(*, reverse=False, cycle=False, relation_type='depends_on'):
    raw = structured(children=hierarchy('h1', 'a', hierarchy('h2', 'b')),
                     relations=relation('edge', 'c', 'd') + (relation('back', 'd', 'c') if cycle else ''))
    raw = raw.replace(b'</SPEC-OBJECTS>', (spec_object(identifier='c') + spec_object(identifier='d')).encode() + b'</SPEC-OBJECTS>')
    doc = read(raw)
    resource = ExchangeMapping(artifact_bytes(mapping_value(
        types=[{'external_type': 'spec_type', 'artifact_type': 'document'}],
        fields=[{'external_type': 'spec_type', 'external_field': 'spec_text', 'target_field': 'title', 'value_map': None}],
        relations=[{'external_type': 'rel_type', 'relation_type': relation_type, 'direction': 'reverse' if reverse else 'forward'}],
        hierarchies=[{'external_type': 'type', 'relation_type': 'contains', 'direction': 'parent_to_child'}])))
    records = [record_value('document', relations=[edge('contains', ref('SEC'), '0', position=0)]),
        record_value('section', relations=[edge('contains', ref('BLOCK'), '1', position=0)]),
        record_value('content_block'), record_value('document', id=ref('DOC', '1'), document_role='supporting'),
        domain_value('component'), domain_value('component', id=ref('COMP', '1'))]
    first, second = (records[5], records[4]) if reverse else (records[4], records[5])
    first['relations'].append(edge(relation_type, second['id'], '2'))
    if cycle: second['relations'].append(edge(relation_type, first['id'], '3'))
    args = dict(mappings=[resource], key=resource.key, expected_mapping_sha256=resource.sha256,
        expected_source_sha256=doc.source_sha256, source_system='supplier', source_document='source',
        object_bindings={'a': ref('SEC'), 'b': ref('BLOCK'), 'c': ref('COMP'), 'd': ref('COMP', '1')},
        occurrence_bindings={'spec': ref('DOC'), 'empty': ref('DOC', '1'), 'h1': ref('SEC'), 'h2': ref('BLOCK')},
        relation_bindings={'h1': 'REL-'+'0'*26, 'h2': 'REL-'+'1'*26, 'edge': 'REL-'+'2'*26}, native_model=model(records))
    if cycle: args['relation_bindings']['back'] = 'REL-'+'3'*26
    return doc, args, records


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('relation_type', ['depends_on', 'part_of'])
def test_native_relation_cycle_policy_uses_selected_core_type_not_blanket_reqif_rule(reverse, relation_type):
    doc, args, _ = bound_graph(reverse=reverse, cycle=True, relation_type=relation_type)
    assert len(read(encode_reqif(doc)).relations) == 2
    with no_write_attempts():
        if relation_type == 'part_of':
            with pytest.raises(ReqIFError) as exc: doc.map_structure(**args)
            assert exc.value.exit_code == 3 and exc.value.reason == 'reqif_native_structure_invalid'
        else:
            report = doc.map_structure(**args)
            assert [r['external_identity']['external_id'] for r in report['relations']] == ['edge', 'back']
            a, b = ref('COMP'), ref('COMP', '1')
            assert [(r['source'], r['target']) for r in report['relations']] == ([(b,a), (a,b)] if reverse else [(a,b), (b,a)])
            assert not report['import_complete']


@pytest.mark.parametrize('kind', ['object-identity', 'document-identity', 'edge-identity', 'contains-cycle', 'two-native-owners'])
def test_ambiguous_inverse_identity_and_actual_native_ownership_prevent_mapping(kind):
    doc, args, records = bound_graph()
    if kind == 'object-identity': args['object_bindings']['d'] = args['object_bindings']['c']
    elif kind == 'document-identity': args['occurrence_bindings']['empty'] = args['occurrence_bindings']['spec']
    elif kind == 'edge-identity': args['relation_bindings']['edge'] = args['relation_bindings']['h1']
    elif kind == 'two-native-owners':
        records[3]['relations'].append(edge('contains', ref('SEC'), '4', position=0))
    else:
        records[0]['relations'] = []
        records[1]['relations'].append(edge('contains', ref('SEC', '1'), '4', position=1))
        records.append(record_value('section', id=ref('SEC', '1'), relations=[edge('contains', ref('SEC'), '5', position=0)]))
    args['native_model'] = model(records)
    before = deepcopy(args['native_model'].artifacts)
    with no_write_attempts(), pytest.raises(ReqIFError) as exc: doc.map_structure(**args)
    assert exc.value.exit_code == (3 if kind in ('contains-cycle', 'two-native-owners') else 6)
    assert args['native_model'].artifacts == before


@pytest.mark.parametrize('table,key', [('object_bindings','c'), ('occurrence_bindings','spec'),
                                      ('occurrence_bindings','h2'), ('relation_bindings','h1'), ('relation_bindings','edge')])
def test_missing_bindings_do_not_fall_back_to_names_positions_or_endpoints(table, key):
    doc, args, _ = bound_graph()
    args[table].pop(key)
    with pytest.raises(ReqIFError) as exc: doc.map_structure(**args)
    assert exc.value.exit_code == 6 and exc.value.reason == 'reqif_native_binding_missing'
    assert exc.value.object_id == key


def test_reimport_and_sibling_reordering_keep_occurrence_and_relation_identity():
    _, args, records = bound_graph(cycle=True)
    domain = domain_value('requirement')
    records[2].update(block_kind='artifact_ref', payload={'render_mode':'full'},
                      relations=[edge('references', domain['id'], '4')])
    records += [record_value('content_block', id=ref('BLOCK','1'), block_kind='artifact_ref',
                payload={'render_mode':'full'}, relations=[edge('references', domain['id'], '5')]), domain]
    records[1]['relations'].append(edge('contains', ref('BLOCK','1'), '6', position=1))
    args['object_bindings']['b'] = domain['id']
    args['occurrence_bindings']['h3'] = ref('BLOCK','1')
    args['relation_bindings']['h3'] = 'REL-'+'6'*26
    observed = []
    for order in [('h2','h3'), ('h3','h2')]:
        doc, _, _ = bound_graph(cycle=True)
        raw = doc.source_bytes.replace(hierarchy('h1','a',hierarchy('h2','b')).encode(),
            hierarchy('h1','a',''.join(hierarchy(key,'b') for key in order)).encode())
        doc = read(raw)
        for item in records[1]['relations']:
            key = 'h2' if item['target'] == ref('BLOCK') else 'h3'
            item['position'] = order.index(key)
        args.update(expected_source_sha256=doc.source_sha256, native_model=model(records))
        with no_write_attempts():
            report = doc.map_structure(**args)
            again = read(encode_reqif(doc))
            replay = again.map_structure(**{**args, 'expected_source_sha256': again.source_sha256})
        assert report['hierarchies'] == replay['hierarchies'] and report['relations'] == replay['relations']
        assert [h['external_identity']['external_id'] for h in report['hierarchies']] == ['h1', *order]
        observed.append({h['external_identity']['external_id']:h['relation_id'] for h in report['hierarchies']})
        assert report['relations'][0]['external_identity']['external_id'] == 'edge'
        assert report['relations'][1]['external_identity']['external_id'] == 'back'
        assert [o.identifier for o in doc.objects] == ['a', 'b', 'c', 'd']
        assert [h.object_id for h in doc.hierarchies] == ['a', 'b', 'b']
    assert observed == [{'h1':'REL-'+'0'*26, 'h2':'REL-'+'1'*26, 'h3':'REL-'+'6'*26}]*2
    assert next(r for r in args['native_model'].artifacts if r['id'] == domain['id']) == domain
