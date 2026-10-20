"""Hostile XML stays bounded, passive and independent of host codec plugins."""
from contextlib import contextmanager
from hashlib import sha256
import codecs
import json

import pytest

from specroad.verification import JUnitDocument, JUnitLimits, XmlImportError
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts


def expansion_attack():
    declarations = ['<!ENTITY e0 "xxxxxxxxxx">']
    for level in range(1, 10):
        declarations.append('<!ENTITY e' + str(level) + ' "' +
                            ('&e' + str(level - 1) + ';') * 10 + '">')
    return ('<!DOCTYPE testsuite [' + ''.join(declarations) +
            ']><testsuite>&e9;</testsuite>')


DTD_ATTACKS = {
    'external-public': '<!DOCTYPE testsuite PUBLIC "-//secret//DTD//EN" '
                       '"https://example.invalid/secret"><testsuite/>',
    'external-general': '<!DOCTYPE testsuite [<!ENTITY e SYSTEM '
                        '"file:///secret">]><testsuite>&e;</testsuite>',
    'external-parameter': '<!DOCTYPE testsuite [<!ENTITY % e SYSTEM '
                          '"https://example.invalid/secret">%e;]><testsuite/>',
    'recursive-general': '<!DOCTYPE testsuite [<!ENTITY e "&e;">]><testsuite>&e;</testsuite>',
    'recursive-parameter': '<!DOCTYPE testsuite [<!ENTITY % e "%e;">%e;]><testsuite/>',
    'default-attribute': '<!DOCTYPE testsuite [<!ATTLIST testsuite name CDATA "secret">]>'
                         '<testsuite/>',
    'exponential': expansion_attack(),
    'quadratic': '<!DOCTYPE testsuite [<!ENTITY e "' + 'x' * 4096 +
                 '">]><testsuite>' + '&e;' * 4096 + '</testsuite>',
}
SCHEMA_ATTACKS = {
    'schema-location': '<extension xmlns:other="http://www.w3.org/2001/XMLSchema-instance" '
                       'other:schemaLocation="urn:fixture https://example.invalid/secret"/>',
    'no-namespace-location': '<extension xmlns:x="http://www.w3.org/2001/XMLSchema-instance" '
                            'x:noNamespaceSchemaLocation="file:///secret"/>',
    'encoded-namespace': '<extension xmlns:x="http://www.w3.org/2001/XMLSchema-instan&#99;e" '
                         'x:schemaLocation="urn:fixture file:///secret"/>',
    'default-schema': '<schema xmlns="http://www.w3.org/2001/XMLSchema"/>',
    'schema-redefine': '<x:redefine xmlns:x="http://www.w3.org/2001/XMLSchema" '
                      'schemaLocation="file:///secret"/>',
    'include': '<i:include xmlns:i="http://www.w3.org/2001/XInclude" href="file:///secret"/>',
    'include-text': '<i:include xmlns:i="http://www.w3.org/2001/XInclude" '
                    'href="https://example.invalid/secret" parse="text"/>',
}


@contextmanager
def no_external_access(monkeypatch):
    attempts = []
    def forbidden(*args, **kwargs):
        attempts.append(True)
        raise AssertionError('The XML input attempted host I/O or external execution')
    with no_write_attempts(), monkeypatch.context() as patch:
        for name in ('builtins.open', 'io.open', 'os.open', 'socket.getaddrinfo',
                     'socket.create_connection', 'os.popen', 'os.execve', 'os.posix_spawn'):
            patch.setattr(name, forbidden, raising=False)
        yield
    assert attempts == []


@pytest.mark.parametrize('attack', sorted(DTD_ATTACKS))
@pytest.mark.parametrize('encoding', ['utf-8', 'utf-8-sig', 'utf-16', 'utf-16-le', 'utf-16-be'])
def test_entity_expansion_is_rejected_at_the_doctype_before_reading_the_subset(attack, encoding, monkeypatch):
    raw = DTD_ATTACKS[attack].encode(encoding)
    with no_external_access(monkeypatch), pytest.raises(XmlImportError) as caught:
        JUnitDocument(raw)
    error = caught.value
    assert (error.reason, error.exit_code) == ('xml_dtd_or_entity_forbidden', 7)
    assert error.diagnostic()['code'] == 'SRV083'
    # DTD rejection precedes even an invalid or exponentially expanding subset.
    assert error.position <= len(DTD_ATTACKS[attack].split('>', 1)[0].encode(encoding))
    assert 'secret' not in json.dumps(error.diagnostic()) and 'secret' not in str(error)


