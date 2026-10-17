"""Passive raster attachments from the caller's already owned model bytes."""
from dataclasses import dataclass
from hashlib import sha256


MAX_RENDER_ATTACHMENT_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class RenderAttachment:
    path: str
    media_type: str
    content: bytes
    sha256: str


def resolve_render_attachment(model, path, *, source_path, error_type):
    """Bind exact resource bytes and an inert image media type, never open paths.

    Signature checks are admission checks, not an image decoder or a promise
    that arbitrary raster bytes will display. SVG/HTML/PDF are not rendered.
    """
    def fail(reason):
        raise error_type(reason, path=source_path, pointer='/payload/markdown')

    descriptor = next((item for item in model.attachment_descriptors if item.path == path), None)
    if descriptor is None:
        fail('render_attachment_provider_required')
    raw = model.source_files.get(path)
    if type(raw) is not bytes or len(raw) != descriptor.size or sha256(raw).hexdigest() != descriptor.sha256:
        fail('render_attachment_binding_mismatch')
    if len(raw) > MAX_RENDER_ATTACHMENT_BYTES:
        fail('render_attachment_size_limit')
    kind = descriptor.media_type
    if kind not in ('image/png', 'image/jpeg', 'image/gif', 'image/webp'):
        fail('render_attachment_media_provider_required')
    signatures = {
        'image/png': raw.startswith(b'\x89PNG\r\n\x1a\n'),
        'image/jpeg': raw.startswith(b'\xff\xd8\xff'),
        'image/gif': raw.startswith((b'GIF87a', b'GIF89a')),
        'image/webp': len(raw) >= 12 and raw[:4] == b'RIFF' and raw[8:12] == b'WEBP',
    }
    if not signatures[kind]:
        fail('render_attachment_signature_mismatch')
    return RenderAttachment(path, kind, raw, descriptor.sha256)
