"""Owned cross-format corpus, explicit profiles and synthetic review history.

CSV uses one declared type/profile per stream. ReqIF uses its actual scalar,
XHTML, relation and occurrence intersection; omitted native records are losses.
These fixtures do not authenticate a human or authorize a project import.
"""
from hashlib import sha256

from specroad.exchange import decode_ndjson, merge_reqif_source, select_csv_profile
from specroad.mappings import CSVProfile, ExchangeMapping, ExternalIdentityRegistry, select_mapping
from specroad.model.attachments import AttachmentDescriptor
from specroad.model.canonical import canonical_json_bytes
from specroad.validation import ModelDocument
from support.domain import domain_value, relation
from support.exchange_mappings import mapping_value, registry_value
from support.records import record_value, ref
from support.reqif_objects import TIME, LIMITS, datatype, definition, document
from support.targets import model
from test_relation_review_status import review


CONTEXT = {'source_system': 'roundtrip-fixture', 'source_document': 'explicit-corpus',
           'external_revision': None}
FORMATS = ('csv', 'ndjson', 'reqif', 'reqifz')
LANGUAGES = ('de-DE', 'en-IN', 'zh-Hant-TW')
REQIF_FIELDS = {
    'requirement': ('id', 'title', 'revision', 'statement', 'language', 'normative_force'),
    'goal': ('id', 'title', 'revision', 'statement'),
    'document': ('id', 'title', 'revision', 'language', 'purpose'),
    'section': ('id', 'title', 'revision'),
    'content_block': ('id', 'title', 'revision', 'block_kind'),
}


def external(identity):
    return {**{k: CONTEXT[k] for k in ('source_system', 'source_document')}, 'external_id': identity}


def edge(kind, target, token, identity, **extra):
    return {**relation(kind, target), 'relation_id': 'REL-' + token * 26,
            'external_identities': [external(identity)], **extra}


def reqif_resources():
    types, fields = [], []
    for kind, names in REQIF_FIELDS.items():
        definitions = ''
        for name in names:
            family = 'INTEGER' if name == 'revision' else 'XHTML' if (kind, name) == ('requirement', 'statement') else 'STRING'
            definitions += definition(family, kind + '.' + name, 'dt.' + family)
            fields.append({'external_type': kind, 'external_field': kind + '.' + name,
                           'target_field': name, 'value_map': None})
        tag = 'SPECIFICATION-TYPE' if kind == 'document' else 'SPEC-OBJECT-TYPE'
        types.append('<' + tag + ' IDENTIFIER="' + kind + '" LAST-CHANGE="' + TIME
                     + '"><SPEC-ATTRIBUTES>' + definitions + '</SPEC-ATTRIBUTES></' + tag + '>')
    types.append('<SPEC-RELATION-TYPE IDENTIFIER="addresses" LAST-CHANGE="' + TIME
                 + '"><SPEC-ATTRIBUTES/></SPEC-RELATION-TYPE>')
    raw = document(datatypes=''.join(datatype(family, 'dt.' + family)
                                    for family in ('STRING', 'INTEGER', 'XHTML')))
    raw = raw.replace(b'</SPEC-TYPES>', ''.join(types).encode() + b'</SPEC-TYPES>')
    mapping = ExchangeMapping(canonical_json_bytes(mapping_value(mapping_id='roundtrip:reqif',
        types=[{'external_type': k, 'artifact_type': k} for k in REQIF_FIELDS], fields=fields,
        relations=[{'external_type': 'addresses', 'relation_type': 'addresses', 'direction': 'forward'}],
        hierarchies=[{'external_type': k, 'relation_type': 'contains', 'direction': 'parent_to_child'}
                     for k in ('section', 'content_block')])))
    entries = [{'object_class': kind, **external(identity), 'external_revision': None, 'data': {}, 'extensions': {}}
               for kind, identity in (('hierarchy', 'section-use'), ('hierarchy', 'first-block'),
                                     ('hierarchy', 'second-block'), ('relation', 'addresses-goal'))]
    registry = ExternalIdentityRegistry(canonical_json_bytes(registry_value(mapping,
        mapping_id='roundtrip:identities', entries=entries)))
    return raw, mapping, registry


