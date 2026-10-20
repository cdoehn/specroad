"""Bounded JUnit XML values, without mapping, file access or test execution.

This reader accepts one complete byte document. All XML, including ignored
extensions, passes the same structural limits. Original bytes remain available
for a later explicit attachment; successful parsing is not verified Evidence.
"""
from dataclasses import dataclass, fields
from hashlib import sha256
from xml.parsers import expat

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object


class XmlImportError(ModelError):
    code = 'SRV083'

    def __init__(self, reason, *, exit_code=3, **location):
        super().__init__(reason, **location)
        self.exit_code = exit_code

    def diagnostic(self):
        return {**super().diagnostic(), 'code': self.code, 'exit_code': self.exit_code}


@dataclass(frozen=True)
class JUnitLimits:
    """Per-document hard limits; callers may tighten, never enlarge them."""
    max_bytes: int = 4 * 1024 * 1024
    max_depth: int = 64
    max_elements: int = 10000
    max_text_chars: int = 1024 * 1024
    max_attributes_per_element: int = 64
    max_name_chars: int = 256
    max_expanded_name_chars: int = 1024 * 1024

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if type(value) is not int or not 1 <= value <= field.default:
                raise XmlImportError('invalid_xml_limits', exit_code=2)


_CHILDREN = {
    'testsuites': frozenset({'testsuite'}),
    'testsuite': frozenset({'testsuite', 'testcase', 'system-out', 'system-err'}),
    'testcase': frozenset({'failure', 'error', 'skipped', 'system-out', 'system-err'}),
    **{name: frozenset() for name in ('failure', 'error', 'skipped', 'system-out', 'system-err')},
}
_ATTRIBUTES = frozenset({'name', 'classname', 'file', 'line', 'time', 'timestamp',
                        'tests', 'failures', 'errors', 'skipped'})
_XSI = 'http://www.w3.org/2001/XMLSchema-instance'
_EXTERNAL_NAMESPACES = frozenset({'http://www.w3.org/2001/XMLSchema',
                                 'http://www.w3.org/2001/XInclude'})
_SEPARATOR = '\x1f'
# Keep declarations independent of the host's extensible codec registry.
_ENCODINGS = frozenset({'utf-8', 'utf-16', 'utf-16le', 'utf-16be',
                        'iso-8859-1', 'us-ascii', 'ascii'})


