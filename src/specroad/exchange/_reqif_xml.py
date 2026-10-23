"""ReqIF XML event/tree conversion and deterministic serialization only.

The caller supplies the existing bounded XML reader. No mapping, filesystem
access or external resolver is introduced by this transport layer.
"""
from ._reqif_values import REQIF_NAMESPACE, XHTML_NAMESPACE, ReqIFError, ReqIFLimits, _Node, _SEP, _XML


def read_tree(raw, limits, *, reader, structure=False):
    if type(limits) is not ReqIFLimits:
        raise ReqIFError("typed_xml_limits_required", exit_code=2)
    stack, roots = [], []

    def start(name, attributes, reject):
        if structure:
            # Inspect every event, including deferred extensions and originals.
            from ._reqif_attachments import relative_reference
            local = name.rsplit(_SEP, 1)[-1].lower()
            if local in ('script', 'style', 'iframe', 'embed', 'applet', 'include'):
                reject('reqif_xhtml_active_content')
            for key, value in attributes.items():
                attr = key.rsplit(_SEP, 1)[-1].lower()
                if attr.startswith('on'):
                    reject('reqif_xhtml_event_attribute')
                if attr in ('href', 'src', 'data', 'action', 'formaction', 'codebase', 'archive', 'poster'):
                    try:
                        relative_reference(value)
                    except ReqIFError as error:
                        reject(error.reason, exit_code=error.exit_code)
        pointer = (stack[-1][3] if stack else "") + "/" + name.rsplit(_SEP, 1)[-1]
        if stack:
            pointer += "[" + str(stack[-1][4]) + "]"
            stack[-1][4] += 1
        stack.append([name, tuple(sorted(attributes.items())), [], pointer, 0])

    def end(_):
        name, attrs, content, pointer, _ = stack.pop()
        node = _Node(name, attrs, tuple(content), pointer)
        (stack[-1][2] if stack else roots).append(node)

    def text(value):
        if stack:
            stack[-1][2].append(value)

    reader(raw, limits=limits, limit_type=ReqIFLimits, error_type=ReqIFError,
           on_start=start, on_end=end, on_text=text)
    if len(roots) != 1 or roots[0].tag != "REQ-IF":
        raise ReqIFError("reqif_root_required", pointer="/")
    return roots[0]


def _escape(value, *, attribute=False):
    value = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\r", "&#13;")
    return value.replace('"', "&quot;").replace("\t", "&#9;").replace("\n", "&#10;") if attribute else value


def _serialize(root):
    # Known ReqIF + xml:lang only. Unknown namespace-bearing payload is never
    # rewritten under guessed prefix bindings; the document retains its bytes.
    def name(value):
        namespace, _, local = value.rpartition(_SEP)
        if not namespace or namespace == REQIF_NAMESPACE:
            return local
        if namespace == _XML:
            return "xml:" + local
        if namespace == XHTML_NAMESPACE:
            return "xhtml:" + local
        raise ReqIFError("reqif_uninterpreted_namespace")

    pending, xhtml = [root], False
    while pending:
        node = pending.pop()
        xhtml = xhtml or node.name.startswith(XHTML_NAMESPACE + _SEP)
        pending.extend(node.children)

    def emit(node, *, first=False, mixed=False):
        attrs = [('xmlns', REQIF_NAMESPACE)] if first else []
        if first and xhtml:
            attrs.append(('xmlns:xhtml', XHTML_NAMESPACE))
        attrs += [(name(k), v) for k, v in node.attributes]
        opening = "<" + name(node.name) + "".join(' ' + k + '="' + _escape(v, attribute=True) + '"' for k, v in sorted(attrs)) + ">"
        # Preserve scalar text and mixed content; discard only structural
        # indentation between elements so already canonical output is stable.
        content = node.content
        mixed = mixed or node.name.startswith(XHTML_NAMESPACE + _SEP)
        if not mixed and node.children and all(type(x) is _Node or not x.strip(' \t\r\n') for x in content):
            content = node.children
        return opening + "".join(emit(x, mixed=mixed) if type(x) is _Node else _escape(x) for x in content) + "</" + name(node.name) + ">"
    return ('<?xml version="1.0" encoding="UTF-8"?>\n' + emit(root, first=True) + "\n").encode("utf-8")