@pytest.mark.parametrize('attack', sorted(SCHEMA_ATTACKS))
@pytest.mark.parametrize('ignored', [False, True], ids=['direct', 'ignored-subtree'])
def test_schema_and_inclusion_requests_cannot_hide_under_opaque_extensions(attack, ignored, monkeypatch):
    body = SCHEMA_ATTACKS[attack]
    if ignored:
        body = '<extension><testcase>' + body + '</testcase></extension>'
    raw = ('<testsuite>' + body + '</testsuite>').encode()
    with no_external_access(monkeypatch), pytest.raises(XmlImportError) as caught:
        JUnitDocument(raw)
    assert (caught.value.reason, caught.value.exit_code) == ('xml_external_reference_forbidden', 7)


@pytest.mark.parametrize('body', ['<?xml-stylesheet href="file:///secret"?><testsuite/>',
    '<testsuite><?execute secret?></testsuite>',
    '<testsuite><extension><?execute secret?></extension></testsuite>',
    '<testsuite/><?execute secret?>'])
def test_processing_requests_are_forbidden_at_every_document_position(body, monkeypatch):
    with no_external_access(monkeypatch), pytest.raises(XmlImportError) as caught:
        JUnitDocument(body.encode())
    assert (caught.value.reason, caught.value.exit_code) == ('xml_processing_instruction_forbidden', 7)


@pytest.mark.parametrize('body', [
    '<testsuite xmlns:p="urn:p" xmlns:q="urn:q" xmlns:r="urn:r"/>',
    '<testsuite xmlns:p="urn:p" xmlns:q="urn:q" name="third"/>',
    '<testsuite><extension xmlns:p="urn:p" xmlns:q="urn:q" extra="third"/></testsuite>',
])
def test_namespace_declarations_and_ordinary_attributes_share_the_element_limit(body, monkeypatch):
    with no_external_access(monkeypatch), pytest.raises(XmlImportError) as caught:
        JUnitDocument(body.encode(), limits=JUnitLimits(max_attributes_per_element=2))
    assert (caught.value.reason, caught.value.exit_code) == ('xml_attribute_limit', 7)


def test_namespace_attribute_budget_resets_per_element_and_counts_empty_default_bindings():
    limits = JUnitLimits(max_attributes_per_element=2)
    raw = b'''<testsuite xmlns:p="urn:p" name="suite">
    <testcase xmlns:p="urn:changed" name="first"/>
    <extension xmlns:q="urn:q" extra="value"/>
    <testcase xmlns="" name="second"/>
    </testsuite>'''
    assert [n['attributes']['name'] for n in JUnitDocument(raw, limits=limits).data['root']['children']] == [
        'first', 'second']
    with pytest.raises(XmlImportError) as caught:
        JUnitDocument(b'<testsuite xmlns="" name="second"/>',
                      limits=JUnitLimits(max_attributes_per_element=1))
    assert caught.value.reason == 'xml_attribute_limit'


def test_default_namespace_declaration_limit_rejects_the_next_binding():
    attributes = ' '.join('xmlns:p' + str(i) + '="urn:p"' for i in range(64))
    boundary = ('<testsuite ' + attributes + '/>').encode()
    assert JUnitDocument(boundary).data['ignored_attributes'] == 0
    with pytest.raises(XmlImportError) as caught:
        JUnitDocument(('<testsuite ' + attributes + ' xmlns:extra="urn:p"/>').encode())
    assert (caught.value.reason, caught.value.exit_code) == ('xml_attribute_limit', 7)


@pytest.mark.parametrize('body,total', [
    ('<testsuite><testcase name="x"/></testsuite>', 9 + 8 + 4),
    ('<testsuite><extension><testcase name="x"/></extension></testsuite>', 9 + 9 + 8 + 4),
    ('<testsuite xmlns:e="urn:e"><e:x/><e:x/></testsuite>', 9 + 7 + 7),
    ('<testsuite xmlns:e="urn:e" e:x="1" e:y="2"/>', 9 + 7 + 7),
    ('<testsuite><testcase name="é"/></testsuite>', 9 + 8 + 4),
])
def test_expanded_names_have_a_cumulative_limit_including_ignored_and_repeated_names(body, total):
    raw = body.encode()
    assert JUnitDocument(raw, limits=JUnitLimits(max_expanded_name_chars=total)).source_bytes == raw
    with pytest.raises(XmlImportError) as caught:
        JUnitDocument(raw, limits=JUnitLimits(max_expanded_name_chars=total - 1))
    assert (caught.value.reason, caught.value.exit_code) == ('xml_expanded_name_limit', 7)