def _parse(raw, limits):
    parser = expat.ParserCreate(namespace_separator=_SEPARATOR)
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    parser.buffer_text = True
    stack, root = [], None
    elements = text_chars = ignored_elements = ignored_attributes = 0
    expanded_name_chars = namespace_declarations = 0

    def reject(reason, *, exit_code=7):
        raise XmlImportError(reason, exit_code=exit_code, position=parser.CurrentByteIndex,
                             line=parser.CurrentLineNumber, column=parser.CurrentColumnNumber)

    def forbidden(*_):
        reject('xml_dtd_or_entity_forbidden')

    def count_text(text):
        nonlocal text_chars
        text_chars += len(text)
        if text_chars > limits.max_text_chars:
            reject('xml_text_limit')

    def name_parts(name, *, expanded=False):
        nonlocal expanded_name_chars
        if len(name) > limits.max_name_chars:
            reject('xml_name_limit')
        if expanded:
            expanded_name_chars += len(name)
            if expanded_name_chars > limits.max_expanded_name_chars:
                reject('xml_expanded_name_limit')
        namespace, _, local = name.rpartition(_SEPARATOR)
        return namespace, local

    def start(name, attributes):
        nonlocal root, elements, ignored_elements, ignored_attributes
        nonlocal namespace_declarations
        elements += 1
        if elements > limits.max_elements:
            reject('xml_element_limit')
        if len(stack) >= limits.max_depth:
            reject('xml_depth_limit')
        namespace, local = name_parts(name, expanded=True)
        if namespace in _EXTERNAL_NAMESPACES:
            reject('xml_external_reference_forbidden')
        if len(attributes) + namespace_declarations > limits.max_attributes_per_element:
            reject('xml_attribute_limit')
        namespace_declarations = 0
        for key, value in attributes.items():
            ns, attr = name_parts(key, expanded=True)
            if ns == _XSI and attr in ('schemaLocation', 'noNamespaceSchemaLocation'):
                reject('xml_external_reference_forbidden')
            count_text(value)
        if not stack and name not in ('testsuites', 'testsuite'):
            reject('junit_root_required', exit_code=3)
        if name not in _CHILDREN or (stack and stack[-1] is None):
            ignored_elements += 1
            stack.append(None)
            return
        if stack and name not in _CHILDREN[stack[-1]['tag']]:
            reject('junit_element_placement', exit_code=3)
        known = {key: value for key, value in attributes.items() if key in _ATTRIBUTES}
        ignored_attributes += len(attributes) - len(known)
        node = {'tag': name, 'attributes': known, 'text': [], 'children': []}
        if stack:
            stack[-1]['children'].append(node)
        else:
            root = node
        stack.append(node)

    def end(_):
        node = stack.pop()
        if node is not None:
            node['text'] = ''.join(node['text'])

    def characters(text):
        count_text(text)
        if stack and stack[-1] is not None:
            stack[-1]['text'].append(text)

    def namespace(prefix, uri):
        nonlocal namespace_declarations
        # Namespace declarations arrive before their element's start event.
        # Count them there as well as ordinary attributes at the start event.
        namespace_declarations += 1
        if namespace_declarations > limits.max_attributes_per_element:
            reject('xml_attribute_limit')
        name_parts(prefix or '')
        name_parts(uri or '')
        count_text(uri or '')

    def declaration(version, encoding, standalone):
        if version != '1.0':
            reject('xml_version_not_supported', exit_code=3)
        if encoding is not None and encoding.lower() not in _ENCODINGS:
            reject('unsupported_xml_encoding', exit_code=3)

    def instruction(target, data):
        reject('xml_processing_instruction_forbidden')

    parser.StartDoctypeDeclHandler = forbidden
    parser.EntityDeclHandler = forbidden
    parser.ExternalEntityRefHandler = forbidden
    parser.SkippedEntityHandler = forbidden
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = characters
    parser.CommentHandler = count_text
    parser.StartNamespaceDeclHandler = namespace
    parser.XmlDeclHandler = declaration
    parser.ProcessingInstructionHandler = instruction
    try:
        # A single bounded final buffer avoids reparsing unfinished large tokens
        # on older Expat versions. Never disable the interpreter's protections.
        parser.Parse(raw, True)
    except expat.ExpatError as error:
        raise XmlImportError('invalid_xml', position=parser.ErrorByteIndex,
                             line=error.lineno, column=error.offset) from error
    except (LookupError, ValueError) as error:
        if isinstance(error, XmlImportError):
            raise
        raise XmlImportError('unsupported_xml_encoding') from error
    return {'format_version': 'junit-core-v1',
            'source': {'size': len(raw), 'sha256': sha256(raw).hexdigest()},
            'root': root, 'ignored_elements': ignored_elements,
            'ignored_attributes': ignored_attributes,
            'test_code_executed': False, 'evidence_created': False}


@dataclass(frozen=True, init=False)
class JUnitDocument:
    """An owned read result; attributes are reported strings, not trusted totals."""
    source_bytes: bytes
    _encoded: bytes

    def __init__(self, raw, *, limits=None):
        if type(raw) is not bytes:
            raise XmlImportError('xml_bytes_required')
        if limits is None:
            limits = JUnitLimits()
        if type(limits) is not JUnitLimits:
            raise XmlImportError('typed_xml_limits_required', exit_code=2)
        limits = JUnitLimits(**{field.name: getattr(limits, field.name) for field in fields(limits)})
        if len(raw) > limits.max_bytes:
            raise XmlImportError('xml_byte_limit', exit_code=7)
        value = _parse(raw, limits)
        object.__setattr__(self, 'source_bytes', raw)
        object.__setattr__(self, '_encoded', canonical_json_bytes(value))

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self.source_bytes).hexdigest()

    def __bool__(self):
        raise TypeError('Parsed JUnit is not successful verification or write authority')
