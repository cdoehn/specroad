"""Fixed prose syntax over admitted semantic nodes and owned raster assets."""
from base64 import b64encode
from html import escape
import re

from ._render_text import _attribute, _label


class ProseEmitter:
    """Use the composed emitter's text escaping and selected output format."""

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
        if kind in ('link', 'image'):
            asset = node['attachment']
            # The media type comes from a closed admission list, never from a
            # filename or untrusted URI. Both formats carry all resource bytes.
            uri = 'data:' + asset.media_type + ';base64,' + b64encode(asset.content).decode('ascii')
            title = ' title="' + _attribute(node['title']) + '"' if 'title' in node else ''
            if kind == 'image':
                return '<img src="' + uri + '" alt="' + _attribute(_label(node)) + '"' + title + '>'
            label = ''.join(self.prose(child) for child in node['children'])
            return '<a href="' + uri + '"' + title + '>' + label + '</a>'
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
