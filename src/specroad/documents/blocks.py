"""Exact passive content-block contracts, without target resolution or execution."""
from dataclasses import dataclass
from hashlib import sha256

from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from ..model.record_schemas import BLOCK_KINDS, _block_payload, record_schema
from ..model.versions import SCHEMA_VERSION
from ..storage.json_syntax import parse_json_object
from ..storage.record_artifact import RecordArtifact


def content_block_payload_schema(block_kind, version=SCHEMA_VERSION):
    """Return a detached standalone schema for one compiled-in payload kind.

    These are the existing stored-field contracts. Query evaluation, prose
    parsing, include traversal and referenced-record resolution are separate.
    """
    if type(block_kind) is not str or block_kind not in BLOCK_KINDS:
        raise ModelError('content_block_kind_not_supported', pointer='/block_kind')
    record = record_schema('content_block', version)
    return {'$schema': record['$schema'],
        '$id': 'urn:specroad:schema:' + version + ':content-block-payload:' + block_kind,
        '$defs': record['$defs'], **_block_payload()[block_kind],
        'x-specroad-validation-scope': 'content_block_payload_fields_only'}


@dataclass(frozen=True, init=False)
class ContentBlock:
    """Owned exact record bytes and their typed payload, not rendering approval."""
    source_bytes: bytes
    path: str | None
    block_kind: str

    def __init__(self, raw, *, path=None):
        record = RecordArtifact(raw, expected_type='content_block', path=path)
        # Local block cardinality/target-kind checks do not establish complete
        # relation records. Validate their stored fields without resolving them.
        SourceRelations(record.source_bytes, expected_type='content_block', path=path)
        object.__setattr__(self, 'source_bytes', record.source_bytes)
        object.__setattr__(self, 'path', record.path)
        object.__setattr__(self, 'block_kind', record.data['block_kind'])

    @property
    def data(self):
        return parse_json_object(self.source_bytes, path=self.path)

    @property
    def payload(self):
        return self.data['payload']

    @property
    def binding(self):
        data = self.data
        schema = content_block_payload_schema(self.block_kind, data['schema_version'])
        return {'artifact_id': data['id'], 'revision': data['revision'],
            'block_kind': self.block_kind, 'path': self.path,
            'source_sha256': sha256(self.source_bytes).hexdigest(),
            'record_sha256': canonical_json_sha256(data),
            'payload_sha256': canonical_json_sha256(data['payload']),
            'payload_schema_id': schema['$id'], 'payload_schema_sha256': canonical_json_sha256(schema),
            'validation_scope': 'content_block_fields_only',
            'target_references_resolved': False, 'payload_semantics_evaluated': False,
            'rendering_performed': False, 'write_authorized': False, 'approval_granted': False}

    def __bool__(self):
        raise TypeError('A readable content block is not semantic or rendering approval')
