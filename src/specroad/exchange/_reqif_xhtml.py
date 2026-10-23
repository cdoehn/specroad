"""Explicit, inert XHTML/prose intersection; no filesystem, renderer or resolver."""
from dataclasses import dataclass
from hashlib import sha256
import re
import string
from urllib.parse import quote, unquote

from ..documents.prose import ProseError, _parse_markdown
from ..model.attachments import AttachmentDescriptor
from ..model.errors import ModelError
from ..model.paths import project_path
from ._reqif_values import XHTML_NAMESPACE, ReqIFError, ReqIFXHTML, _Node, _SEP, _error

_BLOCK = {'div', 'p', 'pre', 'blockquote', 'ul', 'ol', 'hr'}
_INLINE = {'span', 'em', 'i', 'strong', 'b', 'br', 'code', 'a', 'object'}
_ATTRS = {'a': {'href', 'title'}, 'object': {'data', 'type'}}
_XML_SPACE = ' \t\r\n'


def parse_markdown(markdown, *, pointer=''):
    """Keep parser budgets separate from unsupported semantic representations."""
    try:
        return _parse_markdown(markdown)
    except ProseError as error:
        limited = error.reason in {'prose_size_limit', 'prose_nesting_limit', 'prose_complexity_limit'}
        raise ReqIFError('reqif_' + error.reason if limited else 'reqif_xhtml_prose_not_representable',
                         exit_code=7 if limited else 3, pointer=pointer) from error


def _tag(node):
    namespace, _, local = node.name.rpartition(_SEP)
    return local if namespace == XHTML_NAMESPACE else None


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


def validate_xhtml(parts, simplified):
    """Validate all value/original subtrees; keep unsupported passive source."""
    if 'THE-VALUE' not in parts:
        raise ReqIFError('reqif_xhtml_value_required')
    unsupported = []

    def visit(node, *, parent=None, in_link=False):
        tag = _tag(node)
        local = node.name.rsplit(_SEP, 1)[-1].lower()
        if local in ('script', 'style', 'iframe', 'embed', 'applet', 'include'):
            raise _error('reqif_xhtml_active_content', node, exit_code=7)
        for key, val in node.attributes:
            name = key.rsplit(_SEP, 1)[-1].lower()
            if name.startswith('on'):
                raise _error('reqif_xhtml_event_attribute', node, exit_code=7)
            if name in ('href', 'data', 'src'):
                try:
                    relative_reference(val)
                except ReqIFError as error:
                    raise _error(error.reason, node, exit_code=error.exit_code) from error
            if key not in _ATTRS.get(tag, set()):
                unsupported.append((node.pointer, 'reqif_xhtml_attribute_not_representable'))
        if tag not in _BLOCK | _INLINE | {'li'}:
            unsupported.append((node.pointer, 'reqif_xhtml_element_not_representable'))
        if tag in ('a', 'object') and not ({'href'} if tag == 'a' else {'data', 'type'}) <= node.attrs.keys():
            raise _error('reqif_xhtml_reference_attribute_required', node)
        if tag == 'a' and in_link:
            raise _error('reqif_xhtml_nested_link', node)
        # An object's passive fallback may contain blocks. It remains explicitly
        # unsupported, and every descendant still undergoes safety validation.
        if tag in _BLOCK and parent in (_INLINE - {'object'}) | {'p'} or tag == 'li' and parent not in ('ul', 'ol'):
            raise _error('reqif_xhtml_element_placement', node)
        if tag in ('br', 'hr') and node.content:
            raise _error('reqif_xhtml_empty_element_required', node)
        if tag == 'code' and node.children:
            raise _error('reqif_xhtml_code_text_required', node)
        if tag == 'pre' and node.children:
            if len(node.content) != 1 or _tag(node.children[0]) != 'code':
                raise _error('reqif_xhtml_pre_text_required', node)
        if tag in ('ul', 'ol') and (not node.children or any(_tag(c) != 'li' for c in node.children)
                or any(type(c) is str and c.strip(_XML_SPACE) for c in node.content)):
            raise _error('reqif_xhtml_list_items_required', node)
        if tag == 'object' and (node.attrs.get('type') != 'image/png' or node.children):
            unsupported.append((node.pointer, 'reqif_xhtml_object_not_representable'))
        for child in node.children:
            visit(child, parent=tag, in_link=in_link or tag == 'a')

    roots = {}
    for name in ('THE-VALUE', 'THE-ORIGINAL-VALUE'):
        if name not in parts:
            continue
        wrapper = parts[name]
        if wrapper.attrs or len(wrapper.children) != 1 or any(type(c) is str and c.strip(_XML_SPACE) for c in wrapper.content):
            raise _error('reqif_xhtml_root_required', wrapper)
        root = wrapper.children[0]
        if _tag(root) not in ('div', 'p'):
            unsupported.append((root.pointer, 'reqif_xhtml_root_not_representable'))
        visit(root)
        roots[name] = root
    return ReqIFXHTML(roots['THE-VALUE'], roots.get('THE-ORIGINAL-VALUE'), simplified, tuple(unsupported))