def corpus(language='de-DE', *, nullable=False):
    image_bytes = b'\x89PNG\r\n\x1a\nowned-roundtrip-image\x00\xff'
    note_bytes = 'e\u0301 é 日本語 العربية\r\n'.encode()
    attachments = tuple(AttachmentDescriptor(path, media, len(raw), sha256(raw).hexdigest())
        for path, media, raw in (('attachments/roundtrip.png', 'image/png', image_bytes),
                                ('attachments/notes.txt', 'text/plain', note_bytes)))
    files = [ModelDocument(a.path, raw) for a, raw in zip(attachments, (image_bytes, note_bytes))]
    goal = domain_value('goal', title='Goal é e\u0301', statement='Explicit destination.')
    requirement = domain_value('requirement', language=language, normative_force='must_not',
        title='Requirement 日本語', statement='Safe content\n\n![diagram](attachments/roundtrip.png)',
        relations=[edge('addresses', goal['id'], '0', 'addresses-goal')])
    doc = record_value('document', relations=[edge('contains', ref('SEC'), '1', 'section-use', position=0)])
    section = record_value('section', relations=[
        edge('contains', ref('BLOCK'), '2', 'second-block', position=9),
        edge('contains', ref('BLOCK', '1'), '3', 'first-block', position=3)])
    blocks = [record_value('content_block', title='Second', payload={'markdown': 'Second paragraph'}),
              record_value('content_block', id=ref('BLOCK', '1'), title='First', payload={'markdown': 'First paragraph'})]
    configuration = record_value('configuration', name='Explicit Linux configuration')
    if nullable:
        configuration['parent'] = None
    evidence = record_value('evidence', attachments=[a.data for a in attachments])
    records = [requirement, goal, doc, section, *blocks, configuration, evidence]
    for i, value in enumerate(records):
        value['external_identities'] = [external('record-' + str(i))]
        value['extensions'] = {'fixture.passive': {'text': 'e\u0301 é العربية',
            'ordered': [None, False, 0, '', [], {}, ['a', 'a']], 'optional': None}}
    raw, _, _ = reqif_resources()
    doc['extensions'] = merge_reqif_source(raw, source_context=CONTEXT,
        expected_source_sha256=sha256(raw).hexdigest(), extensions=doc['extensions'],
        expected_extensions_sha256=sha256(canonical_json_bytes(doc['extensions'])).hexdigest(), limits=LIMITS)
    records.append(review(requirement, goal))
    return records, attachments, files


def csv_resources(records, kind):
    fields = sorted(set().union(*(set(v) for v in records if v['artifact_type'] == kind)) - {'id', 'artifact_type'})
    mapping = ExchangeMapping(canonical_json_bytes(mapping_value(mapping_id='roundtrip:csv-' + kind,
        source_format='csv', types=[{'external_type': kind, 'artifact_type': kind}],
        fields=[{'external_type': kind, 'external_field': field, 'target_field': field, 'value_map': None}
                for field in fields], relations=[], hierarchies=[])))
    profile = CSVProfile(canonical_json_bytes({
        'schema_version': '0.2.0', 'mapping_format_version': 'csv-profile-v1',
        'mapping_id': 'roundtrip:csv-profile-' + kind, 'mapping_version': '1.0.0',
        'mapping': mapping.binding(), 'external_type': kind,
        'identity': {'column': 'id', 'kind': 'native_id'},
        'columns': [{'column': f, 'external_field': f, 'codec': {'kind': 'typed-json-v1'},
                     'empty_cell': 'error', 'missing_column': 'error'} for f in fields],
        'error_policy': 'reject', 'extensions': {}}))
    return mapping, profile


def export_model(records, attachments, files, fmt, *, kind='requirement'):
    options = {'output_format': fmt, 'include_attachments': True}
    extra = []
    if fmt == 'csv':
        mapping, profile = csv_resources(records, kind)
        extra.append(ModelDocument('mappings/profile.json', profile.source_bytes))
        options.update(csv_profile_key=profile.key, expected_csv_profile_sha256=profile.sha256)
    elif fmt == 'ndjson':
        mapping = ExchangeMapping(canonical_json_bytes(mapping_value(mapping_id='roundtrip:ndjson',
            source_format='ndjson', fields=[], relations=[], hierarchies=[])))
        profile = None
    else:
        _, mapping, registry = reqif_resources()
        extra.append(ModelDocument('mappings/identities.json', registry.source_bytes))
        options['reqif_limits'] = LIMITS
        if fmt == 'reqifz':
            options['max_archive_bytes'] = 20 * 1024 * 1024
        profile = None
    extra.append(ModelDocument('mappings/exchange.json', mapping.source_bytes))
    options.update(mapping_key=mapping.key, expected_mapping_sha256=mapping.sha256)
    return model(records, resource_files=[*files, *extra], attachments=attachments), mapping, profile, options


def decode_native_records(exported, mapping, profile, fmt):
    """Decode only actual transport bytes using the explicitly selected profile."""
    if fmt == 'ndjson':
        return [item['object'] for item in decode_ndjson(exported.output_bytes).objects]
    assert fmt == 'csv'
    codec = select_csv_profile([mapping, profile], key=profile.key, expected_sha256=profile.sha256)
    selected = select_mapping([mapping], key=mapping.key, expected_sha256=mapping.sha256)
    return [{**selected.artifact(row['external_type'], row['fields'])['artifact'],
             'id': row['identity']['value']} for row in codec.decode(exported.output_bytes).records]
