"""Fixed table presentation of the native typed rows and group ordering."""
from ._render_text import _cell


class TableEmitter:
    """Use the composed emitter's escaping, anchors and selected format."""

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
