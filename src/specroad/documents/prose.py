"""Inert, source-bound prose nodes; no renderer, loader or executable extension."""
from dataclasses import dataclass
from hashlib import sha256
import html
import re
import string
import unicodedata
from urllib.parse import unquote

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.paths import project_path
from ..storage.json_syntax import parse_json_object
from .blocks import ContentBlock


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


_FENCE = re.compile(r'^( {0,3})(`{3,}|~{3,})(.*)$')
_LIST = re.compile(r'^( {0,3})([-+*]|[0-9]{1,9}[.)])(?:([ \t]+)(.*)|$)')
_QUOTE = re.compile(r'^ {0,3}>[ \t]?(.*)$')
_ENTITY = re.compile(r'&(?:#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6}|[A-Za-z][A-Za-z0-9]*);')


def _thematic(line):
    stripped = line.strip(' \t')
    return (len(line) - len(line.lstrip(' ')) <= 3 and bool(stripped)
        and stripped[0] in '*-_' and len(stripped.replace(' ', '').replace('\t', '')) >= 3
        and not set(stripped).difference({stripped[0], ' ', '\t'}))


def _text(nodes, value):
    if not value:
        return
    if nodes and nodes[-1].get('type') == 'text':
        nodes[-1]['text'] += value
    else:
        nodes.append({'type': 'text', 'text': value})


def _punctuation(char):
    return bool(char) and (char in string.punctuation or unicodedata.category(char)[0] in 'PS')


