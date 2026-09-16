"""Read-only attachment verification; bytes are never copied into the project."""

import os

from ..model.attachments import AttachmentDescriptor
from ..model.errors import ModelError
from ..model.paths import PathClass, project_path
from ..security.resource_access import opened_resource
from .project import ProjectSource
from .byte_binding import ByteFingerprint, fingerprint_reader, validate_block_size


def fingerprint_file(boundary, path, *, block_size=65536):
    """Bind a guarded descriptor to the shared bounded-memory byte hasher."""
    validate_block_size(block_size)  # Reject invalid requests before file access.
    with opened_resource(boundary, project_path(path)) as (descriptor, initial):
        observed = fingerprint_reader(lambda size: os.read(descriptor, size),
                                      initial.st_size, block_size=block_size)
    return observed


def inspect_attachment(source, path, media_type):
    """Observe size/hash, with an explicitly supplied (not sniffed) media type."""
    if not isinstance(source, ProjectSource):
        raise TypeError("A bound ProjectSource is required")
    path = project_path(path)
    AttachmentDescriptor(path, media_type, 0, "0" * 64)
    source.check_current()
    if source.classify(path) is not PathClass.ATTACHMENT:
        raise ModelError("not_attachment_path", path=path)
    observed = fingerprint_file(source.boundary, path)
    source.check_current()
    return AttachmentDescriptor(path, media_type, observed.size, observed.sha256)


def verify_attachment(source, descriptor):
    """Return the bound declaration only after matching the actual bytes."""
    if not isinstance(descriptor, AttachmentDescriptor):
        raise TypeError("An AttachmentDescriptor is required")
    actual = inspect_attachment(source, descriptor.path, descriptor.media_type)
    if actual.size != descriptor.size:
        raise ModelError("attachment_size_mismatch", path=descriptor.path)
    if actual.sha256 != descriptor.sha256:
        raise ModelError("attachment_hash_mismatch", path=descriptor.path)
    return actual


def verify_attachments(source, descriptors):
    if isinstance(descriptors, (str, bytes, dict)):
        raise ModelError("attachment_sequence_required")
    try:
        descriptors = tuple(descriptors)
    except TypeError as error:
        raise ModelError("attachment_sequence_required") from error
    if any(not isinstance(value, AttachmentDescriptor) for value in descriptors):
        raise ModelError("invalid_attachment_descriptor")
    names = [value.path for value in descriptors]
    if len(set(names)) != len(names):
        raise ModelError("duplicate_attachment")
    if len({name.casefold() for name in names}) != len(names):
        raise ModelError("attachment_path_collision")
    result = tuple(verify_attachment(source, value) for value in sorted(descriptors, key=lambda value: value.path))
    # Check earlier members again; never publish a partially verified tuple.
    for value in result:
        verify_attachment(source, value)
    source.check_current()
    return result
