"""Iterative lexical scan of physical Markdown lines and reserved fences."""
import re
from ..model.errors import ModelError
from .json_syntax import parse_json_object
from .plan_source_errors import _error


def _fence(line):
    match = re.fullmatch(r'( *)(`{3,}|~{3,})([^\n]*)\n?', line)
    if match is None:
        return None
    return len(match[1]), match[2][0], len(match[2]), match[3].strip(' \t')


def _heading(line):
    """Recognize header syntax; only the reserved following fence activates it."""
    text = line.rstrip('\n')
    match = re.match(r'^( {0,3})(#{1,6})[ \t]+', text)
    if match:
        level, indent, begin, kind = len(match[2]), 0, match.end(), 'heading'
        end = len(text.rstrip(' \t'))
        closing = re.search(r'[ \t]+#+[ \t]*$', text[begin:])
        if closing is not None:
            end = begin + closing.start()
    else:
        match = re.match(r'^( *)- ', text)
        if not match:
            return None
        level, indent, begin, kind = 0, len(match[1]), match.end(), 'list'
        end = len(text.rstrip(' \t'))
    content = text[begin:end]
    pattern = r'\[([^\[\]]+)\][ \t]+(.+)' if level == 1 else r'\[([^\[\]]*)\][ \t]+\[([^\[\]]+)\][ \t]+(.+)'
    values = re.fullmatch(pattern, content)
    if values is None:
        return {'invalid': True, 'indent': indent, 'kind': kind, 'level': level}
    display_group, title_group = (1, 2) if level == 1 else (2, 3)
    def span(group):
        return (len(text[:begin + values.start(group)].encode('utf-8')),
                len(text[:begin + values.end(group)].encode('utf-8')))
    return {'invalid': False, 'indent': indent, 'kind': kind, 'level': level,
        'display_id': values[display_group], 'title': values[title_group],
        'status': None if level == 1 else values[1], 'display_span': span(display_group),
        'title_span': span(title_group), 'status_span': None if level == 1 else span(1)}


def _body(raw, indent, *, source, path, offset):
    parts = raw.decode('utf-8').split('\n')
    lines = [line + '\n' for line in parts[:-1]] + ([parts[-1]] if parts[-1] else [])
    result = []
    for line in lines:
        if indent and line.strip(' \t\n'):
            if not line.startswith(' ' * indent):
                raise _error('plan_body_indentation', source, path, offset)
            result.append(line[indent:])
        else:
            # Whitespace-only lines remain exact, rather than becoming proof.
            result.append(line)
        offset += len(line.encode('utf-8'))
    return ''.join(result)


def _comments(line, inside):
    """Track actual comment delimiters outside escaped/inline-code examples."""
    cursor, first = 0, None
    while cursor < len(line):
        if inside:
            end = line.find('-->', cursor)
            if end < 0:
                return True, first
            inside, cursor = False, end + 3
        elif line[cursor] == '\\':
            cursor += 2
        elif line[cursor] == '`':
            end = cursor
            while end < len(line) and line[end] == '`':
                end += 1
            delimiter = line[cursor:end]
            closing = end
            while True:
                closing = line.find(delimiter, closing)
                if closing < 0:
                    cursor = end
                    break
                stop = closing + len(delimiter)
                if line[closing-1] != '`' and line[stop:stop+1] != '`':
                    cursor = stop
                    break
                closing += 1
        elif line.startswith('<!--', cursor):
            first = cursor if first is None else first
            inside, cursor = True, cursor + 4
        else:
            cursor += 1
    return inside, first


