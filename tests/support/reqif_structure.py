"""Owned structure/XHTML source and explicitly bound native model fixtures."""
from hashlib import sha256
from xml.sax.saxutils import quoteattr

from specroad.exchange import ReqIFAttachment
from specroad.model.attachments import AttachmentDescriptor
from support.reqif_objects import TIME, datatype, definition, document, spec_object, value

XHTML = 'http://www.w3.org/1999/xhtml'


def hierarchy(identifier, obj='a', children=''):
    return ('<SPEC-HIERARCHY IDENTIFIER=' + quoteattr(identifier) + ' LAST-CHANGE=' + quoteattr(TIME)
            + ' LONG-NAME="occurrence metadata"><OBJECT><SPEC-OBJECT-REF>' + obj
            + '</SPEC-OBJECT-REF></OBJECT><CHILDREN>' + children + '</CHILDREN></SPEC-HIERARCHY>')


def specification(identifier='spec', children='', values=''):
    return ('<SPECIFICATION IDENTIFIER=' + quoteattr(identifier) + ' LAST-CHANGE=' + quoteattr(TIME)
            + ' DESC="spec metadata"><TYPE><SPECIFICATION-TYPE-REF>spec_type</SPECIFICATION-TYPE-REF></TYPE>'
            + '<VALUES>' + values + '</VALUES><CHILDREN>' + children + '</CHILDREN></SPECIFICATION>')


def relation(identifier='edge', source='a', target='b', values=''):
    return ('<SPEC-RELATION IDENTIFIER=' + quoteattr(identifier) + ' LAST-CHANGE=' + quoteattr(TIME)
            + ' DESC="relation metadata"><TYPE><SPEC-RELATION-TYPE-REF>rel_type</SPEC-RELATION-TYPE-REF></TYPE>'
            + '<VALUES>' + values + '</VALUES><SOURCE><SPEC-OBJECT-REF>' + source
            + '</SPEC-OBJECT-REF></SOURCE><TARGET><SPEC-OBJECT-REF>' + target + '</SPEC-OBJECT-REF></TARGET></SPEC-RELATION>')


def structured(*, children=None, relations=None):
    if children is None: children = hierarchy('h1', 'a', hierarchy('h2', 'b')) + hierarchy('h3', 'a')
    if relations is None: relations = relation()
    types = ''.join('<' + tag + ' IDENTIFIER="' + key + '" LAST-CHANGE="' + TIME + '"><SPEC-ATTRIBUTES>'
        + definition('STRING', field, 'dt', default) + '</SPEC-ATTRIBUTES></' + tag + '>'
        for tag, key, field, default in [('SPECIFICATION-TYPE', 'spec_type', 'spec_text', 'default spec'),
                                        ('SPEC-RELATION-TYPE', 'rel_type', 'rel_text', 'default relation')])
    raw = document(datatypes=datatype('STRING'), objects=spec_object(identifier='a') + spec_object(identifier='b'),
        extra='<SPEC-RELATIONS>' + relations + '</SPEC-RELATIONS><SPECIFICATIONS>'
        + specification(children=children) + specification('empty') + '</SPECIFICATIONS>')
    return raw.replace(b'</SPEC-TYPES>', types.encode() + b'</SPEC-TYPES>')


def xvalue(body, *, original=None, simplified=None):
    attrs = '' if simplified is None else ' IS-SIMPLIFIED=' + quoteattr(simplified)
    result = '<ATTRIBUTE-VALUE-XHTML' + attrs + '><DEFINITION><ATTRIBUTE-DEFINITION-XHTML-REF>field</ATTRIBUTE-DEFINITION-XHTML-REF></DEFINITION>'
    result += '<THE-VALUE><div xmlns="' + XHTML + '">' + body + '</div></THE-VALUE>'
    if original is not None:
        result += '<THE-ORIGINAL-VALUE><div xmlns="' + XHTML + '">' + original + '</div></THE-ORIGINAL-VALUE>'
    return result + '</ATTRIBUTE-VALUE-XHTML>'


def xdocument(body, *, original=None, simplified=None, default=False):
    field = definition('XHTML', 'field', 'dt')
    val = xvalue(body, original=original, simplified=simplified)
    if default:
        field = field.replace('</ATTRIBUTE-DEFINITION-XHTML>', '<DEFAULT-VALUE>' + val + '</DEFAULT-VALUE></ATTRIBUTE-DEFINITION-XHTML>')
    return document(datatypes=datatype('XHTML'), definitions=field,
                    objects=spec_object('' if default else val))


def attachment(reference='pictures/a.png', path='attachments/a.png', content=b'\x89PNG\r\n\x1a\nfixture', media_type='image/png'):
    return ReqIFAttachment(reference, AttachmentDescriptor(path, media_type, len(content), sha256(content).hexdigest()), content)
