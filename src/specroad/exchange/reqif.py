"""Passive ReqIF object facade over separate values, XML, profile and mapping.

This is the 14.h object subset, not a project importer or a general XSD engine.
The caller supplies per-document parser bounds and owns all input/output bytes.
Uninterpreted content stays in the source; it prevents a complete export claim.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..model.numbers import number_from_token
from ..storage._xml_reader import read_bounded_xml
from . import _reqif_mapping as _mapping
from ._reqif_mapping import reqif_object_identifier
from ._reqif_profile import _validate
from ._reqif_values import (
    REQIF_NAMESPACE, ReqIFDatatype, ReqIFDefinition, ReqIFError, ReqIFLimits,
    ReqIFObject, ReqIFType, ReqIFValue, _Node,
)
from ._reqif_xml import _serialize, read_tree



def _read(raw, limits):
    # Keep host-failure boundaries at the facade while event mapping stays pure.
    return read_tree(raw, limits, reader=read_bounded_xml)


@dataclass(frozen=True, init=False)
class ReqIFDocument:
    source_bytes: bytes
    datatypes: tuple
    types: tuple
    objects: tuple
    unsupported: tuple
    _root: _Node
    _limits: ReqIFLimits

    def __init__(self, raw, *, limits):
        if hasattr(self, "_root"):
            raise AttributeError("ReqIFDocument is immutable")
        root = _read(raw, limits)
        datatypes, types, objects, unsupported = _validate(root)
        for name, value in (("source_bytes", raw), ("_root", root), ("_limits", limits),
                            ("datatypes", datatypes), ("types", types), ("objects", objects), ("unsupported", unsupported)):
            object.__setattr__(self, name, value)

    @property
    def source_sha256(self):
        return sha256(self.source_bytes).hexdigest()

    def __bool__(self):
        raise TypeError("A ReqIF object subset is not successful project import or write authority")

    def observation(self):
        return {"profile": "reqif-object-profile-v1", "source_sha256": self.source_sha256,
                "object_count": len(self.objects), "validation_scope": "reqif_type_object_subset",
                "uninterpreted": [{"pointer": p, "reason": r} for p, r in self.unsupported],
                "import_complete": False, "write_authorized": False, "execution_ready": False}

    def project_object(self, identifier):
        return _mapping.project_object(self, identifier, number_parser=number_from_token)

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
            validate=_validate, serialize=_serialize, decode=decode_reqif)


def decode_reqif(raw, *, limits):
    return ReqIFDocument(raw, limits=limits)


def encode_reqif(document):
    """Serialize supported typed source objects, preserving absence and defaults.

    Full unknown/XHTML/hierarchy transport is a later integration. Original
    bytes remain available; refusing serialization cannot silently lose them.
    """
    if type(document) is not ReqIFDocument:
        raise ReqIFError("reqif_document_required", exit_code=2)
    if document.unsupported:
        raise ReqIFError("reqif_uninterpreted_export", pointer=document.unsupported[0][0])
    raw = _serialize(document._root)
    _validate(_read(raw, document._limits))
    return raw
