"""Closed inert XHTML shape validation over the bounded XML reader's nodes.

Both value and original subtrees retain their source pointers. Unsupported
passive shapes remain distinct from malformed structure and safety failures.
"""
from ._reqif_attachments import relative_reference
from ._reqif_values import XHTML_NAMESPACE, ReqIFError, ReqIFXHTML, _SEP, _error

_BLOCK = {'div', 'p', 'pre', 'blockquote', 'ul', 'ol', 'hr'}
_INLINE = {'span', 'em', 'i', 'strong', 'b', 'br', 'code', 'a', 'object'}
_ATTRS = {'a': {'href', 'title'}, 'object': {'data', 'type'}}
_XML_SPACE = ' \t\r\n'


def _tag(node):
    namespace, _, local = node.name.rpartition(_SEP)
    return local if namespace == XHTML_NAMESPACE else None


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
