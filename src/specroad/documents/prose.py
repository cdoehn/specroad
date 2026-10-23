"""Inert, source-bound prose nodes; no renderer, loader or executable extension."""
from dataclasses import dataclass
from hashlib import sha256

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from .blocks import ContentBlock
from ._prose_parser import _Parser


class ProseError(ModelError):
    """A prose payload is outside the safe declared subset."""
    exit_code = 3


@dataclass(frozen=True, init=False)
class ProseContent:
    """Owned record bytes and detached semantic nodes, never rendering approval."""
    source_bytes: bytes
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use parse_prose with a native ContentBlock')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Parsed prose is not rendering or attachment approval')


def parse_prose(block):
    """Parse an owned prose/admonition block; do not read attachments or render."""
    if type(block) is not ContentBlock:
        raise ProseError('prose_content_block_required')
    block = ContentBlock(block.source_bytes, path=block.path)
    if block.block_kind not in ('prose', 'admonition'):
        raise ProseError('prose_block_kind_required', path=block.path, pointer='/block_kind')
    encoded, node = _parse_markdown(block.payload['markdown'], path=block.path)
    if block.block_kind == 'admonition':
        node = {**node, 'type': 'admonition', 'level': block.payload['level']}
        if 'title' in block.payload: node['title'] = block.payload['title']
    report = {'format_version': 1, 'kind': 'safe-prose-v1', 'block': block.binding,
        'normalized_markdown_sha256': sha256(encoded).hexdigest(),
        'nodes_sha256': canonical_json_sha256(node), 'content': node,
        'validation_scope': 'owned_prose_nodes', 'prose_parsed': True,
        'attachments_resolved': False, 'project_files_verified': False,
        'full_validation_passed': False, 'rendering_performed': False,
        'write_authorized': False, 'approval_granted': False}
    result = object.__new__(ProseContent)
    object.__setattr__(result, 'source_bytes', block.source_bytes)
    object.__setattr__(result, '_encoded', canonical_json_bytes(report))
    return result


def _parse_markdown(value, *, path=None):
    """Shared inert text parser; no fabricated ContentBlock or approval report."""
    parser = _Parser(path, ProseError)
    if type(value) is not str:
        parser.fail('prose_string_required')
    value = value.replace('\r\n', '\n').replace('\r', '\n')
    try:
        encoded = value.encode('utf-8')
    except UnicodeError:
        parser.fail('prose_utf8_required')
    if len(encoded) > 1_048_576: parser.fail('prose_size_limit')
    if any(ord(char) < 32 and char not in '\n\t' or ord(char) == 127 for char in value):
        parser.fail('prose_control_character_forbidden')
    parts = value.split('\n')
    lines = [part + '\n' for part in parts[:-1]] + ([parts[-1]] if parts[-1] else [])
    children = parser.blocks(lines)
    node = {'type': 'document', 'children': children}
    pending = [(node, 0)]
    while pending:
        current, depth = pending.pop()
        parser.depth(depth)
        pending.extend((child, depth + 1) for child in current.get('children', []))
    return encoded, node