def _text(nodes, text):
    if text:
        if nodes and nodes[-1]['type'] == 'text':
            nodes[-1]['text'] += text
        else:
            nodes.append({'type': 'text', 'text': text})


def _binding(item, bindings):
    tag = _tag(item)
    reference = item.attrs['href' if tag == 'a' else 'data']
    binding = bindings.get(reference)
    if binding is None:
        raise _error('reqif_attachment_unresolved', item)
    if tag == 'object' and (binding.descriptor.media_type != 'image/png'
            or not binding.content.startswith(b'\x89PNG\r\n\x1a\n')):
        raise _error('reqif_attachment_image_type_mismatch', item)
    return binding


def _nodes(root, bindings):
    def inline(content):
        nodes = []
        for item in content:
            if type(item) is str:
                _text(nodes, item)
                continue
            tag = _tag(item)
            if tag == 'span':
                for child in inline(item.content):
                    if child['type'] == 'text': _text(nodes, child['text'])
                    else: nodes.append(child)
            elif tag in ('em', 'i', 'strong', 'b'):
                nodes.append({'type': 'emphasis' if tag in ('em', 'i') else 'strong', 'children': inline(item.content)})
            elif tag == 'br': nodes.append({'type': 'line_break'})
            elif tag == 'code': nodes.append({'type': 'code_span', 'text': ''.join(item.content)})
            elif tag in ('a', 'object'):
                binding = _binding(item, bindings)
                children = inline(item.content) if tag == 'a' else []
                if tag == 'object': _text(children, ''.join(item.content))
                node = {'type': 'link' if tag == 'a' else 'image',
                        'attachment_path': binding.descriptor.path, 'children': children}
                if 'title' in item.attrs: node['title'] = item.attrs['title']
                nodes.append(node)
            else:
                raise _error('reqif_xhtml_element_not_representable', item)
        return nodes

    def flow(content):
        result, pending = [], []
        structural = any(type(c) is _Node and _tag(c) in _BLOCK for c in content) and all(
            type(c) is _Node and _tag(c) in _BLOCK or type(c) is str and not c.strip(_XML_SPACE) for c in content)

        def flush():
            children = inline(pending)
            if children: result.append({'type': 'paragraph', 'children': children})
            pending.clear()

        for item in content:
            if type(item) is str or _tag(item) in _INLINE:
                if not (structural and type(item) is str): pending.append(item)
                continue
            flush()
            tag = _tag(item)
            if tag == 'div': result.extend(flow(item.content))
            elif tag == 'p':
                children = inline(item.content)
                if children: result.append({'type': 'paragraph', 'children': children})
            elif tag == 'pre':
                text = ''.join(item.children[0].content if item.children else item.content)
                result.append({'type': 'code_block', 'text': text, 'info': ''})
            elif tag == 'hr': result.append({'type': 'thematic_break'})
            elif tag == 'blockquote': result.append({'type': 'block_quote', 'children': flow(item.content)})
            elif tag in ('ul', 'ol'):
                node = {'type': 'bullet_list' if tag == 'ul' else 'ordered_list',
                        'children': [{'type': 'list_item', 'children': flow(c.content)} for c in item.children]}
                if tag == 'ol': node['start'] = 1
                result.append(node)
            else: raise _error('reqif_xhtml_element_not_representable', item)
        flush()
        return result

    return {'type': 'document', 'children': flow(root.content) if _tag(root) == 'div' else flow((root,))}


def _escape(text):
    return ''.join('\\' + char if char in string.punctuation else char for char in text)


