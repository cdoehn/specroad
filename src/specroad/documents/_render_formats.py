"""Fixed presentation emitters for internally assembled document nodes."""
from html import escape
import json
import re


def _anchor(identifier):
    # Full UTF-8 hex is injective and safe in both attributes and fragments.
    return 'artifact-' + identifier.encode('utf-8').hex()


def _value(value):
    if type(value) is str:
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _cell(cell):
    return '[missing]' if cell['type'] == 'missing' else _value(cell['value'])


class Emitter:
    """Only constant markup is executable syntax; source strings stay data."""

    def __init__(self, output_format):
        self.html = output_format == 'html'
        self.anchors = set()

    def text(self, value):
        value = escape(value, quote=True)
        if self.html:
            return value
        value = re.sub(r'([\\`*_{}\[\]()#+.!|>~\-])', r'\\\1', value)
        return value.replace('\r', '&#13;').replace('\n', '&#10;')

    def anchor(self, identifier):
        if identifier in self.anchors:
            return ''
        self.anchors.add(identifier)
        return '<a id="' + _anchor(identifier) + '"></a>'

    def paragraph(self, value):
        text = self.text(value)
        return '<p>' + text + '</p>\n' if self.html else text + '\n\n'

    def heading(self, title, level, identifier=None):
        marker = self.anchor(identifier) if identifier is not None else ''
        level = min(max(level, 1), 6)
        text = self.text(title)
        if self.html:
            tag = 'h' + str(level)
            return marker + '<' + tag + '>' + text + '</' + tag + '>\n'
        return (marker + '\n\n' if marker else '') + '#' * level + ' ' + text + '\n\n'

    def code(self, text, *, block=False):
        # HTML code elements also form safe code spans in Markdown. Blocks use
        # a fence longer than every source run, so source text cannot close it.
        if self.html or not block:
            result = '<code>' + escape(text, quote=True) + '</code>'
            return '<pre>' + result + '</pre>\n' if block else result
        runs = re.findall(r'`+', text)
        fence = '`' * max(3, 1 + max(map(len, runs), default=0))
        return fence + '\n' + text + ('' if text.endswith('\n') else '\n') + fence + '\n\n'

    def prose(self, node):
        kind = node['type']
        if kind == 'text':
            return self.text(node['text'])
        if kind in ('code_span', 'code_block'):
            return self.code(node['text'], block=kind == 'code_block')
        if kind == 'line_break':
            return '<br>\n' if self.html else '  \n'
        if kind == 'thematic_break':
            return '<hr>\n' if self.html else '\n---\n\n'
        if kind in ('bullet_list', 'ordered_list'):
            items = [self.prose(item) for item in node['children']]
            if self.html:
                tag = 'ol' if kind == 'ordered_list' else 'ul'
                start = (' start="' + str(node['start']) + '"') if kind == 'ordered_list' else ''
                return '<' + tag + start + '>' + ''.join(items) + '</' + tag + '>\n'
            result = []
            for index, item in enumerate(items):
                marker = str(node.get('start', 1) + index) + '. ' if kind == 'ordered_list' else '- '
                lines = item.rstrip('\n').split('\n')
                result.append(marker + lines[0] + '\n' + ''.join(' ' * len(marker) + line + '\n' for line in lines[1:]))
            return ''.join(result) + '\n'
        children = ''.join(self.prose(child) for child in node.get('children', ()))
        if kind == 'document':
            return children
        if kind == 'admonition':
            title = node.get('title', node['level'])
            if self.html:
                return '<aside class="admonition"><p><strong>' + self.text(title) + '</strong></p>\n' + children + '</aside>\n'
            children = self.text(title) + '\n\n' + children
            return ''.join('> ' + line + '\n' for line in children.rstrip('\n').split('\n')) + '\n'
        if kind == 'block_quote':
            if self.html:
                return '<blockquote>' + children + '</blockquote>\n'
            return ''.join('> ' + line + '\n' for line in children.rstrip('\n').split('\n')) + '\n'
        if kind in ('paragraph', 'emphasis', 'strong', 'list_item'):
            if self.html:
                tag = {'paragraph': 'p', 'emphasis': 'em', 'strong': 'strong', 'list_item': 'li'}[kind]
                return '<' + tag + '>' + children + '</' + tag + '>' + ('\n' if kind in ('paragraph', 'list_item') else '')
            if kind == 'paragraph':
                return children + '\n\n'
            if kind == 'list_item':
                return children
            marker = '*' if kind == 'emphasis' else '**'
            return marker + children + marker
        raise ValueError('Unsupported internal prose node: ' + kind)

    def table(self, data):
        if data.get('outcome') == 'omit':
            return ''
        if data.get('outcome') == 'message':
            return self.paragraph('No matching artifacts.')
        columns = [self.text(c.get('heading', c.get('field', ''))) for c in data['columns']]
        has_ids = any('artifact_id' in row for row in data['rows'])
        if has_ids:
            columns.insert(0, 'Artifact')
        groups = data.get('groups') or [{'keys': [], 'artifact_ids': None}]
        result = []
        for group in groups:
            if group['keys']:
                result.append(self.paragraph(' / '.join(_cell(cell) for cell in group['keys'])))
            wanted = None if group['artifact_ids'] is None else set(group['artifact_ids'])
            rows = []
            for row in data['rows']:
                if wanted is not None and row['artifact_id'] not in wanted:
                    continue
                cells = [self.text(_cell(cell)) for cell in row['cells']]
                if has_ids:
                    identifier = row['artifact_id']
                    cells.insert(0, self.anchor(identifier) + self.text(identifier))
                rows.append(cells)
            if self.html:
                result.append('<table><thead><tr>' + ''.join('<th>' + c + '</th>' for c in columns) + '</tr></thead><tbody>\n')
                result.extend('<tr>' + ''.join('<td>' + c + '</td>' for c in row) + '</tr>\n' for row in rows)
                result.append('</tbody></table>\n')
            else:
                result.extend(('| ' + ' | '.join(columns) + ' |\n', '| ' + ' | '.join('---' for _ in columns) + ' |\n'))
                result.extend('| ' + ' | '.join(row) + ' |\n' for row in rows)
                result.append('\n')
        return ''.join(result)

    def record(self, record, mode, level=3):
        identifier = record['id']
        title = identifier + ' — ' + record['title']
        if mode == 'link':
            label = self.text(title)
            target = '#' + _anchor(identifier)
            return ('<p><a href="' + target + '">' + label + '</a></p>\n' if self.html
                    else '[' + label + '](' + target + ')\n\n')
        result = self.heading(title, level, identifier)
        fields = (sorted(record) if mode == 'full' else
                  [key for key in ('artifact_type', 'revision', 'normative_force', 'statement', 'description') if key in record])
        for key in fields:
            if key not in ('id', 'title'):
                result += self.paragraph(key + ': ' + _value(record[key]))
        return result

    def output(self, metadata, title, nodes):
        body = [self.paragraph('GENERATED — DO NOT EDIT')]
        body.extend(self.paragraph(key + ': ' + _value(value)) for key, value in metadata.items())
        for node in nodes:
            kind = node['type']
            if kind == 'heading':
                body.append(self.heading(node['title'], node['level'], node['id']))
            elif kind == 'prose':
                body.append(self.anchor(node['id']) + '\n\n' + self.prose(node['content']))
            elif kind == 'table':
                body.append(self.anchor(node['id']) + '\n\n' + self.table(node['data']))
            elif kind == 'record':
                body.append(self.record(node['record'], node['mode'], node['level']))
            elif kind == 'anchor':
                body.append(self.anchor(node['id']) + '\n\n')
            elif kind == 'page_break':
                body.append(self.anchor(node['id']) + '<div class="specroad-page-break"></div>\n\n')
            else:
                raise ValueError('Unsupported internal render node: ' + kind)
        text = ''.join(body)
        if self.html:
            text = ('<!doctype html>\n<html><head><meta charset="utf-8">'
                    '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
                    '<title>' + escape(title, quote=True) + '</title>'
                    '<style>body{font-family:sans-serif;max-width:80em;margin:2em auto;padding:0 1em}'
                    'table{border-collapse:collapse}td,th{border:1px solid;padding:.4em;vertical-align:top}'
                    'pre{white-space:pre-wrap}aside{border-left:.3em solid;padding:1em}'
                    '.specroad-page-break{break-after:page;page-break-after:always}</style>'
                    '</head><body>\n' + text + '</body></html>\n')
        return text.encode('utf-8')
