"""Explicit, passive S.7 mappings for the requirement content tuple.

Callers materialize the returned resources under mappings/ and select their
exact keys and hashes through the ordinary codec/export APIs. Nothing is
installed, inferred from text, or selected as a project default here. These
three fields are a projection, not a claim to transport every native field.
"""
from ..mappings import CSVProfile, ExchangeMapping
from ..model.canonical import canonical_json_bytes
from ..model.domain_fields import NORMATIVE_FORCES
from ..model.errors import ModelError
from ..model._requirement_inputs import REQUIREMENT_CONTENT_FIELDS


def requirement_mapping(source_format):
    """Return an owned versioned mapping; ReqIFZ uses its ReqIF document mapping."""
    if type(source_format) is not str or source_format not in ('csv', 'ndjson', 'reqif'):
        raise ModelError('requirement_exchange_format', pointer='/source_format')
    reqif = source_format == 'reqif'
    return ExchangeMapping(canonical_json_bytes({
        'schema_version': '0.2.0', 'mapping_format_version': 'exchange-mapping-v1',
        'mapping_id': 'reqif-core' if reqif else source_format + '-requirement-core',
        'mapping_version': '1.0.0', 'source_format': source_format,
        'types': [{'external_type': 'specroad.requirement', 'artifact_type': 'requirement'}],
        'fields': [{'external_type': 'specroad.requirement',
                    'external_field': ('specroad.' if reqif else '') + field,
                    'target_field': field,
                    'value_map': ([{'external_value': [force], 'target_value': force}
                                   for force in NORMATIVE_FORCES]
                                  if reqif and field == 'normative_force' else None)}
                   for field in REQUIREMENT_CONTENT_FIELDS],
        'relations': [], 'hierarchies': [], 'extensions': {}}))


def requirement_csv_profile():
    """An explicit CSV profile bound to the exact core CSV mapping above."""
    return CSVProfile(canonical_json_bytes({
        'schema_version': '0.2.0', 'mapping_format_version': 'csv-profile-v1',
        'mapping_id': 'csv-requirement-profile', 'mapping_version': '1.0.0',
        'mapping': requirement_mapping('csv').binding(), 'external_type': 'specroad.requirement',
        'identity': {'column': 'id', 'kind': 'native_id'},
        'columns': [{'column': field, 'external_field': field, 'codec': {'kind': 'string'},
                     'empty_cell': 'value', 'missing_column': 'error'}
                    for field in REQUIREMENT_CONTENT_FIELDS],
        'error_policy': 'reject', 'extensions': {}}))


def _reqif_core_document(mapping, *, limits):
    """Typed first-export definitions, available only for the exact core resource.

    The fixed definition timestamp is resource metadata, not an observation of
    a project or an import. The exporter supplies native object/header times.
    Strings carry the original statement, including Markdown, without rendering.
    """
    core = requirement_mapping('reqif')
    if mapping.binding() != core.binding():
        return None
    from ._reqif_values import REQIF_NAMESPACE, _Node, _SEP
    from ._reqif_xml import _serialize
    from .reqif import decode_reqif_structure

    def node(tag, children=(), **attributes):
        return _Node(REQIF_NAMESPACE + _SEP + tag, tuple(sorted(attributes.items())), tuple(children))

    def identified(tag, identity, children=(), **attributes):
        return node(tag, children, **{'IDENTIFIER': identity, 'LAST-CHANGE': '1970-01-01T00:00:00Z',
                                      'LONG-NAME': identity, **attributes})

    text = identified('DATATYPE-DEFINITION-STRING', 'specroad.text', **{'MAX-LENGTH': '2147483647'})
    force = identified('DATATYPE-DEFINITION-ENUMERATION', 'specroad.force', (
        node('SPECIFIED-VALUES', [identified('ENUM-VALUE', value, (
            node('PROPERTIES', (node('EMBEDDED-VALUE', KEY=str(i), **{'OTHER-CONTENT': value}),)),))
            for i, value in enumerate(NORMATIVE_FORCES)]),))
    definitions = []
    for field in REQUIREMENT_CONTENT_FIELDS:
        family, datatype = ('ENUMERATION', 'specroad.force') if field == 'normative_force' else ('STRING', 'specroad.text')
        definitions.append(identified('ATTRIBUTE-DEFINITION-' + family, 'specroad.' + field, (
            node('TYPE', (node('DATATYPE-DEFINITION-' + family + '-REF', (datatype,)),)),),
            **({'MULTI-VALUED': 'false'} if family == 'ENUMERATION' else {})))
    typ = identified('SPEC-OBJECT-TYPE', 'specroad.requirement', (node('SPEC-ATTRIBUTES', definitions),))
    header = node('REQ-IF-HEADER', (
        node('CREATION-TIME', ('1970-01-01T00:00:00Z',)), node('REQ-IF-TOOL-ID', ('SpecRoad',)),
        node('REQ-IF-VERSION', ('1.0',)), node('SOURCE-TOOL-ID', ('SpecRoad',)),
        node('TITLE', ('Requirement core definitions',))), IDENTIFIER='specroad.core.header')
    root = node('REQ-IF', (node('THE-HEADER', (header,)), node('CORE-CONTENT', (
        node('REQ-IF-CONTENT', (node('DATATYPES', (text, force)), node('SPEC-TYPES', (typ,)),
                              node('SPEC-OBJECTS'))),))))
    return decode_reqif_structure(_serialize(root), limits=limits)
