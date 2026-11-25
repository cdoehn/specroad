"""Original-span rendering of an explicitly supplied ordered plan target.

This module creates candidate bytes only. The caller owns metadata policy,
reference validation and the native writer. No unchanged carrier is formatted.
"""
import re
from dataclasses import replace

from ..model.canonical import canonical_json_bytes as jcs
from ..model.errors import ModelError
from .json_syntax import parse_json_object
from .plan_markdown import parse_plan
from .plan_edits import _indented
from .plan_json_spans import metadata_edits


DERIVED = frozenset(('title', 'display_id', 'children', 'description',
                     'parent_id', 'plan_id', 'implemented'))


def _shape(header):
    match = re.match(rb'^(#{1,6}) ', header)
    if match:
        return 'heading', len(match[1])
    match = re.match(rb'^( *)- ', header)
    if match:
        return 'list', len(match[1])
    raise ModelError('plan_heading_required')


def _parent(shape, headings, lists, root):
    kind, level = shape
    if kind == 'heading':
        return next((identity for depth, identity in reversed(headings) if depth < level), root)
    if level:
        return next((identity for depth, identity in reversed(lists) if depth == level - 2), None)
    return headings[-1][1] if headings else root


def _choose(original, parent, headings, lists, root):
    if original is not None and _parent(original, headings, lists, root) == parent:
        return original
    if parent == root:
        return 'heading', 2
    for depth, identity in reversed(lists):
        if identity == parent:
            return 'list', depth + 2
    if headings and headings[-1][1] == parent:
        return 'list', 0
    for depth, identity in reversed(headings):
        if identity == parent and depth < 6:
            return 'heading', depth + 1
    raise ModelError('plan_target_order_invalid')


def _advance(shape, identity, headings, lists):
    kind, level = shape
    if kind == 'heading':
        lists.clear()
        while headings and headings[-1][0] >= level:
            headings.pop()
        headings.append((level, identity))
    else:
        while lists and lists[-1][0] >= level:
            lists.pop()
        lists.append((level, identity))


def _header(value, shape):
    kind, level = shape
    prefix = '#' * level + ' ' if kind == 'heading' else ' ' * level + '- '
    checkbox = '' if value['artifact_type'] == 'implementation_plan' else (
        '[x] ' if value['implemented'] else '[ ] ')
    for field in ('title', 'display_id'):
        if type(value[field]) is not str or '\n' in value[field] or '\r' in value[field]:
            raise ModelError('plan_text_required')
    return (prefix + checkbox + '[' + value['display_id'] + '] ' + value['title'] + '\n').encode('utf-8')


def _new(value, shape):
    indent = shape[1] + 2 if shape[0] == 'list' else 0
    fence = 'specroad-plan-v1' if value['artifact_type'] == 'implementation_plan' else 'specroad-entry-v1'
    metadata = {k: v for k, v in value.items() if k not in DERIVED}
    # A new source has a deterministic representation. Existing sections use
    # original spans, including their fence spelling and JSON token escapes.
    return _header(value, shape) + _indented('```' + fence + '\n' +
        jcs(metadata).decode('utf-8') + '\n```\n' + value['description'], indent)


def _existing(source, section, end, value, shape):
    raw = source.source_bytes
    before = section.artifact.data
    start = section.header.start
    chunk = raw[start:end]
    metadata = section.metadata.read(raw)
    old = parse_json_object(metadata)
    after = dict(old)
    for key, field in value.items():
        if key not in DERIVED or key in old:
            after[key] = field
    if set(old) - set(value):
        raise ModelError('plan_metadata_removal_requires_explicit_edit')
    edits = list(metadata_edits(section, metadata, old, after))
    from .plan_edit_values import SourceEdit
    if before['description'] != value['description']:
        edits.append(SourceEdit(section.body.start, section.body.end,
            section.body.read(raw), _indented(value['description'], section.indent)))
    same_shape = _shape(section.header.read(raw)) == shape
    if same_shape:
        for field, span in (('title', section.title), ('display_id', section.display_id),
                            ('implemented', section.checkbox)):
            if span is not None and before.get(field) != value.get(field):
                replacement = (b'x' if value[field] else b' ') if field == 'implemented' else value[field].encode('utf-8')
                edits.append(SourceEdit(span.start, span.end, span.read(raw), replacement))
    else:
        edits.append(SourceEdit(section.header.start, section.header.end,
            section.header.read(raw), _header(value, shape)))
    for edit in sorted(edits, key=lambda e: (e.start, e.end), reverse=True):
        chunk = chunk[:edit.start-start] + edit.after + chunk[edit.end-start:]
    wanted = shape[1] + 2 if shape[0] == 'list' else 0
    if wanted != section.indent:
        header, separator, rest = chunk.partition(b'\n')
        changed = []
        for line in rest.split(b'\n'):
            if line.strip(b' \t'):
                prefix = b' ' * section.indent
                if not line.startswith(prefix):
                    raise ModelError('plan_body_indent_required')
                line = b' ' * wanted + line[section.indent:]
            changed.append(line)
        chunk = header + separator + b'\n'.join(changed)
    return chunk


def render_plan_sources(sources, values, *, id_prefix, raw_targets=False):
    """Render complete desired preorder; refuse all unrequested projections.

    Existing material outside an affected heading/metadata/body span is reused.
    The optional EOF line separator becomes part of the preceding description;
    its caller must account for that projection change in the same metadata pass.
    """
    originals, preambles = {}, {}
    for source in sources:
        sections = source.sections
        preambles[sections[0].artifact.data['id']] = source.source_bytes[:sections[0].header.start]
        for index, section in enumerate(sections):
            end = sections[index + 1].header.start if index + 1 < len(sections) else len(source.source_bytes)
            originals[section.artifact.data['id']] = source, section, end
    result = []
    for group in values:
        root = group[0]['id']
        chunks = [preambles.get(root, b'')]
        headings, lists = [], []
        for index, value in enumerate(group):
            previous = originals.get(value['id'])
            original = None if previous is None else _shape(previous[1].header.read(previous[0].source_bytes))
            shape = ('heading', 1) if not index else _choose(original, value['parent_id'], headings, lists, root)
            chunk = _new(value, shape) if previous is None else _existing(*previous, value, shape)
            if chunks[-1] and not chunks[-1].endswith(b'\n'):
                chunks[-1] += b'\n'
            chunks.append(chunk)
            if index:
                _advance(shape, value['id'], headings, lists)
        from ..model.paths import artifact_path
        path = artifact_path('implementation_plan', root, id_prefix)
        raw = b''.join(chunks)
        result.append((path, raw) if raw_targets else parse_plan(raw, path=path, id_prefix=id_prefix))
    return tuple(result)
