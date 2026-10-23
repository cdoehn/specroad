"""Validate caller-owned attachment bytes and relative ReqIF references.

No XML traversal, prose conversion, filesystem access or media decoding. The
original reference remains the lookup key after exactly one URI safety check.
"""
from dataclasses import dataclass
from hashlib import sha256
import re
from urllib.parse import unquote

from ..model.attachments import AttachmentDescriptor
from ..model.errors import ModelError
from ..model.paths import project_path
from ._reqif_values import ReqIFError


def relative_reference(value):
    """Check one URI decoding, keeping the original reference as the lookup key."""
    if type(value) is not str or not value or re.search(r'%(?![0-9a-fA-F]{2})', value):
        raise ReqIFError('reqif_attachment_reference_unsafe', exit_code=7)
    try:
        decoded = unquote(value, encoding='utf-8', errors='strict')
        if (any(c in decoded for c in '\\%?#:') or decoded.startswith('/')
                or any(ord(c) < 32 or ord(c) == 127 for c in decoded)
                or any(v in ('', '.', '..') for v in decoded.split('/'))):
            raise ReqIFError('reqif_attachment_reference_unsafe', exit_code=7)
        project_path(decoded)
    except (ModelError, UnicodeError) as error:
        raise ReqIFError('reqif_attachment_reference_unsafe', exit_code=7) from error
    return decoded


@dataclass(frozen=True)
class ReqIFAttachment:
    """Caller-owned bytes bound to a relative ReqIF reference and native path."""
    reference: str
    descriptor: AttachmentDescriptor
    content: bytes

    def __post_init__(self):
        relative_reference(self.reference)
        if type(self.descriptor) is not AttachmentDescriptor or type(self.content) is not bytes:
            raise ReqIFError('reqif_attachment_binding_required', exit_code=2)
        try:
            AttachmentDescriptor.from_data(self.descriptor.data)
        except ModelError as error:
            raise ReqIFError(error.reason, exit_code=2) from error
        if not self.descriptor.path.startswith('attachments/'):
            raise ReqIFError('reqif_attachment_target_required', exit_code=7)
        if len(self.content) != self.descriptor.size or sha256(self.content).hexdigest() != self.descriptor.sha256:
            raise ReqIFError('reqif_attachment_bytes_changed', exit_code=6)


def _attachments(values):
    if type(values) not in (tuple, list):
        raise ReqIFError('reqif_attachment_bindings_required', exit_code=2)
    result, paths = {}, {}
    for value in values:
        if type(value) is not ReqIFAttachment:
            raise ReqIFError('reqif_attachment_binding_required', exit_code=2)
        value = ReqIFAttachment(value.reference, value.descriptor, value.content)
        if value.reference in result:
            raise ReqIFError('reqif_attachment_binding_ambiguous', exit_code=6)
        previous = paths.get(value.descriptor.path)
        if previous is not None and previous.descriptor != value.descriptor:
            raise ReqIFError('reqif_attachment_target_conflict', exit_code=6)
        result[value.reference] = value
        paths[value.descriptor.path] = value
    return result
