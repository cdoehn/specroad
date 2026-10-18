"""Fixed table presentation of the native typed rows and group ordering."""
from ._render_text import _attribute, _cell


class TableEmitter:
    """Use the composed emitter's escaping, anchors and selected format."""

    def language_inline(self, text, language):
        if language is None:
            return text
        if self.html:
            attributes = ' dir="' + _attribute(language['text_direction']) + '"'
            if language['language'] is not None:
                attributes += ' lang="' + _attribute(language['language']) + '"'
            return '<span' + attributes + '>' + text + '</span>'
        fields = [('language', language['language']), ('text_direction', language['text_direction'])]
        return self.text('[' + ', '.join(k + '=' + v for k, v in fields if v is not None) + '] ') + text

    def table_cell(self, cell, annotation=None, requirement=None):
        if annotation is None:
            return self.text(_cell(cell))
        if annotation['records'] is not None:
            records = []
            for row, bound in zip(cell['value'], annotation['records']):
                parts = [self.table_identity(row['artifact_id'], bound)]
                parts.extend(self.table_cell(value, item, bound['requirement'])
                             for value, item in zip(row['cells'], bound['cells']))
                records.append(' / '.join(parts))
            return '<br>'.join(records) if records else self.text(_cell(cell))
        value = (requirement['force_label'] if requirement is not None
                 and annotation['requirement_field'] == 'normative_force' else _cell(cell))
        return self.language_inline(self.text(value), annotation['content_language'])

    def table_identity(self, identifier, annotation):
        text = self.anchor(identifier) + self.text(identifier)
        if annotation is not None and annotation['requirement'] is not None:
            # Force labels are metadata beside the original cells, never a
            # modal verb or negation inserted into the normative statement.
            text += '<br>' + self.text('normative_force: ' + annotation['requirement']['force_label'])
        return text

    def table(self, data, presentation=None):
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
        for group_number, group in enumerate(groups):
            if group['keys']:
                if presentation is None:
                    result.append(self.paragraph(' / '.join(_cell(cell) for cell in group['keys'])))
                else:
                    original = presentation['groups'][group_number]
                    text = ' / '.join(self.table_cell(cell, annotation, original['requirement'])
                                      for cell, annotation in zip(original['keys'], original['cells']))
                    result.append(('<p>' + text + '</p>\n') if self.html else text + '\n\n')
            wanted = None if group['artifact_ids'] is None else set(group['artifact_ids'])
            rows = []
            for row_number, row in enumerate(data['rows']):
                if wanted is not None and row['artifact_id'] not in wanted:
                    continue
                annotation = None if presentation is None else presentation['rows'][row_number]
                cells = [self.table_cell(cell,
                         None if annotation is None else annotation['cells'][number],
                         None if annotation is None else annotation['requirement'])
                         for number, cell in enumerate(row['cells'])]
                if has_ids:
                    identifier = row['artifact_id']
                    cells.insert(0, self.table_identity(identifier, annotation))
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
