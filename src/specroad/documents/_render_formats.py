"""Compose fixed output adapters; source strings never become templates."""
from html import escape
import re

from ._render_text import _anchor, _attribute, _value
from ._render_prose import ProseEmitter
from ._render_tables import TableEmitter


class Emitter(ProseEmitter, TableEmitter):
    """Only constant markup is executable syntax; source strings stay data."""

    def __init__(self, output_format):
        self.html = output_format == 'html'
        self.anchors = set()

    def text(self, value):
        value = escape(value, quote=True).replace('\r', '&#13;')
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

    def record(self, record, mode, level=3, presentation=None):
        identifier = record['id']
        title = identifier + ' — ' + record['title']
        if mode == 'link':
            label = self.text(title)
            target = '#' + _anchor(identifier)
            return ('<p><a href="' + target + '">' + label + '</a></p>\n' if self.html
                    else '[' + label + '](' + target + ')\n\n')
        result = self.heading(title, level, identifier)
        separate = set()
        if presentation is not None:
            result += self.paragraph('normative_force: ' + presentation['force_label'])
            result += self.paragraph(presentation['statement'])
            separate = {'normative_force', 'statement', 'language', 'text_direction'}
        fields = (sorted(record) if mode == 'full' else
                  [key for key in ('artifact_type', 'revision', 'normative_force', 'statement', 'description') if key in record])
        for key in fields:
            if key not in ('id', 'title') and key not in separate:
                result += self.paragraph(key + ': ' + _value(record[key]))
        return result

    def language_block(self, text, content_language):
        if self.html:
            attributes = ' dir="' + _attribute(content_language['text_direction']) + '"'
            if content_language['language'] is not None:
                attributes += ' lang="' + _attribute(content_language['language']) + '"'
            return '<div' + attributes + '>' + text + '</div>\n'
        prefix = ''
        if content_language['language'] is not None:
            prefix = self.paragraph('language: ' + content_language['language'])
        return prefix + self.paragraph('text_direction: ' + content_language['text_direction']) + text

    def output(self, metadata, title, nodes):
        body = [self.paragraph('GENERATED — DO NOT EDIT')]
        body.extend(self.paragraph(key + ': ' + _value(value)) for key, value in metadata.items())
        for node in nodes:
            kind = node['type']
            if kind == 'heading':
                part = self.heading(node['title'], node['level'], node['id'])
            elif kind == 'prose':
                part = self.anchor(node['id']) + '\n\n' + self.prose(node['content'])
            elif kind == 'table':
                part = self.anchor(node['id']) + '\n\n' + self.table(node['data'])
            elif kind == 'record':
                part = self.record(node['record'], node['mode'], node['level'], node.get('presentation'))
            elif kind == 'anchor':
                part = self.anchor(node['id']) + '\n\n'
            elif kind == 'page_break':
                part = (self.anchor(node['id']) + '\n\n<div class="specroad-page-break" '
                        'style="break-after:page;page-break-after:always"></div>\n\n')
            else:
                raise ValueError('Unsupported internal render node: ' + kind)
            if 'content_language' in node:
                part = self.language_block(part, node['content_language'])
            body.append(part)
        text = ''.join(body)
        if self.html:
            text = ('<!doctype html>\n<html><head><meta charset="utf-8">'
                    '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
                    '<title>' + _attribute(title) + '</title>'
                    '<style>body{font-family:sans-serif;max-width:80em;margin:2em auto;padding:0 1em}'
                    'table{border-collapse:collapse}td,th{border:1px solid;padding:.4em;vertical-align:top}'
                    'pre,p,td{white-space:pre-wrap}img{max-width:100%}aside{border-left:.3em solid;padding:1em}'
                    '.specroad-page-break{break-after:page;page-break-after:always}</style>'
                    '</head><body>\n' + text + '</body></html>\n')
        return text.encode('utf-8')