def _scan(raw, path):
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as error:
        raise _error('invalid_utf8', raw, path, error.start) from error
    if raw.startswith(b'\xef\xbb\xbf'):
        raise _error('plan_bom_forbidden', raw, path, 0)
    if b'\r' in raw:
        raise _error('plan_lf_required', raw, path, raw.index(b'\r'))
    lines = text.split('\n')
    lines = [line + '\n' for line in lines[:-1]] + ([lines[-1]] if lines[-1] else [])
    offsets, offset = [], 0
    for line in lines:
        offsets.append(offset)
        offset += len(line.encode('utf-8'))
    offsets.append(len(raw))
    records, code, comment, list_indent = [], None, False, None
    i = 0
    while i < len(lines):
        line = lines[i]
        fence = _fence(line)
        if code is not None:
            if fence is not None and fence[1] == code[1] and fence[2] >= code[2] and not fence[3] and fence[0] <= code[0] + 3:
                code = None
            i += 1
            continue
        # Markers inside quotes/indented code do not open an outer HTML comment.
        # An already open outer comment still observes its closing delimiter.
        if not comment:
            indentation = len(line) - len(line.lstrip(' '))
            code_indent = 4 if list_indent is None else list_indent + 6
            if line.lstrip(' \t').startswith('>') or line.startswith('\t') or indentation >= code_indent:
                i += 1
                continue
        if not comment and fence is not None:
            if fence[1] == '`' and fence[3] in ('specroad-plan-v1', 'specroad-entry-v1'):
                raise _error('plan_orphan_metadata', raw, path, offsets[i])
            if fence[1] == '~' or '`' not in fence[3]:
                code = fence
            i += 1
            continue
        # Comment contents cannot activate a header. A closed inline comment
        # after a real header remains literal source text in that title.
        if comment or '<!--' in line:
            was_comment = comment
            comment, comment_start = _comments(line, comment)
            if was_comment or comment or (comment_start is not None and comment_start <= len(line) - len(line.lstrip(' \t'))) or _heading(line) is None:
                i += 1
                continue
        if line.lstrip(' \t').startswith('>'):
            i += 1
            continue
        indentation = len(line) - len(line.lstrip(' '))
        code_indent = 4 if list_indent is None else list_indent + 6
        if line.startswith('\t') or indentation >= code_indent:
            i += 1
            continue
        if fence is not None:
            if fence[1] == '`' and fence[3] in ('specroad-plan-v1', 'specroad-entry-v1'):
                raise _error('plan_orphan_metadata', raw, path, offsets[i])
            if fence[1] == '~' or '`' not in fence[3]:
                code = fence
            i += 1
            continue
        head = _heading(line)
        j = i + 1
        if j < len(lines) and not lines[j].strip(' \t\n'):
            j += 1
        following = _fence(lines[j]) if j < len(lines) else None
        if head is None or following is None or following[1] != '`' or following[3] not in ('specroad-plan-v1', 'specroad-entry-v1'):
            i += 1
            continue
        if head['invalid'] or (head['level'] != 1 and head['status'] not in (' ', 'x')):
            raise _error('plan_invalid_header', raw, path, offsets[i])
        expected_kind = 'specroad-plan-v1' if head['level'] == 1 else 'specroad-entry-v1'
        indent = head['indent'] + 2 if head['kind'] == 'list' else 0
        if following[3] != expected_kind or (following[0] != indent if head['kind'] == 'list' else following[0] > 3):
            raise _error('plan_metadata_header_mismatch', raw, path, offsets[j])
        if head['kind'] == 'list' and head['indent'] % 2:
            raise _error('plan_list_indentation', raw, path, offsets[i])
        k, json_lines = j + 1, []
        while k < len(lines):
            closing = _fence(lines[k])
            if closing is not None and closing[1] == '`' and closing[2] >= following[2] and not closing[3]:
                if (closing[0] != indent if head['kind'] == 'list' else closing[0] > 3):
                    raise _error('plan_metadata_indentation', raw, path, offsets[k])
                break
            if lines[k].strip(' \t\n') and not lines[k].startswith(' ' * indent):
                raise _error('plan_metadata_indentation', raw, path, offsets[k])
            json_lines.append(lines[k][indent:] if lines[k].startswith(' ' * indent) else lines[k])
            k += 1
        if k == len(lines):
            raise _error('plan_unclosed_metadata', raw, path, offsets[j])
        try:
            meta = parse_json_object(''.join(json_lines).encode('utf-8'), path=path)
        except ModelError as error:
            row = min(j + (error.line or 1), k)
            column = (error.column or 1) - 1 + indent
            location = offsets[row] + len(lines[row][:column].encode('utf-8'))
            if error.pointer and error.line is None:
                from .plan_json_spans import member_spans
                try:
                    key = error.pointer.split('/')[1].replace('~1', '/').replace('~0', '~')
                    members = member_spans(raw[offsets[j+1]:offsets[k]])
                    matches = [m for m in members if m[0] == key]
                    if matches:
                        location = offsets[j+1] + matches[-1][1]
                except (ValueError, RecursionError):
                    pass
            raise _error(error.reason, raw, path, location, pointer=error.pointer) from error
        if records:
            records[-1]['body_end'] = offsets[i]
        records.append({**head, 'meta': meta, 'line': i + 1, 'start': offsets[i],
            'header_end': offsets[i + 1], 'json_start': offsets[j + 1], 'json_end': offsets[k],
            'body_start': offsets[k + 1], 'body_end': len(raw), 'body_indent': indent})
        list_indent = head['indent'] if head['kind'] == 'list' else None
        i = k + 1
    return records
