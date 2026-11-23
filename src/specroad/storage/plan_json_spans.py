"""Top-level JSON value byte spans, after the strict native value check.

The decoder locates tokens only; it is never a schema or numeric-policy bypass.
Keeping each untouched token also preserves escapes, ordering and whitespace.
"""
import json
from ..model.canonical import canonical_json_bytes
from .plan_edits import SourceEdit


def member_spans(raw):
    text = raw.decode('utf-8')
    decoder = json.JSONDecoder()
    def space(offset):
        while offset < len(text) and text[offset] in ' \t\r\n':
            offset += 1
        return offset
    def byte(offset):
        return len(text[:offset].encode('utf-8'))
    cursor = space(0)
    if text[cursor:cursor+1] != '{':
        return ()
    cursor = space(cursor + 1)
    result = []
    while text[cursor:cursor+1] != '}':
        key_start = cursor
        key, cursor = decoder.raw_decode(text, cursor)
        cursor = space(cursor)
        if text[cursor:cursor+1] != ':':
            raise ValueError('JSON colon required')
        start = space(cursor + 1)
        _, end = decoder.raw_decode(text, start)
        result.append((key, byte(key_start), byte(start), byte(end)))
        cursor = space(end)
        if text[cursor:cursor+1] == '}':
            break
        if text[cursor:cursor+1] != ',':
            raise ValueError('JSON comma required')
        cursor = space(cursor + 1)
    return tuple(result)


def metadata_edits(section, raw, before, after):
    fields = member_spans(raw)
    edits = []
    present = set()
    for name, _, start, end in fields:
        present.add(name)
        if canonical_json_bytes(before[name]) != canonical_json_bytes(after[name]):
            edits.append(SourceEdit(section.metadata.start + start, section.metadata.start + end,
                raw[start:end], canonical_json_bytes(after[name])))
    added = [name for name in after if name not in present]
    if added:
        position = fields[-1][3] if fields else raw.index(b'{') + 1
        insertion = (b',' if fields else b'') + b','.join(
            canonical_json_bytes(name) + b':' + canonical_json_bytes(after[name]) for name in added)
        # An insertion adjoining the last changed value shares its preimage.
        if edits and edits[-1].end - section.metadata.start == position:
            last = edits.pop()
            edits.append(SourceEdit(last.start, last.end, last.before, last.after + insertion))
        else:
            edits.append(SourceEdit(section.metadata.start + position, section.metadata.start + position, b'', insertion))
    return edits