class _Parser:
    def __init__(self, path):
        self.path = path
        self.remaining = 2_000_000

    def fail(self, reason):
        raise ProseError(reason, path=self.path, pointer='/payload/markdown')

    def depth(self, value):
        if value > 64:
            self.fail('prose_nesting_limit')

    def work(self, amount=1):
        self.remaining -= amount
        if self.remaining < 0:
            self.fail('prose_complexity_limit')

    def explicit_container_end(self, lines, index):
        # The first usable subset requires explicit continuation indentation
        # or quote markers. Refuse an ambiguous lazy continuation instead of
        # silently assigning it to a different semantic container.
        if index >= len(lines): return
        line = lines[index].rstrip('\n')
        if (line.strip(' \t') and not (self.fence(line) or _LIST.match(line)
                or _QUOTE.match(line) or _thematic(line)
                or re.match(r'^ {0,3}#{1,6}(?:[ \t]|$)', line))):
            self.fail('prose_lazy_continuation_not_supported')

    def plain(self, value):
        """Decode text escapes once, with entities unable to introduce markup."""
        def entity(match):
            decoded = html.unescape(match[0])
            if any(char in '<>' or ord(char) < 32 or ord(char) == 127 for char in decoded):
                self.fail('prose_active_entity')
            return decoded
        value = _ENTITY.sub(entity, value)
        return re.sub(r'\\([' + re.escape(string.punctuation) + r'])', r'\1', value)

    def attachment(self, value):
        value = self.plain(value)
        try:
            value = unquote(value, encoding='utf-8', errors='strict')
            # A path node is not a URL. No query, fragment, double decoding or
            # alternate root interpretation can survive into the node value.
            if any(char in value for char in '%?#') or not value.startswith('attachments/'):
                self.fail('prose_attachment_path_required')
            return project_path(value)
        except (ModelError, UnicodeError) as error:
            if isinstance(error, ProseError):
                raise
            self.fail('prose_attachment_path_required')

    def fence(self, line):
        match = _FENCE.match(line)
        if match and (match[2][0] != '`' or '`' not in match[3]):
            return match
        return None

    def blocks(self, lines, depth=0):
        self.depth(depth)
        nodes = []; index = 0
        while index < len(lines):
            raw = lines[index]; line = raw.rstrip('\n')
            if not line.strip(' \t'):
                index += 1; continue
            fence = self.fence(line)
            if fence:
                indent, marker, info = fence.groups(); index += 1; content = []
                closer = re.compile(r'^ {0,3}' + re.escape(marker[0]) + '{' + str(len(marker)) + r',}[ \t]*$')
                while index < len(lines) and not closer.match(lines[index].rstrip('\n')):
                    part = lines[index]
                    trim = min(len(indent), len(part) - len(part.lstrip(' ')))
                    content.append(part[trim:]); index += 1
                if index < len(lines): index += 1
                nodes.append({'type': 'code_block', 'text': ''.join(content),
                              'info': self.plain(info.strip(' \t'))})
                continue
            if re.match(r'^ {0,3}#{1,6}(?:[ \t]|$)', line):
                self.fail('prose_heading_forbidden')
            if re.match(r'^ {0,3}\[[^\]]+\]:', line):
                self.fail('prose_reference_definition_forbidden')
            if _thematic(line):
                nodes.append({'type': 'thematic_break'}); index += 1; continue
            quote = _QUOTE.match(line)
            if quote:
                quoted = []
                while index < len(lines):
                    match = _QUOTE.match(lines[index].rstrip('\n'))
                    if not match: break
                    quoted.append(match[1] + ('\n' if lines[index].endswith('\n') else ''))
                    index += 1
                nodes.append({'type': 'block_quote', 'children': self.blocks(quoted, depth + 1)})
                self.explicit_container_end(lines, index)
                continue
            listing = _LIST.match(line)
            if listing:
                marker = listing[2]; ordered = marker[0].isdigit(); items = []
                kind = marker[-1] if ordered else marker
                while index < len(lines):
                    item = _LIST.match(lines[index].rstrip('\n'))
                    if (not item or _thematic(lines[index].rstrip('\n'))
                            or item[2][0].isdigit() != ordered or item[2][-1] != kind):
                        break
                    padding = item[3] or ' '
                    width = len(item[1]) + len(item[2]) + len(padding.expandtabs(4))
                    if '\t' in padding or len(padding) > 4:
                        self.fail('prose_list_indentation_not_supported')
                    content = [(item[4] or '') + ('\n' if lines[index].endswith('\n') else '')]
                    index += 1
                    while index < len(lines):
                        part = lines[index]
                        if not part.strip(' \t\n'):
                            # Blank lines belong to the item only when a next
                            # indented block or peer item actually follows.
                            probe = index + 1
                            while probe < len(lines) and not lines[probe].strip(' \t\n'): probe += 1
                            if probe == len(lines): break
                            if lines[probe].startswith(' ' * width):
                                content.append(part); index += 1; continue
                            break
                        if not part.startswith(' ' * width): break
                        content.append(part[width:]); index += 1
                    items.append({'type': 'list_item', 'children': self.blocks(content, depth + 1)})
                    probe = index
                    while probe < len(lines) and not lines[probe].strip(' \t\n'): probe += 1
                    peer = _LIST.match(lines[probe].rstrip('\n')) if probe < len(lines) else None
                    if peer and peer[2][0].isdigit() == ordered and peer[2][-1] == kind:
                        index = probe
                    else: break
                node = {'type': 'ordered_list' if ordered else 'bullet_list', 'children': items}
                if ordered: node['start'] = int(marker[:-1])
                self.explicit_container_end(lines, index)
                nodes.append(node); continue
            if line.startswith(('    ', '\t')):
                self.fail('prose_indented_code_forbidden')
            paragraph = [line.lstrip(' ')]; index += 1
            while index < len(lines) and lines[index].strip(' \t\n'):
                part = lines[index].rstrip('\n')
                if re.match(r'^ {0,3}(?:=+|-+)[ \t]*$', part):
                    self.fail('prose_heading_forbidden')
                if (self.fence(part) or _QUOTE.match(part) or _thematic(part)
                        or re.match(r'^ {0,3}#{1,6}(?:[ \t]|$)', part)):
                    break
                listing = _LIST.match(part)
                if listing and (not listing[2][0].isdigit() or listing[2][:-1] == '1'):
                    break
                paragraph.append(part.lstrip(' \t')); index += 1
            nodes.append({'type': 'paragraph',
                          'children': self.inlines('\n'.join(paragraph).rstrip(' \t'), depth + 1)})
        return nodes

    def code_end(self, value, index):
        self.work(len(value) - index)
        run = re.match(r'`+', value[index:])[0]
        match = re.search(r'(?<!`)' + re.escape(run) + r'(?!`)', value[index + len(run):])
        return (run, index + len(run) + match.start()) if match else (run, None)

    def link_end(self, value, start):
        index = start; nesting = 0
        while index < len(value):
            self.work()
            char = value[index]
            if char == '\\': index += 2; continue
            if char == '`':
                run, end = self.code_end(value, index)
                index = end + len(run) if end is not None else index + len(run)
                continue
            if char == '[': nesting += 1
            if char == ']':
                if nesting == 0: return index
                nesting -= 1
            index += 1
        return None

    def destination(self, value, start):
        index = start
        while index < len(value) and value[index] in ' \t\n': index += 1
        begin = index; nesting = 0
        if index < len(value) and value[index] == '<':
            index += 1; begin = index
            while index < len(value) and value[index] != '>':
                if value[index] in '<\n': return None
                index += 2 if value[index] == '\\' else 1
            if index == len(value): return None
            target = value[begin:index]; index += 1
        else:
            while index < len(value):
                char = value[index]
                if char == '\\': index += 2; continue
                if char == '(':
                    nesting += 1; self.depth(nesting)
                elif char == ')':
                    if not nesting: break
                    nesting -= 1
                elif char in ' \t\n': break
                index += 1
            if nesting: return None
            target = value[begin:index]
        space_start = index
        while index < len(value) and value[index] in ' \t\n': index += 1
        title = None
        if index > space_start and index < len(value) and value[index] in '\"\'(':
            delimiter = ')' if value[index] == '(' else value[index]
            begin = index + 1; index = begin
            while index < len(value) and value[index] != delimiter:
                index += 2 if value[index] == '\\' else 1
            if index == len(value): return None
            title = self.plain(value[begin:index]); index += 1
            while index < len(value) and value[index] in ' \t\n': index += 1
        if index >= len(value) or value[index] != ')': return None
        return target, title, index + 1

    def emphasis(self, tokens):
        index = 0
        while index < len(tokens):
            closer = tokens[index]
            if not closer.get('_close'):
                index += 1; continue
            opener_index = index - 1
            while opener_index >= 0:
                self.work()
                opener = tokens[opener_index]
                if (opener.get('_open') and opener.get('_mark') == closer['_mark']
                        and not ((opener['_close'] or closer['_open'])
                            and (opener['_count'] + closer['_count']) % 3 == 0
                            and (opener['_count'] % 3 or closer['_count'] % 3))):
                    break
                opener_index -= 1
            if opener_index < 0:
                index += 1; continue
            amount = 2 if min(opener['_count'], closer['_count']) >= 2 else 1
            children = self.finish(tokens[opener_index + 1:index])
            opener['_count'] -= amount; closer['_count'] -= amount
            replacement = ([opener] if opener['_count'] else []) + [
                {'type': 'strong' if amount == 2 else 'emphasis', 'children': children}]
            if closer['_count']: replacement.append(closer)
            tokens[opener_index:index + 1] = replacement
            index = opener_index + len(replacement) - (1 if closer['_count'] else 0)
        return self.finish(tokens)

    def finish(self, tokens):
        nodes = []
        for token in tokens:
            if '_mark' in token: _text(nodes, token['_mark'] * token['_count'])
            elif token['type'] == 'text': _text(nodes, token['text'])
            else: nodes.append(token)
        return nodes

    def inlines(self, value, depth=0, *, in_link=False):
        self.depth(depth)
        tokens = []; index = 0
        while index < len(value):
            self.work()
            char = value[index]
            if char == '\\' and index + 1 < len(value):
                if value[index + 1] in string.punctuation:
                    _text(tokens, value[index + 1]); index += 2; continue
                if value[index + 1] == '\n':
                    tokens.append({'type': 'line_break'}); index += 2; continue
            if char == '\n' and tokens and tokens[-1].get('type') == 'text':
                trailing = len(tokens[-1]['text']) - len(tokens[-1]['text'].rstrip(' '))
                if trailing >= 2:
                    tokens[-1]['text'] = tokens[-1]['text'].rstrip(' ')
                    tokens.append({'type': 'line_break'}); index += 1; continue
            if char == '`':
                run, end = self.code_end(value, index)
                if end is not None:
                    literal = value[index + len(run):end].replace('\n', ' ')
                    if literal.startswith(' ') and literal.endswith(' ') and literal.strip(' '):
                        literal = literal[1:-1]
                    tokens.append({'type': 'code_span', 'text': literal})
                    index = end + len(run); continue
                _text(tokens, run); index += len(run); continue
            image = value.startswith('![', index)
            if char == '[' or image:
                begin = index + (2 if image else 1)
                end = self.link_end(value, begin)
                if end is not None and value[end + 1:end + 2] == '(':
                    destination = self.destination(value, end + 2)
                    if destination:
                        if in_link and not image: self.fail('prose_nested_link_forbidden')
                        target, title, next_index = destination
                        node = {'type': 'image' if image else 'link',
                            'attachment_path': self.attachment(target),
                            'children': self.inlines(value[begin:end], depth + 1, in_link=not image or in_link)}
                        if title is not None: node['title'] = title
                        tokens.append(node); index = next_index; continue
            if char == '<' and re.match(r'<(?:/?[A-Za-z]|!|\?)', value[index:]):
                self.fail('prose_raw_html_or_autolink_forbidden')
            if char == '&':
                entity = _ENTITY.match(value, index)
                if entity:
                    _text(tokens, self.plain(entity[0])); index = entity.end(); continue
            if char in '*_':
                run = re.match(re.escape(char) + '+', value[index:])[0]
                before = value[index - 1] if index else '\n'
                after = value[index + len(run)] if index + len(run) < len(value) else '\n'
                left = not after.isspace() and (not _punctuation(after) or before.isspace() or _punctuation(before))
                right = not before.isspace() and (not _punctuation(before) or after.isspace() or _punctuation(after))
                tokens.append({'_mark': char, '_count': len(run),
                    '_open': left and (char == '*' or not right or _punctuation(before)),
                    '_close': right and (char == '*' or not left or _punctuation(after))})
                index += len(run); continue
            _text(tokens, char); index += 1
        return self.emphasis(tokens)


def parse_prose(block):
    """Parse an owned prose/admonition block; do not read attachments or render."""
    if type(block) is not ContentBlock:
        raise ProseError('prose_content_block_required')
    block = ContentBlock(block.source_bytes, path=block.path)
    if block.block_kind not in ('prose', 'admonition'):
        raise ProseError('prose_block_kind_required', path=block.path, pointer='/block_kind')
    value = block.payload['markdown'].replace('\r\n', '\n').replace('\r', '\n')
    parser = _Parser(block.path)
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
    if block.block_kind == 'admonition':
        node = {'type': 'admonition', 'level': block.payload['level'], 'children': children}
        if 'title' in block.payload: node['title'] = block.payload['title']
    pending = [(node, 0)]
    while pending:
        current, depth = pending.pop()
        parser.depth(depth)
        pending.extend((child, depth + 1) for child in current.get('children', []))
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
