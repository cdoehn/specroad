"""Owned import-security inputs and fixed adapters shared by W/R cases.

Fixture bytes, bounds and error expectations retain their existing meanings.
These helpers only compose trusted test code; isolated execution and effect
traps stay in support.import_security. No input selects executable code.
"""
from dataclasses import asdict
from xml.sax.saxutils import quoteattr

from specroad.exchange import encode_reqifz
from specroad.mappings import CSVProfile, ExchangeMapping
from specroad.model.canonical import canonical_json_bytes
from specroad.verification import JUnitLimits
from support.csv_codec import column
from support.exchange_mappings import mapping_value
from support.folds import goal
from support.import_security import IMPORTS
from support.ndjson_codec import envelope
from support.reqif_objects import LIMITS, document, datatype, definition, spec_object, value, one
from test_work_archive import foreign_zip


READER_IMPORTS = IMPORTS + """
from specroad.verification import JUnitLimits
from specroad.mappings import ExternalIdentityRegistry, select_mapping
"""


TEXT = "Literal $(touch CONVERTER_RAN); https://supplier.invalid/data; 日本語 & <value>."


def input_resources(fmt):
    external_type, field = ('type', 'field') if fmt in ('reqif', 'reqifz') else ('Goal', 'Text')
    resource = ExchangeMapping(canonical_json_bytes(mapping_value(
        source_format='reqif' if fmt == 'reqifz' else fmt,
        types=[{'external_type': external_type, 'artifact_type': 'goal'}],
        fields=[{'external_type': external_type, 'external_field': field,
                 'target_field': 'statement', 'value_map': None}], relations=[], hierarchies=[])))
    profile = CSVProfile(canonical_json_bytes({
        'schema_version': '0.2.0', 'mapping_format_version': 'csv-profile-v1',
        'mapping_id': 'example:security-csv', 'mapping_version': '1.0.0',
        'mapping': resource.binding(), 'external_type': external_type,
        'identity': {'column': 'ID', 'kind': 'external_id'}, 'columns': [column('Text')],
        'error_policy': 'reject', 'extensions': {}})) if fmt == 'csv' else None
    if fmt == 'csv':
        raw = ('ID,Text\r\nexternal-1,' + TEXT + '\r\n').encode()
    elif fmt == 'ndjson':
        raw = canonical_json_bytes(envelope(goal(statement=TEXT, external_identities=[]))) + b'\n'
    else:
        raw = document(datatypes=datatype('STRING'), definitions=definition('STRING', 'field', 'dt'),
                       objects=spec_object(value('STRING', 'field', TEXT), identifier='external-1'))
        if fmt == 'reqifz':
            raw = encode_reqifz({'document.reqif': raw, 'unused.txt': b'passive only'},
                document_paths=['document.reqif'], limits=LIMITS, max_uncompressed_bytes=8*1024*1024)
    return raw, resource, profile


XML_PARSERS = ['reqif', 'reqif-structure', 'reqifz', 'junit']


XML_ATTACKS = ['public-dtd', 'parameter-entity', 'recursive-entity', 'expansion',
               'hidden-schema', 'encoded-schema', 'hidden-include', 'trailing-pi', 'host-codec']


def reader(parser, *, paths=('document.reqif',), maximum=8*1024*1024):
    calls = {
        'reqif': 'decode_reqif(raw, limits=ReqIFLimits(**bounds))',
        'reqif-structure': 'decode_reqif_structure(raw, limits=ReqIFLimits(**bounds))',
        'junit': 'JUnitDocument(raw, limits=JUnitLimits(**bounds))',
        'mapping': 'ExchangeMapping(raw)',
        'registry': 'ExternalIdentityRegistry(raw)',
        'csv-profile': 'CSVProfile(raw)',
    }
    if parser == 'reqifz':
        return ('decode_reqifz(raw, expected_sha256=sha256(raw).hexdigest(), document_paths='
                + repr(list(paths)) + ', limits=ReqIFLimits(**bounds), max_uncompressed_bytes='
                + repr(maximum) + ')')
    return calls[parser]


def wrapped(xml, parser):
    return foreign_zip([('document.reqif', xml)]) if parser == 'reqifz' else xml


def parser_bounds(parser):
    return asdict(JUnitLimits() if parser == 'junit' else LIMITS)


def hostile_xml(parser, attack):
    junit = parser == 'junit'
    root = 'testsuite' if junit else 'REQ-IF'
    xml = '<testsuite><testcase name="already parsed"/></testsuite>' if junit else one().decode()
    xml = xml.split('?>', 1)[-1].lstrip()  # The corpus supplies its own declaration/encoding.
    encoding = 'utf-8'
    if attack in XML_ATTACKS[:4]:
        if attack == 'public-dtd':
            dtd = ' PUBLIC "-//fixture//DTD//EN" "https://supplier.invalid/secret"'
        elif attack == 'parameter-entity':
            dtd = ' [<!ENTITY % e SYSTEM "file:///private/not-readable">%e;]'
            encoding = 'utf-16'
        elif attack == 'recursive-entity':
            dtd = ' [<!ENTITY e "&e;">]'
            encoding = 'utf-16-be'
        else:
            declarations = ['<!ENTITY e0 "xxxxxxxxxx">']
            for i in range(1, 10):
                declarations.append('<!ENTITY e' + str(i) + ' "' + ('&e' + str(i-1) + ';')*10 + '">')
            dtd = ' [' + ''.join(declarations) + ']'
        xml = '<!DOCTYPE ' + root + dtd + '>' + xml
        reason, code = 'xml_dtd_or_entity_forbidden', 7
    elif attack in ('hidden-schema', 'encoded-schema', 'hidden-include'):
        if attack == 'hidden-include':
            fragment = '<i:include xmlns:i="http://www.w3.org/2001/XInclude" href="file:///private/data" parse="text"/>'
        else:
            ns = 'http://www.w3.org/2001/XMLSchema-instance'
            attr, location = 'schemaLocation', 'urn:fixture https://supplier.invalid/schema'
            if attack == 'encoded-schema':
                ns = ns.replace('instance', 'instan&#99;e')
                attr, location, encoding = 'noNamespaceSchemaLocation', 'file:///private/schema', 'utf-16'
            fragment = '<foreign xmlns:x="' + ns + '" x:' + attr + '=' + quoteattr(location) + '/>'
        fragment = '<opaque xmlns="urn:foreign"><nested>' + fragment + '</nested></opaque>'
        if not junit:
            fragment = '<TOOL-EXTENSIONS>' + fragment + '</TOOL-EXTENSIONS>'
        xml = xml.replace('</' + root + '>', fragment + '</' + root + '>')
        reason, code = 'xml_external_reference_forbidden', 7
    elif attack == 'trailing-pi':
        xml += '<?xml-stylesheet href="https://supplier.invalid/converter"?>'
        reason, code = 'xml_processing_instruction_forbidden', 7
    else:
        xml = '<?xml version="1.0" encoding="x-specroad-executable"?>' + xml
        reason, code = 'unsupported_xml_encoding', 3
    return wrapped(xml.encode(encoding), parser), reason, code
