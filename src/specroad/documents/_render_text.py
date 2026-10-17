"""Shared literal text and stable ID formatting; no input discovery."""
from html import escape
import json


def _anchor(identifier):
    # Full UTF-8 hex is injective and safe in both attributes and fragments.
    return 'artifact-' + identifier.encode('utf-8').hex()

def _value(value):
    if type(value) is str:
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)

def _cell(cell):
    return '[missing]' if cell['type'] == 'missing' else _value(cell['value'])

def _attribute(value):
    return escape(value, quote=True).replace('\r', '&#13;').replace('\n', '&#10;')

def _label(node):
    pending = [node]
    parts = []
    while pending:
        current = pending.pop()
        if 'text' in current:
            parts.append(current['text'])
        elif current['type'] == 'line_break':
            parts.append(' ')
        pending.extend(reversed(current.get('children', ())))
    return ''.join(parts)