def test_short_references_cannot_expand_into_unbounded_namespace_names(monkeypatch):
    prefix = '<testsuite xmlns:e="' + 'u' * 250 + '">'
    elements = ['<e:n' + str(i).zfill(4) + '/>' for i in range(4096)]
    boundary = (prefix + ''.join(elements[:-1]) + '</testsuite>').encode()
    assert JUnitDocument(boundary).data['ignored_elements'] == 4095
    raw = (prefix + ''.join(elements) + '</testsuite>').encode()
    assert len(raw) < 50000
    with no_external_access(monkeypatch), pytest.raises(XmlImportError) as caught:
        JUnitDocument(raw)
    assert (caught.value.reason, caught.value.exit_code) == ('xml_expanded_name_limit', 7)


@pytest.mark.parametrize('body', [
    '<testsuite xmlns:e="urn:' + 'x' * 253 + '"/>',
    '<testsuite xmlns:' + 'p' * 257 + '="urn:p"/>',
    '<testsuite xmlns:e="' + 'u' * 250 + '"><e:toolong/></testsuite>',
    '<testsuite xmlns:e="' + 'u' * 250 + '" e:toolong=""/>',
])
def test_namespace_expansion_cannot_evade_the_individual_name_limit(body):
    with pytest.raises(XmlImportError) as caught:
        JUnitDocument(body.encode())
    assert (caught.value.reason, caught.value.exit_code) == ('xml_name_limit', 7)


@pytest.mark.parametrize('text', ['<!DOCTYPE testsuite [<!ENTITY e "secret">]>',
    '<?xml-stylesheet href="file:///secret"?>', '<x:include href="https://example.invalid"/>'])
def test_declaration_looking_literal_data_is_not_misclassified_as_xml_structure(text, monkeypatch):
    raw = ('<testsuite><!--' + text + '--><system-out><![CDATA[' + text +
           ']]></system-out></testsuite>').encode()
    with no_external_access(monkeypatch):
        doc = JUnitDocument(raw)
    assert doc.data['root']['children'][0]['text'] == text
    assert doc.sha256 == sha256(raw).hexdigest()
    assert doc.data['evidence_created'] is doc.data['test_code_executed'] is False


@pytest.mark.parametrize('body,total', [
    ('<testsuite name="a&#x1f642;"><system-out><![CDATA[é]]></system-out></testsuite>', 3),
    ('<testsuite><!--abc--><extension name="de">f</extension></testsuite>', 6),
    ('<testsuite xmlns:e="urn:e"><e:x>a&amp;b</e:x></testsuite>', 8),
])
def test_text_budget_counts_decoded_unicode_across_all_content(body, total):
    raw = body.encode()
    assert JUnitDocument(raw, limits=JUnitLimits(max_text_chars=total)).source_bytes == raw
    with pytest.raises(XmlImportError) as caught:
        JUnitDocument(raw, limits=JUnitLimits(max_text_chars=total - 1))
    assert (caught.value.reason, caught.value.exit_code) == ('xml_text_limit', 7)


@pytest.mark.parametrize('raw,reason', [
    (b'<testsuite>' * 65 + b'</testsuite>' * 65, 'xml_depth_limit'),
    (b'<testsuite><extension>' + b'<x>' * 63 + b'</x>' * 63 +
     b'</extension></testsuite>', 'xml_depth_limit'),
    (b'<testsuite><extension>' + b'<x/>' * 9999 + b'</extension></testsuite>', 'xml_element_limit'),
    (b'<testsuite><system-out>' + b'x' * (1024 * 1024 + 1) +
     b'</system-out></testsuite>', 'xml_text_limit'),
    (b' ' * (4 * 1024 * 1024 + 1), 'xml_byte_limit'),
], ids=['known-depth', 'ignored-depth', 'ignored-elements', 'text', 'bytes'])
def test_default_safety_limits_stop_known_and_ignored_content_without_io(raw, reason, monkeypatch):
    with no_external_access(monkeypatch), pytest.raises(XmlImportError) as caught:
        JUnitDocument(raw)
    assert (caught.value.reason, caught.value.exit_code) == (reason, 7)


