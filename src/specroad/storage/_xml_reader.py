"""Internal bounded XML events, independent of any import format's profile.

Trusted adapters supply their limit/error types and event consumers. XML data
cannot select those callbacks. Every event, including ignored extensions, first
passes the shared safety checks. No resolver, file I/O or result publication.
"""
from dataclasses import fields
from xml.parsers import expat


_XSI = 'http://www.w3.org/2001/XMLSchema-instance'
_EXTERNAL_NAMESPACES = frozenset({'http://www.w3.org/2001/XMLSchema',
                                 'http://www.w3.org/2001/XInclude'})
_SEPARATOR = '\x1f'
# Keep declarations independent of the host's extensible codec registry.
_ENCODINGS = frozenset({'utf-8', 'utf-16', 'utf-16le', 'utf-16be',
                      'iso-8859-1', 'us-ascii', 'ascii'})


def read_bounded_xml(raw, *, limits, limit_type, error_type, on_start, on_end, on_text):
    """Read owned bytes; give start consumers a position-bound rejection helper.

    The adapter owns format-specific structure and result assembly. This reader
    owns input validation, parser configuration, counters and error translation.
    Callbacks never receive the parser or a way to disable its protections.
    """
    if type(raw) is not bytes:
        raise error_type('xml_bytes_required')
    if limits is None:
        limits = limit_type()
    if type(limits) is not limit_type:
        raise error_type('typed_xml_limits_required', exit_code=2)
    limits = limit_type(**{field.name: getattr(limits, field.name) for field in fields(limits)})
    if len(raw) > limits.max_bytes:
        raise error_type('xml_byte_limit', exit_code=7)

    parser = expat.ParserCreate(namespace_separator=_SEPARATOR)
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    parser.buffer_text = True
    depth = elements = text_chars = expanded_name_chars = namespace_declarations = 0

    def reject(reason, *, exit_code=7):
        raise error_type(reason, exit_code=exit_code, position=parser.CurrentByteIndex,
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
        nonlocal depth, elements, namespace_declarations
        elements += 1
        if elements > limits.max_elements:
            reject('xml_element_limit')
        if depth >= limits.max_depth:
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
        on_start(name, attributes, reject)
        depth += 1

    def end(name):
        nonlocal depth
        on_end(name)
        depth -= 1

    def characters(text):
        count_text(text)
        on_text(text)

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
        raise error_type('invalid_xml', position=parser.ErrorByteIndex,
                         line=error.lineno, column=error.offset) from error
    except (LookupError, ValueError) as error:
        if isinstance(error, error_type):
            raise
        raise error_type('unsupported_xml_encoding') from error