def _markdown(node):
    kind = node['type']
    children = node.get('children', [])
    if kind == 'text': return _escape(node['text'])
    if kind == 'line_break': return '\\\n'
    if kind in ('emphasis', 'strong'):
        mark = '*' if kind == 'emphasis' else '**'
        return mark + ''.join(_markdown(c) for c in children) + mark
    if kind == 'code_span':
        text = node['text']; mark = '`' * (max((len(v) for v in re.findall(r'`+', text)), default=0) + 1)
        pad = ' ' if text.strip(' ') and (text.startswith(('`', ' ')) or text.endswith(('`', ' '))) else ''
        return mark + pad + text + pad + mark
    if kind in ('link', 'image'):
        title = ' "' + _escape(node['title']) + '"' if 'title' in node else ''
        return ('!' if kind == 'image' else '') + '[' + ''.join(_markdown(c) for c in children) + '](' + quote(node['attachment_path'], safe='/') + title + ')'
    if kind == 'paragraph': return ''.join(_markdown(c) for c in children)
    if kind == 'thematic_break': return '---'
    if kind == 'code_block':
        text = node['text']; mark = '`' * max(3, max((len(v) for v in re.findall(r'`+', text)), default=0) + 1)
        return mark + '\n' + text + ('' if not text or text.endswith('\n') else '\n') + mark
    if kind in ('document', 'list_item'):
        return '\n\n'.join(_markdown(c) for c in children)
    if kind == 'block_quote':
        return '\n'.join('> ' + line for line in '\n\n'.join(_markdown(c) for c in children).split('\n'))
    if kind in ('bullet_list', 'ordered_list'):
        items = []
        for i, child in enumerate(children):
            prefix = str(i + node.get('start', 1)) + '. ' if kind == 'ordered_list' else '- '
            lines = _markdown(child).split('\n')
            items.append(prefix + lines[0] + ''.join('\n' + ' ' * len(prefix) + v for v in lines[1:]))
        return '\n'.join(items)
    raise ReqIFError('reqif_xhtml_node_not_representable')


def project_xhtml(value, *, attachments=()):
    bindings = _attachments(attachments)
    if type(value) is not ReqIFXHTML:
        raise ReqIFError('reqif_xhtml_value_required', exit_code=2)
    if value.unsupported:
        raise ReqIFError(value.unsupported[0][1], pointer=value.unsupported[0][0])
    if value.simplified:
        raise _error('reqif_xhtml_source_simplified', value.value)
    # The original is retained, not substituted, but its references must be
    # bound too before a field can be called fully representable.
    if value.original is not None:
        pending = [value.original]
        while pending:
            item = pending.pop()
            if _tag(item) in ('a', 'object'):
                _binding(item, bindings)
            pending.extend(reversed(item.children))
    expected = _nodes(value.value, bindings)
    markdown = _markdown(expected)
    _, actual = parse_markdown(markdown, pointer=value.value.pointer)
    if actual != expected:
        raise _error('reqif_xhtml_prose_roundtrip_loss', value.value)
    return {'markdown': markdown, 'content': actual,
            'attachments': [b.descriptor.data for b in bindings.values()],
            'media_decoded': False, 'import_complete': False, 'write_authorized': False}


def from_markdown(markdown, *, attachments=()):
    """Inverse over the actual native parser, not markdown text substitution."""
    bindings = _attachments(attachments)
    _, document = parse_markdown(markdown)

    def element(tag, content=(), attrs=()):
        return _Node(XHTML_NAMESPACE + _SEP + tag, tuple(attrs), tuple(content))

    def convert(node):
        kind = node['type']
        if kind == 'text': return node['text']
        if kind in ('link', 'image'):
            matches = [v for v in bindings.values() if v.descriptor.path == node['attachment_path']]
            if len(matches) != 1:
                raise ReqIFError('reqif_attachment_inverse_ambiguous', exit_code=6)
            binding = matches[0]
            if kind == 'image':
                if ('title' in node or any(c['type'] != 'text' for c in node['children'])
                        or binding.descriptor.media_type != 'image/png'
                        or not binding.content.startswith(b'\x89PNG\r\n\x1a\n')):
                    raise ReqIFError('reqif_xhtml_inverse_not_representable', exit_code=6)
                return element('object', [c['text'] for c in node['children']], [('data', binding.reference), ('type', 'image/png')])
            attrs = [('href', binding.reference)]
            if 'title' in node: attrs.append(('title', node['title']))
            return element('a', [convert(c) for c in node['children']], attrs)
        if kind == 'code_span': return element('code', (node['text'],))
        if kind == 'code_block':
            if node['info']: raise ReqIFError('reqif_xhtml_code_info_not_representable', exit_code=6)
            return element('pre', (node['text'],))
        if kind == 'ordered_list' and node['start'] != 1:
            raise ReqIFError('reqif_xhtml_list_start_not_representable', exit_code=6)
        tags = {'document': 'div', 'paragraph': 'p', 'emphasis': 'em', 'strong': 'strong',
                'line_break': 'br', 'thematic_break': 'hr', 'block_quote': 'blockquote',
                'bullet_list': 'ul', 'ordered_list': 'ol', 'list_item': 'li'}
        if kind not in tags: raise ReqIFError('reqif_xhtml_node_not_representable', exit_code=6)
        return element(tags[kind], [convert(c) for c in node.get('children', [])])

    root = convert(document)
    checked = project_xhtml(ReqIFXHTML(root, None, False, ()), attachments=attachments)
    if checked['content'] != document:
        raise ReqIFError('reqif_xhtml_inverse_roundtrip_loss', exit_code=6)
    return root
