"""Owned ReqIF object fixtures; no schema download, external tool or project."""
from xml.sax.saxutils import escape, quoteattr

from specroad.exchange import ReqIFLimits


NAMESPACE = "http://www.omg.org/spec/ReqIF/20110401/reqif.xsd"
TIME = "2026-10-23T12:00:00.125+02:00"
LIMITS = ReqIFLimits(max_bytes=8*1024*1024, max_depth=128, max_elements=100000,
                    max_text_chars=4*1024*1024, max_attributes_per_element=64,
                    max_name_chars=512, max_expanded_name_chars=8*1024*1024)


def value(family, definition, literal):
    reference = '<DEFINITION><ATTRIBUTE-DEFINITION-' + family + '-REF>' + escape(definition) + '</ATTRIBUTE-DEFINITION-' + family + '-REF></DEFINITION>'
    if family == 'ENUMERATION':
        return '<ATTRIBUTE-VALUE-ENUMERATION>' + reference + '<VALUES>' + ''.join(
            '<ENUM-VALUE-REF>' + escape(v) + '</ENUM-VALUE-REF>' for v in literal) + '</VALUES></ATTRIBUTE-VALUE-ENUMERATION>'
    return '<ATTRIBUTE-VALUE-' + family + ' THE-VALUE=' + quoteattr(literal) + '>' + reference + '</ATTRIBUTE-VALUE-' + family + '>'


def definition(family, identifier, datatype, default=None, *, multi=True):
    attrs = ' IDENTIFIER=' + quoteattr(identifier) + ' LAST-CHANGE=' + quoteattr(TIME) + ' LONG-NAME="same display name" IS-EDITABLE="false"'
    if family == 'ENUMERATION':
        attrs += ' MULTI-VALUED="' + ('true' if multi else 'false') + '"'
    text = '<ATTRIBUTE-DEFINITION-' + family + attrs + '>'
    if default is not None:
        text += '<DEFAULT-VALUE>' + value(family, identifier, default) + '</DEFAULT-VALUE>'
    return text + '<TYPE><DATATYPE-DEFINITION-' + family + '-REF>' + datatype + '</DATATYPE-DEFINITION-' + family + '-REF></TYPE></ATTRIBUTE-DEFINITION-' + family + '>'


def document(*, datatypes='', definitions='', objects='', extra='', extensions=''):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<REQ-IF xmlns="' + NAMESPACE + '" xml:lang="de">'
        '<THE-HEADER><REQ-IF-HEADER IDENTIFIER="header"><COMMENT>owned fixture</COMMENT>'
        '<CREATION-TIME>' + TIME + '</CREATION-TIME><REQ-IF-TOOL-ID>fixture</REQ-IF-TOOL-ID>'
        '<REQ-IF-VERSION>1.0</REQ-IF-VERSION><SOURCE-TOOL-ID>fixture</SOURCE-TOOL-ID><TITLE>Types</TITLE>'
        '</REQ-IF-HEADER></THE-HEADER><CORE-CONTENT><REQ-IF-CONTENT>'
        '<DATATYPES>' + datatypes + '</DATATYPES><SPEC-TYPES><SPEC-OBJECT-TYPE IDENTIFIER="type" LAST-CHANGE="' + TIME + '">'
        '<SPEC-ATTRIBUTES>' + definitions + '</SPEC-ATTRIBUTES></SPEC-OBJECT-TYPE></SPEC-TYPES>'
        '<SPEC-OBJECTS>' + objects + '</SPEC-OBJECTS>' + extra + '</REQ-IF-CONTENT></CORE-CONTENT>' + extensions + '</REQ-IF>').encode()


def datatype(family, identifier='dt', bounds=None):
    if bounds is None:
        bounds = {'STRING': ' MAX-LENGTH="4096"', 'INTEGER': ' MIN="-10000000000000000" MAX="10000000000000000"',
                  'REAL': ' MIN="-INF" MAX="INF" ACCURACY="17"'}.get(family, '')
    text = '<DATATYPE-DEFINITION-' + family + ' IDENTIFIER="' + identifier + '" LAST-CHANGE="' + TIME + '" LONG-NAME="type metadata"' + bounds + '>'
    if family == 'ENUMERATION':
        text += '<SPECIFIED-VALUES>' + ''.join('<ENUM-VALUE IDENTIFIER="' + name + '" LAST-CHANGE="' + TIME + '" LONG-NAME="label">'
                '<PROPERTIES><EMBEDDED-VALUE KEY="' + str(i) + '" OTHER-CONTENT="original"/></PROPERTIES></ENUM-VALUE>'
                for i, name in enumerate(('enum_a', 'enum_b'))) + '</SPECIFIED-VALUES>'
    return text + '</DATATYPE-DEFINITION-' + family + '>'


def spec_object(values='', *, identifier='object', type_id='type'):
    return '<SPEC-OBJECT IDENTIFIER=' + quoteattr(identifier) + ' LAST-CHANGE=' + quoteattr(TIME) + ' LONG-NAME="object name" DESC="metadata">' + '<VALUES>' + values + '</VALUES><TYPE><SPEC-OBJECT-TYPE-REF>' + type_id + '</SPEC-OBJECT-TYPE-REF></TYPE></SPEC-OBJECT>'


def one(family='STRING', literal='owned text', *, default=None, multi=True):
    return document(datatypes=datatype(family), definitions=definition(family, 'field', 'dt', default, multi=multi),
                    objects=spec_object('' if literal is None else value(family, 'field', literal)))
