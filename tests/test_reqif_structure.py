"""14.i.W: source structures, native bindings and semantic prose intersection."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
from unittest.mock import patch
from xml.sax.saxutils import escape

import pytest

from specroad.documents import ContentBlock, parse_prose
from specroad.exchange import ReqIFAttachment, ReqIFError, decode_reqif, decode_reqif_structure, encode_reqif
from specroad.mappings import ExchangeMapping, MappingError
from support.artifacts import artifact_bytes
from support.domain import domain_value, relation as native_relation
from support.exchange_mappings import mapping_value
from support.read_only import no_write_attempts
from support.records import record_value, ref
from support.reqif_objects import LIMITS, TIME, spec_object
from support.reqif_structure import (attachment, hierarchy, relation, structured, xdocument, XHTML)
from support.targets import model


def read(raw):
    return decode_reqif_structure(raw, limits=LIMITS)


def semantics(doc):
    return {'specifications': [(s.identifier, s.type_id, s.children, s.element.attributes,
                               doc.project_record(s.identifier)) for s in doc.specifications],
            'hierarchies': [(h.identifier, h.object_id, h.owner_id, h.children, h.element.attributes) for h in doc.hierarchies],
            'relations': [(r.identifier, r.type_id, r.source, r.target, r.element.attributes,
                           doc.project_record(r.identifier)) for r in doc.relations]}


def test_structure_roundtrip_preserves_occurrence_identity_owner_order_and_defaults():
    raw = structured()
    with no_write_attempts():
        doc = read(raw); encoded = encode_reqif(doc); again = read(encoded)
    assert semantics(doc) == semantics(again)
    assert encode_reqif(again) == encoded
    assert [(s.identifier, s.children) for s in doc.specifications] == [('spec', ('h1', 'h3')), ('empty', ())]
    assert [(h.identifier, h.object_id, h.owner_id, h.children) for h in doc.hierarchies] == [
        ('h1', 'a', 'spec', ('h2',)), ('h2', 'b', 'h1', ()), ('h3', 'a', 'spec', ())]
    assert len(doc.objects) == 2
    assert doc.project_record('spec')['fields'] == {'spec_text': 'default spec'}
    assert doc.project_record('edge')['fields'] == {'rel_text': 'default relation'}
    assert doc.project_record('edge')['origins'] == {'rel_text': 'default'}
    assert doc.source_bytes == raw and doc.source_sha256 == sha256(raw).hexdigest()
    assert not doc.unsupported
    observed = doc.observation()
    assert observed['profile'] == 'reqif-structure-xhtml-v1'
    assert (observed['specification_count'], observed['occurrence_count'], observed['relation_count']) == (2, 3, 1)
    assert not any(observed[k] for k in ('import_complete', 'execution_ready', 'write_authorized'))
    with pytest.raises(TypeError): bool(doc)
    with pytest.raises(FrozenInstanceError): doc.hierarchies[0].owner_id = 'other'


def test_structure_mode_is_explicit_and_does_not_reinterpret_legacy_observations():
    old = decode_reqif(structured(), limits=LIMITS)
    assert old.observation()['profile'] == 'reqif-object-profile-v1' and old.unsupported
    with pytest.raises(ReqIFError) as exc: old.project_record('spec')
    assert exc.value.exit_code == 2


@pytest.mark.parametrize('relations', [relation() + relation('back', 'b', 'a'), relation('self', 'a', 'a')])
def test_passive_relation_cycles_are_not_confused_with_hierarchy_ownership(relations):
    doc = read(structured(relations=relations))
    assert semantics(read(encode_reqif(doc))) == semantics(doc)


@pytest.mark.parametrize('old,new', [
    (b'IDENTIFIER="h2"', b'IDENTIFIER="h1"'),
    (b'<SPEC-OBJECT-REF>b</SPEC-OBJECT-REF>', b'<SPEC-OBJECT-REF>missing</SPEC-OBJECT-REF>'),
    (b'<SPEC-OBJECT-REF>a</SPEC-OBJECT-REF>', b'<SPEC-OBJECT-REF>spec</SPEC-OBJECT-REF>'),
    (b'<SPECIFICATION-TYPE-REF>spec_type', b'<SPECIFICATION-TYPE-REF>type'),
    (b'<SPEC-RELATION-TYPE-REF>rel_type', b'<SPEC-RELATION-TYPE-REF>spec_type'),
    (b'<SPEC-OBJECT-TYPE-REF>type', b'<SPEC-OBJECT-TYPE-REF>rel_type'),
    (b'IDENTIFIER="edge"', b'IDENTIFIER="a"'),
    (b'<TARGET><SPEC-OBJECT-REF>b</SPEC-OBJECT-REF></TARGET>', b''),
])
def test_global_duplicates_missing_and_wrong_kind_references_prevent_structure_pass(old, new):
    raw = structured().replace(old, new)
    with no_write_attempts(), pytest.raises(ReqIFError) as exc: read(raw)
    assert exc.value.exit_code == 3 and exc.value.pointer


def text(value): return {'type': 'text', 'text': value}
def para(*nodes): return {'type': 'paragraph', 'children': list(nodes)}


@pytest.mark.parametrize('body,expected', [
    ('', []), ('<div/><p/>', []), ('<p>plain</p>', [para(text('plain'))]),
    ('before<p>block</p>after', [para(text('before')), para(text('block')), para(text('after'))]),
    ('<div>\n<p>one</p>\n<p>two</p>\n</div>', [para(text('one')), para(text('two'))]),
    ('<p><span>A</span> B\nC<br/>D</p>', [para(text('A B\nC'), {'type': 'line_break'}, text('D'))]),
    ('<p><em>E</em> <i>I</i> <strong>S</strong> <b>B</b></p>', [para(
        {'type': 'emphasis', 'children': [text('E')]}, text(' '), {'type': 'emphasis', 'children': [text('I')]},
        text(' '), {'type': 'strong', 'children': [text('S')]}, text(' '), {'type': 'strong', 'children': [text('B')]})]),
    ('<p><code>a ` b</code></p>', [para({'type': 'code_span', 'text': 'a ` b'})]),
    ('<pre><code>  a\n\tb\n</code></pre>', [{'type': 'code_block', 'text': '  a\n\tb\n', 'info': ''}]),
    ('<pre>literal\n</pre>', [{'type': 'code_block', 'text': 'literal\n', 'info': ''}]),
    ('<blockquote><p>quote</p></blockquote><hr/>', [{'type': 'block_quote', 'children': [para(text('quote'))]}, {'type': 'thematic_break'}]),
    ('<ul><li>a</li><li>b</li></ul>', [{'type': 'bullet_list', 'children': [
        {'type': 'list_item', 'children': [para(text('a'))]}, {'type': 'list_item', 'children': [para(text('b'))]}]}]),
    ('<ol><li>a</li><li>b</li></ol>', [{'type': 'ordered_list', 'start': 1, 'children': [
        {'type': 'list_item', 'children': [para(text('a'))]}, {'type': 'list_item', 'children': [para(text('b'))]}]}]),
])
def test_all_xhtml_core_families_reparse_to_independent_native_semantic_oracles(body, expected):
    raw = xdocument(body); doc = read(raw)
    with no_write_attempts():
        result = doc.project_xhtml('object', 'field')
        parsed = parse_prose(ContentBlock(artifact_bytes(record_value('content_block', payload={'markdown': result['markdown']})))).data
        encoded = encode_reqif(doc)
        inverse = doc.export_xhtml('object', 'field', result['markdown'], expected_source_sha256=doc.source_sha256)
    assert result['content'] == parsed['content'] == {'type': 'document', 'children': expected}
    assert inverse['xml_bytes'] == raw
    assert read(encoded).project_xhtml('object', 'field')['content'] == result['content']
    assert encode_reqif(read(encoded)) == encoded
    assert result['origin'] == 'explicit' and not result['media_decoded']
    assert not inverse['export_complete'] and not inverse['write_authorized']


@pytest.mark.parametrize('content', ['日本語 e\u0301 é 😀', '*_`[]()!#>-+\\ & <script>literal</script>',
                                     '&lt; not another entity', 'first\nsecond', '1. not a list'])
def test_decoded_text_is_not_reparsed_as_markup_or_entities(content):
    doc = read(xdocument('<p>' + escape(content) + '</p>'))
    result = doc.project_xhtml('object', 'field')
    assert result['content'] == {'type': 'document', 'children': [para(text(content))]}


def test_explicit_png_and_link_bindings_preserve_targets_titles_and_inline_children():
    bindings = (attachment(), attachment('manual/a%20b.txt', 'attachments/manual.txt', b'manual', 'text/plain'))
    doc = read(xdocument('<p><object type="image/png" data="pictures/a.png">alt &amp; text</object>'
                        ' <a href="manual/a%20b.txt" title="title &quot;quoted&quot;"><em>manual</em></a></p>'))
    with no_write_attempts(): result = doc.project_xhtml('object', 'field', attachments=bindings)
    nodes = result['content']['children'][0]['children']
    assert nodes == [{'type': 'image', 'attachment_path': 'attachments/a.png', 'children': [text('alt & text')]}, text(' '),
                     {'type': 'link', 'attachment_path': 'attachments/manual.txt', 'title': 'title "quoted"',
                      'children': [{'type': 'emphasis', 'children': [text('manual')]}]}]
    exported = doc.export_xhtml('object', 'field', result['markdown'] + '\n\nNew',
                               expected_source_sha256=doc.source_sha256, attachments=bindings)
    assert read(exported['xml_bytes']).project_xhtml('object', 'field', attachments=bindings)['content']['children'] == [para(*nodes), para(text('New'))]
    with pytest.raises(ReqIFError) as exc: doc.project_xhtml('object', 'field')
    assert exc.value.reason == 'reqif_attachment_unresolved'


@pytest.mark.parametrize('body', ['<table><tr><td>retained</td></tr></table>', '<p class="kept">text</p>',
                                 '<h1>title</h1>', '<p xmlns="urn:other">retained</p>',
                                 '<object type="application/pdf" data="file.pdf">fallback</object>'])
def test_unsupported_passive_source_is_retained_without_plaintext_fallback(body):
    raw = xdocument(body); doc = read(raw)
    assert doc.source_bytes == raw and doc.unsupported
    report = doc.project_record('object', xhtml=True)
    assert report['fields'] == {} and not report['representable']
    assert report['unrepresentable'][0]['definition_id'] == 'field'
    with pytest.raises(ReqIFError): encode_reqif(doc)


@pytest.mark.parametrize('default', [False, True])
def test_original_value_flags_and_default_absence_survive_unchanged_and_updated_inverse(default):
    raw = xdocument('<p>current</p>', original='<p>original</p>', simplified='false', default=default)
    doc = read(raw); projection = doc.project_xhtml('object', 'field')
    assert projection['origin'] == ('default' if default else 'explicit')
    assert doc.export_xhtml('object', 'field', 'current', expected_source_sha256=doc.source_sha256)['xml_bytes'] == raw
    changed = doc.export_xhtml('object', 'field', '**new**', expected_source_sha256=doc.source_sha256)['xml_bytes']
    updated = read(changed)
    assert updated.project_xhtml('object', 'field')['content'] == {'type': 'document', 'children': [para({'type': 'strong', 'children': [text('new')]})]}
    assert b'IS-SIMPLIFIED="false"' in changed and b'THE-ORIGINAL-VALUE' in changed and b'original' in changed
    assert updated.objects[0].element.attrs == doc.objects[0].element.attrs
    assert changed == doc.export_xhtml('object', 'field', '**new**', expected_source_sha256=doc.source_sha256)['xml_bytes']


def test_simplified_source_cannot_claim_original_fidelity_or_replace_with_original():
    raw = xdocument('<p>current</p>', original='<p>different</p>', simplified='true')
    doc = read(raw)
    assert read(encode_reqif(doc)).source_bytes and doc.source_bytes == raw
    with pytest.raises(ReqIFError) as exc: doc.project_xhtml('object', 'field')
    assert exc.value.reason == 'reqif_xhtml_source_simplified'


@pytest.mark.parametrize('body', ['<p><div>bad</div></p>', '<p><a href="a"><a href="b">bad</a></a></p>',
                                 '<br>text</br>', '<hr><span/></hr>', '<ul/>', '<ol><p>bad</p></ol>',
                                 '<p><code><em>bad</em></code></p>', '<pre><p>bad</p></pre>'])
def test_invalid_xhtml_structure_is_not_html_repaired(body):
    with pytest.raises(ReqIFError) as exc: read(xdocument(body))
    assert exc.value.exit_code == 3


@pytest.mark.parametrize('body', ['<script>ignored</script>', '<p onclick="run()">text</p>',
                                 '<unknown><a href="https://never.invalid">external</a></unknown>',
                                 '<p><a href="%2e%2e/secret">bad</a></p>', '<p><a href="x%252f..">bad</a></p>'])
@pytest.mark.parametrize('place', ['value', 'original', 'extension'])
def test_active_or_external_content_is_rejected_in_every_source_subtree(body, place):
    raw = xdocument(body if place == 'value' else '<p>safe</p>', original=body if place == 'original' else None)
    if place == 'extension':
        raw = raw.replace(b'</REQ-IF>', ('<TOOL-EXTENSIONS><x xmlns="' + XHTML + '">' + body + '</x></TOOL-EXTENSIONS></REQ-IF>').encode())
    with no_write_attempts(), pytest.raises(ReqIFError) as exc: read(raw)
    assert exc.value.exit_code == 7


@pytest.mark.parametrize('change', ['bytes', 'hash', 'duplicate', 'target', 'inverse-source'])
def test_attachment_integrity_and_source_binding_fail_without_writes(change):
    good = attachment(); doc = read(xdocument('<p><object type="image/png" data="pictures/a.png">alt</object></p>'))
    with no_write_attempts(), pytest.raises(ReqIFError) as exc:
        if change == 'bytes': ReqIFAttachment(good.reference, good.descriptor, b'wrong')
        elif change == 'hash': ReqIFAttachment(good.reference, replace(good.descriptor, sha256='0'*64), good.content)
        elif change == 'duplicate': doc.project_xhtml('object', 'field', attachments=(good, good))
        elif change == 'target': ReqIFAttachment(good.reference, replace(good.descriptor, path='outside/a.png'), good.content)
        else: doc.export_xhtml('object', 'field', 'x', expected_source_sha256='0'*64)
    assert exc.value.exit_code in (6, 7)


def mapped_fixture(reverse=False):
    raw = structured(children=hierarchy('h1', 'a', hierarchy('h2', 'b')), relations=relation('edge', 'c', 'd'))
    raw = raw.replace(b'</SPEC-OBJECTS>', (spec_object(identifier='c') + spec_object(identifier='d')).encode() + b'</SPEC-OBJECTS>')
    doc = read(raw)
    resource = ExchangeMapping(artifact_bytes(mapping_value(types=[{'external_type': 'spec_type', 'artifact_type': 'document'}],
        fields=[{'external_type': 'spec_type', 'external_field': 'spec_text', 'target_field': 'title', 'value_map': None}],
        relations=[{'external_type': 'rel_type', 'relation_type': 'depends_on', 'direction': 'reverse' if reverse else 'forward'}],
        hierarchies=[{'external_type': 'type', 'relation_type': 'contains', 'direction': 'parent_to_child'}])))
    def edge(kind, target, token, **extra):
        return {**native_relation(kind, target), 'relation_id': 'REL-' + token * 26, **extra}
    a, b = ref('SEC'), ref('BLOCK')
    root = record_value('document', id=ref('DOC'), relations=[edge('contains', a, '0', position=0)])
    section = record_value('section', id=a, relations=[edge('contains', b, '1', position=0)])
    block = record_value('content_block', id=b)
    first = domain_value('component')
    second = domain_value('component', id=ref('COMP', '1'))
    (second if reverse else first)['relations'].append(edge('depends_on', first['id'] if reverse else second['id'], '2'))
    empty = record_value('document', id=ref('DOC', '1'), document_role='supporting')
    records = [root, section, block, empty, first, second]
    args = dict(mappings=[resource], key=resource.key, expected_mapping_sha256=resource.sha256,
        expected_source_sha256=doc.source_sha256, source_system='supplier', source_document='source',
        object_bindings={'a': a, 'b': b, 'c': first['id'], 'd': second['id']}, occurrence_bindings={'spec': root['id'], 'empty': empty['id'], 'h1': a, 'h2': b},
        relation_bindings={'h1': 'REL-' + '0'*26, 'h2': 'REL-' + '1'*26, 'edge': 'REL-' + '2'*26}, native_model=model(records))
    return doc, args, records


@pytest.mark.parametrize('reverse', [False, True])
def test_mapping_uses_type_ids_explicit_endpoints_and_actual_m11_structure(reverse):
    doc, args, records = mapped_fixture(reverse)
    before = deepcopy(args['native_model'].artifacts)
    with no_write_attempts(): report = doc.map_structure(**args)
    edge = report['relations'][0]
    first, second = records[4]['id'], records[5]['id']
    assert (edge['source'], edge['target']) == ((second, first) if reverse else (first, second))
    assert edge['external_identity'] == {'object_class': 'relation', 'source_system': 'supplier',
                                        'source_document': 'source', 'external_id': 'edge'}
    assert [h['external_identity']['external_id'] for h in report['hierarchies']] == ['h1', 'h2']
    assert report['hierarchies'][1]['owner_id'] == 'h1'
    assert report['specifications'][0]['field_projection']['artifact'] == {'artifact_type': 'document', 'title': 'default spec'}
    assert report['native_structure']['structure_valid']
    assert not report['import_complete'] and not report['write_authorized']
    assert args['native_model'].artifacts == before


def test_two_native_occurrences_reference_one_unchanged_domain_object():
    from support.domain import domain_value
    doc, args, records = mapped_fixture()
    doc = read(structured(children=hierarchy('h1', 'b', hierarchy('h2', 'a') + hierarchy('h3', 'a')), relations=''))
    domain = domain_value('requirement')
    records = [records[0], records[1], record_value('content_block', id=ref('BLOCK')),
               record_value('content_block', id=ref('BLOCK', '1')), records[3], domain]
    records[1]['relations'] = [{**native_relation('contains', block['id']), 'relation_id': 'REL-' + str(i+1)*26, 'position': i}
                               for i, block in enumerate(records[2:4])]
    for i, block in enumerate(records[2:4]):
        block.update(block_kind='artifact_ref', payload={'render_mode': 'full'},
                     relations=[{**native_relation('references', domain['id']), 'relation_id': 'REL-' + str(i+3)*26}])
    args.update(expected_source_sha256=doc.source_sha256, native_model=model(records), object_bindings={'a': domain['id'], 'b': ref('SEC')},
                relation_bindings={'h1': 'REL-' + '0'*26, 'h2': 'REL-' + '1'*26, 'h3': 'REL-' + '2'*26})
    args['occurrence_bindings']['h3'] = ref('BLOCK', '1')
    report = doc.map_structure(**args)
    assert [v['object_id'] for v in report['hierarchies']] == ['b', 'a', 'a']
    assert [v['target'] for v in report['hierarchies']] == [ref('SEC'), ref('BLOCK'), ref('BLOCK', '1')]
    assert next(r for r in args['native_model'].artifacts if r['id'] == domain['id']) == domain


@pytest.mark.parametrize('change', ['source', 'mapping', 'endpoint', 'occurrence', 'relation-id', 'model-order', 'missing-parent'])
def test_native_mapping_rejects_unbound_or_mismatching_structure(change):
    doc, args, records = mapped_fixture()
    if change == 'source': args['expected_source_sha256'] = '0'*64
    elif change == 'mapping': args['expected_mapping_sha256'] = '0'*64
    elif change == 'endpoint': args['object_bindings'].pop('a')
    elif change == 'occurrence': args['occurrence_bindings']['h1'] = ref('BLOCK')
    elif change == 'relation-id': args['relation_bindings']['edge'] = 'REL-' + '3'*26
    elif change == 'model-order':
        records[0]['relations'][0]['position'] = 7; args['native_model'] = model(records)
    else:
        records[0]['relations'] = []; args['native_model'] = model(records)
    with no_write_attempts(), pytest.raises((ReqIFError, MappingError)): doc.map_structure(**args)


def test_general_mapping_requires_explicit_xhtml_adapter_and_bound_field_value_map():
    doc = read(xdocument('<p><strong>bold</strong></p>'))
    resource = ExchangeMapping(artifact_bytes(mapping_value(types=[{'external_type': 'type', 'artifact_type': 'requirement'}],
        fields=[{'external_type': 'type', 'external_field': 'field', 'target_field': 'statement',
                 'value_map': [{'external_value': '**bold**', 'target_value': 'mapped text'}]}])))
    args = dict(mappings=[resource], key=resource.key, expected_mapping_sha256=resource.sha256,
                expected_source_sha256=doc.source_sha256, source_system='supplier', source_document='doc')
    assert doc.map_record('object', **args)['artifact'] is None
    assert doc.map_record('object', **args, xhtml=True)['artifact'] == {'artifact_type': 'requirement', 'statement': 'mapped text'}


@pytest.mark.parametrize('markdown', ['*italic* and **strong**', '- one\n  - nested\n- two', '> quote\n>\n> next',
                                     '```\ncode & <text>\n```', 'first\\\nsecond\nsoft'])
def test_new_inverse_values_roundtrip_through_native_parser(markdown):
    doc = read(xdocument('<p>old</p>'))
    native = parse_prose(ContentBlock(artifact_bytes(record_value('content_block', payload={'markdown': markdown})))).data['content']
    with no_write_attempts():
        result = doc.export_xhtml('object', 'field', markdown, expected_source_sha256=doc.source_sha256)
        actual = read(result['xml_bytes']).project_xhtml('object', 'field')
    assert actual['content'] == native
    assert result['xml_bytes'] == doc.export_xhtml('object', 'field', markdown, expected_source_sha256=doc.source_sha256)['xml_bytes']


@pytest.mark.parametrize('error_type', [MemoryError, RecursionError, OSError])
def test_real_prose_resource_failures_are_not_relabelled_as_nonrepresentable(error_type):
    doc = read(xdocument('<p>safe</p>'))
    with patch('specroad.exchange._reqif_xhtml._parse_markdown', side_effect=error_type):
        with pytest.raises(error_type): doc.project_record('object', xhtml=True)