@pytest.mark.parametrize('encoding', ['specroad-forbidden-codec', 'cp1252', 'utf-7', 'utf8'])
def test_nonprofile_encoding_is_rejected_without_host_codec_lookup(encoding, monkeypatch):
    calls = []
    def codec_search(name):
        calls.append(name)
        return None
    raw = ('<?xml version="1.0" encoding="' + encoding + '"?><testsuite/>').encode()
    codecs.register(codec_search)
    try:
        with no_external_access(monkeypatch), pytest.raises(XmlImportError) as caught:
            JUnitDocument(raw)
    finally:
        codecs.unregister(codec_search)
    assert calls == []
    assert (caught.value.reason, caught.value.exit_code) == ('unsupported_xml_encoding', 3)
    assert encoding not in json.dumps(caught.value.diagnostic())


@pytest.mark.parametrize('declared,encoder', [
    ('UTF-8', 'utf-8'), ('uTf-8', 'utf-8-sig'), ('UTF-16', 'utf-16'),
    ('UTF-16LE', 'utf-16-le'), ('UTF-16BE', 'utf-16-be'),
    ('ISO-8859-1', 'iso-8859-1'), ('US-ASCII', 'ascii'), ('ASCII', 'ascii'),
])
def test_supported_declared_encodings_preserve_report_values_and_original_bytes(declared, encoder, monkeypatch):
    raw = ('<?xml version="1.0" encoding="' + declared +
           '"?><testsuite name="caf&#233;"/>').encode(encoder)
    with no_external_access(monkeypatch):
        document = JUnitDocument(raw)
    assert document.data['root']['attributes'] == {'name': 'café'}
    assert document.source_bytes == raw


@pytest.mark.parametrize('raw', [b'<testsuite name="unfinished',
    b'<testsuite><!--unfinished', b'<testsuite><![CDATA[unfinished',
    b'<testsuite xmlns:a="urn:p" xmlns:b="urn:p" a:x="1" b:x="2"/>',
    b'<testsuite xmlns:xml="urn:wrong"/>',
    b'<testsuite><testcase/></testsuite><bad-tail/>'])
def test_malformed_tokens_and_namespace_conflicts_never_return_partial_content(raw, monkeypatch):
    with no_external_access(monkeypatch), pytest.raises(XmlImportError) as caught:
        JUnitDocument(raw)
    assert (caught.value.reason, caught.value.exit_code) == ('invalid_xml', 3)
    assert type(caught.value.position) is int
    assert type(caught.value.line) is type(caught.value.column) is int


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_expansion_and_encoding_boundaries_are_present_in_isolated_distributions(tmp_path, mode):
    attacks = [
        (DTD_ATTACKS['exponential'].encode(), 'xml_dtd_or_entity_forbidden', {}),
        (b'<testsuite xmlns:a="urn:a" name="x"/>', 'xml_attribute_limit',
         {'max_attributes_per_element': 1}),
        (b'<testsuite><testcase/></testsuite>', 'xml_expanded_name_limit',
         {'max_expanded_name_chars': 16}),
        (b'<?xml version="1.0" encoding="specroad-forbidden-codec"?><testsuite/>',
         'unsupported_xml_encoding', {}),
    ]
    body = ('import json\nfrom specroad.verification import JUnitDocument, JUnitLimits, XmlImportError\n'
            'answers=[]\nfor raw,reason,limits in ' + repr(attacks) + ':\n'
            ' try: JUnitDocument(raw,limits=JUnitLimits(**limits))\n'
            ' except XmlImportError as error: answers.append(error.reason)\n'
            ' else: raise AssertionError("unsafe input accepted")\n'
            'print(json.dumps(answers))\n')
    if mode == 'core':
        process = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'dist')
        prefix = 'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n'
        process = run_python(['-I', '-S', '-B', '-c', prefix + body], tmp_path, capture=True)
    assert process.returncode == 0, process.stderr.decode()
    assert json.loads(process.stdout) == [reason for raw, reason, limits in attacks]
