"""Pure ReqIFZ transport with explicit documents and document-relative bytes.

Uses the shared canonical ZIP implementation and bounded ReqIF reader. The
derived manifest lives outside the ZIP. No filesystem, native target inference,
loss acceptance, extraction or project import is performed by this codec.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from types import MappingProxyType

from ..model.canonical import canonical_json_bytes
from ..storage.archive import (ArchiveError, decode_zip, encode_zip,
                               validate_portable_archive_paths as _portable_paths)
from ._reqif_attachments import relative_reference
from ._reqif_loss_inventory import _nodes
from ._reqif_values import _SEP
from ._reqif_xhtml_profile import _tag
from .reqif import ReqIFError, ReqIFLimits, decode_reqif_structure
from .reqif_loss import _URI_ATTRIBUTES


def _options(document_paths, limits, maximum):
    if type(limits) is not ReqIFLimits:
        raise ReqIFError('typed_xml_limits_required', exit_code=2)
    if type(maximum) is not int or maximum < 1:
        raise ReqIFError('invalid_archive_byte_limit', exit_code=2)
    if (type(document_paths) not in (list, tuple) or not document_paths
            or any(type(p) is not str for p in document_paths)
            or len(set(document_paths)) != len(document_paths)):
        raise ReqIFError('reqifz_document_selection_required', exit_code=2)
    try:
        _portable_paths(document_paths)
    except ArchiveError as error:
        raise ReqIFError(error.reason, exit_code=error.exit_code) from error
    return tuple(sorted(document_paths, key=lambda p: p.encode('utf-8')))


def _references(files, paths, limits):
    references = set()
    for path in paths:
        if path not in files:
            raise ReqIFError('reqifz_document_missing', exit_code=6)
        document = decode_reqif_structure(files[path], limits=limits)
        parent = path.rpartition('/')[0]
        for node, _ in _nodes(document):
            # Match the existing URI profile even in unknown/original subtrees.
            if _tag(node) in ('a', 'object'):
                required = {'href'} if _tag(node) == 'a' else {'data', 'type'}
                if not required <= node.attrs.keys():
                    raise ReqIFError('reqif_xhtml_reference_attribute_required', pointer=node.pointer)
            for name, reference in node.attributes:
                if name.rpartition(_SEP)[2].lower() not in _URI_ATTRIBUTES:
                    continue
                decoded = relative_reference(reference)
                member = parent + '/' + decoded if parent else decoded
                if member not in files:
                    raise ReqIFError('reqifz_attachment_unresolved', exit_code=6, pointer=node.pointer)
                references.add((path, reference, member))
    return [{'document_path': p, 'reference': r, 'member_path': m}
            for p, r, m in sorted(references, key=lambda row: tuple(v.encode('utf-8') for v in row))]


def encode_reqifz(payloads, *, document_paths, limits, max_uncompressed_bytes):
    """Validate explicit input and return canonical bytes without added members."""
    paths = _options(document_paths, limits, max_uncompressed_bytes)
    if (type(payloads) is not dict
            or any(type(k) is not str or type(v) is not bytes for k, v in payloads.items())):
        raise ReqIFError('reqifz_member_bytes_required', exit_code=2)
    files = dict(payloads)
    try:
        _portable_paths(tuple(files))
        if sum(map(len, files.values())) > max_uncompressed_bytes:
            raise ArchiveError('archive_byte_limit', exit_code=7)
        _references(files, paths, limits)
        return encode_zip(files, max_uncompressed_bytes=max_uncompressed_bytes)
    except ArchiveError as error:
        raise ReqIFError(error.reason, exit_code=error.exit_code) from error


def _transport_manifest_bytes(archive_sha256, files, paths, references):
    """Derive only ReqIFZ metadata from the fully validated shared ZIP result."""
    return canonical_json_bytes({
        'format_version': 'reqifz-container-v1',
        'archive_sha256': archive_sha256,
        'entries': [{'path': name, 'size': len(files[name]), 'sha256': sha256(files[name]).hexdigest()}
                    for name in sorted(files, key=lambda p: p.encode('utf-8'))],
        'documents': list(paths),
        'references': references,
    })


@dataclass(frozen=True, init=False)
class ReqIFZContainer:
    """Validated immutable source bytes, owned members and derived manifest."""
    source_bytes: bytes
    document_paths: tuple
    _files: object
    _manifest_bytes: bytes

    def __init__(self, raw, *, expected_sha256, document_paths, limits, max_uncompressed_bytes):
        paths = _options(document_paths, limits, max_uncompressed_bytes)
        if type(raw) is not bytes:
            raise ReqIFError('reqifz_bytes_required', exit_code=2)
        if type(expected_sha256) is not str or re.fullmatch('[0-9a-f]{64}', expected_sha256) is None:
            raise ReqIFError('reqifz_sha256_required', exit_code=2)
        if sha256(raw).hexdigest() != expected_sha256:
            raise ReqIFError('reqifz_archive_changed', exit_code=6)
        try:
            files = decode_zip(raw, max_uncompressed_bytes=max_uncompressed_bytes,
                               validate_paths=_portable_paths)
        except ArchiveError as error:
            raise ReqIFError(error.reason, exit_code=error.exit_code) from error
        references = _references(files, paths, limits)
        for name, value in (('source_bytes', raw), ('document_paths', paths),
                            ('_files', MappingProxyType(files)),
                            ('_manifest_bytes', _transport_manifest_bytes(
                                expected_sha256, files, paths, references))):
            object.__setattr__(self, name, value)

    @property
    def files(self):
        return dict(self._files)

    @property
    def manifest(self):
        return json.loads(self._manifest_bytes)

    @property
    def manifest_bytes(self):
        return self._manifest_bytes


def decode_reqifz(raw, *, expected_sha256, document_paths, limits, max_uncompressed_bytes):
    """Verify the full external hash and return the explicitly assessed transport."""
    return ReqIFZContainer(raw, expected_sha256=expected_sha256, document_paths=document_paths,
                          limits=limits, max_uncompressed_bytes=max_uncompressed_bytes)
