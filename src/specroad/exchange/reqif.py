"""Passive ReqIF object facade over separate values, XML, profile and mapping.

The default is the 14.h object subset; decode_reqif_structure explicitly adds
the 14.i structure/XHTML subset. Neither is a project importer or XSD engine.
The caller supplies per-document parser bounds and owns all input/output bytes.
Uninterpreted content stays in the source; it prevents a complete export claim.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..model.numbers import number_from_token
from ..storage._xml_reader import read_bounded_xml
from . import _reqif_mapping as _mapping
from . import _reqif_structure as _structure
from ._reqif_mapping import reqif_object_identifier
from ._reqif_profile import _validate
from ._reqif_values import (
    REQIF_NAMESPACE, ReqIFDatatype, ReqIFDefinition, ReqIFError, ReqIFLimits,
    ReqIFObject, ReqIFType, ReqIFValue, _Node,
)
from ._reqif_xhtml import ReqIFAttachment, project_xhtml as _project_xhtml
from ._reqif_xml import _serialize, read_tree



def _read(raw, limits, *, structure=False):
    # Keep host-failure boundaries at the facade while event mapping stays pure.
    return read_tree(raw, limits, reader=read_bounded_xml, structure=structure)


@dataclass(frozen=True, init=False)
class ReqIFDocument:
    source_bytes: bytes
    datatypes: tuple
    types: tuple
    objects: tuple
    unsupported: tuple
    specifications: tuple
    relations: tuple
    hierarchies: tuple
    _structure: bool
    _root: _Node
    _limits: ReqIFLimits

    def __init__(self, raw, *, limits, structure=False):
        if hasattr(self, "_root"):
            raise AttributeError("ReqIFDocument is immutable")
        if type(structure) is not bool:
            raise ReqIFError('reqif_structure_mode_required', exit_code=2)
        root = _read(raw, limits, structure=structure)
        parsed = _validate(root, structure=structure)
        datatypes, types, objects, unsupported = parsed[:4]
        specifications, relations, hierarchies = parsed[4:] if structure else ((), (), ())
        for name, value in (("source_bytes", raw), ("_root", root), ("_limits", limits),
                            ("datatypes", datatypes), ("types", types), ("objects", objects), ("unsupported", unsupported),
                            ('specifications', specifications), ('relations', relations), ('hierarchies', hierarchies),
                            ('_structure', structure)):
            object.__setattr__(self, name, value)

    @property
    def source_sha256(self):
        return sha256(self.source_bytes).hexdigest()

    def __bool__(self):
        raise TypeError("A ReqIF object subset is not successful project import or write authority")

    def observation(self):
        result = {"profile": "reqif-object-profile-v1", "source_sha256": self.source_sha256,
                "object_count": len(self.objects), "validation_scope": "reqif_type_object_subset",
                "uninterpreted": [{"pointer": p, "reason": r} for p, r in self.unsupported],
                "import_complete": False, "write_authorized": False, "execution_ready": False}
        if self._structure:
            result.update(profile='reqif-structure-xhtml-v1', validation_scope='reqif_structure_xhtml_subset',
                          specification_count=len(self.specifications), relation_count=len(self.relations),
                          occurrence_count=len(self.hierarchies))
        return result

    def project_object(self, identifier):
        return _mapping.project_object(self, identifier, number_parser=number_from_token)

    def project_record(self, identifier, *, xhtml=False, attachments=()):
        """Project a typed object/specification/relation; XHTML is explicit."""
        _structure.require_structure(self)
        return _mapping.project_object(self, identifier, number_parser=number_from_token,
                                       records=_structure.records(self), xhtml=xhtml, attachments=attachments)

    def project_xhtml(self, identifier, definition_id, *, attachments=()):
        obj, definition, value = _structure.field(self, identifier, definition_id)
        if value is None:
            raise ReqIFError('reqif_xhtml_value_absent', object_id=identifier, definition_id=definition_id)
        projected = _project_xhtml(value.lexical, attachments=attachments)
        return {**projected, 'source_sha256': self.source_sha256, 'external_id': identifier,
                'definition_id': definition_id,
                'origin': 'explicit' if value in obj.values else 'default'}

    def export_xhtml(self, identifier, definition_id, markdown, *, expected_source_sha256, attachments=()):
        return _structure.export_xhtml(self, identifier, definition_id, markdown,
            expected_source_sha256=expected_source_sha256, attachments=attachments,
            decode=decode_reqif_structure, serialize=_serialize)

    def map_record(self, identifier, *, source_system, source_document, external_revision=None,
                   xhtml=False, attachments=(), **mapping_binding):
        mapping = _structure.bound_mapping(self, **mapping_binding)
        identity = _mapping._source_identity(identifier, source_system, source_document, external_revision)
        projected = self.project_record(identifier, xhtml=xhtml, attachments=attachments)
        result = {'mapping': mapping.resource.binding(), 'artifact': None, 'unmapped': {}}
        if projected['representable']:
            result = mapping.artifact(projected['external_type'], projected['fields'])
        return {**projected, **result, 'external_identity': identity, 'source_sha256': self.source_sha256,
                'mapping_complete': projected['representable'], 'import_complete': False,
                'write_authorized': False, 'execution_ready': False}

    def map_structure(self, **bindings):
        return _structure.map_structure(self, **bindings)

    def map_object(self, identifier, *, mappings, key, expected_mapping_sha256,
                   expected_source_sha256, source_system, source_document, external_revision=None):
        return _mapping.map_object(
            self, identifier, mappings=mappings, key=key,
            expected_mapping_sha256=expected_mapping_sha256,
            expected_source_sha256=expected_source_sha256, source_system=source_system,
            source_document=source_document, external_revision=external_revision)

    def export_object(self, identifier, native_fields, *, mappings, key, expected_mapping_sha256,
                      expected_source_sha256, source_system, source_document, external_revision=None):
        """Return bytes for one inverse-mapped object in the explicitly bound source.

        The existing document owns definitions, IDs and metadata. Unchanged
        effective fields retain lexical spelling, enum order and absence. This
        is neither a whole native model exporter nor a writer/approval gate.
        """
        return _mapping.export_object(
            self, identifier, native_fields, mappings=mappings, key=key,
            expected_mapping_sha256=expected_mapping_sha256,
            expected_source_sha256=expected_source_sha256, source_system=source_system,
            source_document=source_document, external_revision=external_revision,
            validate=lambda root: _validate(root, structure=self._structure), serialize=_serialize,
            decode=decode_reqif_structure if self._structure else decode_reqif)


def decode_reqif(raw, *, limits):
    return ReqIFDocument(raw, limits=limits)


def decode_reqif_structure(raw, *, limits):
    """Opt in to the passive structure/XHTML profile without import authority."""
    return ReqIFDocument(raw, limits=limits, structure=True)


def encode_reqif(document):
    """Serialize supported typed source objects, preserving absence and defaults.

    The explicit structure profile also preserves supported hierarchy/XHTML
    source. Unknown content still blocks rewriting; original bytes stay owned.
    """
    if type(document) is not ReqIFDocument:
        raise ReqIFError("reqif_document_required", exit_code=2)
    if document.unsupported:
        raise ReqIFError("reqif_uninterpreted_export", pointer=document.unsupported[0][0])
    raw = _serialize(document._root)
    _validate(_read(raw, document._limits, structure=document._structure), structure=document._structure)
    return raw
