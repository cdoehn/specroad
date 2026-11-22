"""The sole plan-markdown-v1 carrier, parsed without writes or cached authority.

Offsets are UTF-8 byte offsets; diagnostics additionally expose physical line
and character column. A failed parse never returns a partially valid plan.
Source bytes remain the caller's original input, including ignored examples.
"""
from dataclasses import dataclass
from hashlib import sha256
import re

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.plan_inventory import PlanProjectionInventory
from ..model.plan_projection import PlanProjection
from .json_syntax import parse_json_object


class PlanSourceError(ModelError):
    def diagnostic(self):
        identity_error = self.reason in ('duplicate_artifact_id', 'duplicate_plan_display_id',
            'duplicate_plan_relation_id', 'duplicate_plan_claim_id', 'plan_carrier_identity_mismatch',
            'artifact_identity_mismatch')
        return {**super().diagnostic(), 'code': 'SRV201' if identity_error else 'SRV200',
                'severity': 'error', 'partial_result_available': False}


@dataclass(frozen=True)
class SourceSpan:
    start: int
    end: int

    def read(self, source):
        return source[self.start:self.end]


@dataclass(frozen=True)
class PlanSection:
    artifact: PlanProjection
    header: SourceSpan
    metadata: SourceSpan
    body: SourceSpan
    title: SourceSpan
    display_id: SourceSpan
    checkbox: SourceSpan | None
    indent: int
    line: int


_CONTEXT_FIELDS = ('id', 'artifact_type', 'title', 'display_id', 'language',
    'description', 'notes', 'entry_kind', 'work_kind', 'scope', 'prerequisites',
    'requirement_bindings', 'coverage_claims', 'acceptance_criteria',
    'expected_scope', 'relations', 'applicability', 'parent_id', 'plan_id', 'children')


@dataclass(frozen=True)
class PlanSource:
    source_bytes: bytes
    path: str | None
    sections: tuple[PlanSection, ...]

    @property
    def file_sha256(self):
        return sha256(self.source_bytes).hexdigest()

    @property
    def projections(self):
        return tuple(section.artifact for section in self.sections)

    @property
    def resource_manifest(self):
        return {'path': self.path, 'file_sha256': self.file_sha256,
                'artifacts': [{'id': p.data['id'], 'sha256': p.sha256} for p in self.projections]}

    def section(self, identity):
        for section in self.sections:
            if section.artifact.data['id'] == identity:
                return section
        raise ModelError('plan_entry_not_found', path=self.path)

    def context_sha256(self, identity):
        value = self.section(identity).artifact.data
        return canonical_json_sha256({k: value[k] for k in _CONTEXT_FIELDS if k in value})

    def revision_diagnostics(self, previous=None):
        """Compare explicitly supplied adjacent sources, never infer history."""
        if previous is None:
            return ()
        if type(previous) is not PlanSource or previous.projections[0].data['id'] != self.projections[0].data['id']:
            raise ModelError('plan_comparison_basis_mismatch', path=self.path)
        from ..model.lifecycle_content import _content_hash
        old = {p.data['id']: p.data for p in previous.projections}
        result = []
        for section in self.sections:
            value = section.artifact.data
            before = old.get(value['id'])
            if before is not None and _content_hash(before) != _content_hash(value) and value['revision'] != before['revision'] + 1:
                result.append({'code': 'SRV206', 'severity': 'warning', 'reason': 'plan_content_revision_mismatch',
                    'path': self.path, 'line': section.line, 'column': 1,
                    'artifact_id': value['id'], 'pointer': '/revision',
                    'expected_revision': before['revision'] + 1, 'actual_revision': value['revision']})
        return tuple(result)

    def replace_fields(self, updates, *, expected_file_sha256):
        from .plan_edits import replace_fields
        return replace_fields(self, updates, expected_file_sha256=expected_file_sha256)

    def replace_spans(self, edits, *, expected_file_sha256):
        from .plan_edits import replace_spans
        return replace_spans(self, edits, expected_file_sha256=expected_file_sha256)


def _error(reason, raw, path, offset, *, pointer=''):
    offset = min(max(offset, 0), len(raw))
    prefix = raw[:offset]
    return PlanSourceError(reason, path=path, position=offset, line=prefix.count(b'\n') + 1,
        column=len(prefix.rsplit(b'\n', 1)[-1].decode('utf-8', errors='replace')) + 1, pointer=pointer)


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
        # HTML comment state is independent of model or metadata parsing.
        if comment or '<!--' in line:
            cursor = 0
            while cursor < len(line):
                marker = '-->' if comment else '<!--'
                at = line.find(marker, cursor)
                if at < 0:
                    break
                comment = not comment
                cursor = at + len(marker)
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
            raise _error(error.reason, raw, path, location, pointer=error.pointer) from error
        if records:
            records[-1]['body_end'] = offsets[i]
        records.append({**head, 'meta': meta, 'line': i + 1, 'start': offsets[i],
            'header_end': offsets[i + 1], 'json_start': offsets[j + 1], 'json_end': offsets[k],
            'body_start': offsets[k + 1], 'body_end': len(raw), 'body_indent': indent})
        list_indent = head['indent'] if head['kind'] == 'list' else None
        i = k + 1
    return records


def parse_plan(raw, *, path=None, id_prefix=None):
    """Parse complete original bytes. This proves fields/structure, not a graph."""
    if type(raw) is not bytes:
        raise ModelError('bytes_required', path=path)
    records = _scan(raw, path)
    if not records or records[0]['level'] != 1:
        raise _error('plan_heading_required', raw, path, 0)
    if any(r['level'] == 1 for r in records[1:]):
        r = next(r for r in records[1:] if r['level'] == 1)
        raise _error('duplicate_plan_heading', raw, path, r['start'])
    # Validate each carrier kind before its ID can affect a parent's schema.
    for index, row in enumerate(records):
        kind = 'implementation_plan' if index == 0 else 'plan_entry'
        if row['meta'].get('artifact_type') != kind:
            raise _error('artifact_type_mismatch', raw, path, row['json_start'], pointer='/artifact_type')
    heading_stack, list_stack = [], []
    sections, data = [], []
    for index, row in enumerate(records):
        row['children'] = []
        if index:
            if row['kind'] == 'heading':
                list_stack.clear()
                while heading_stack and heading_stack[-1]['level'] >= row['level']:
                    heading_stack.pop()
                parent = heading_stack[-1] if heading_stack else records[0]
                heading_stack.append(row)
            else:
                while list_stack and list_stack[-1]['indent'] >= row['indent']:
                    list_stack.pop()
                if row['indent']:
                    if not list_stack or list_stack[-1]['indent'] != row['indent'] - 2:
                        raise _error('plan_list_parent_missing', raw, path, row['start'])
                    parent = list_stack[-1]
                else:
                    parent = heading_stack[-1] if heading_stack else records[0]
                list_stack.append(row)
            row['parent'] = parent
            parent['children'].append(row['meta'].get('id'))
    for index, row in enumerate(records):
        derived = {'title': row['title'], 'display_id': row['display_id'], 'children': row['children'],
            'description': _body(raw[row['body_start']:row['body_end']], row['body_indent'],
                source=raw, path=path, offset=row['body_start'])}
        if index:
            derived.update(implemented=row['status'] == 'x', plan_id=records[0]['meta'].get('id'),
                           parent_id=row['parent']['meta'].get('id'))
        for key, value in derived.items():
            if key in row['meta'] and canonical_json_bytes(row['meta'][key]) != canonical_json_bytes(value):
                raise _error('plan_derived_field_conflict', raw, path, row['json_start'], pointer='/' + key)
        value = {**row['meta'], **derived}
        try:
            projection = PlanProjection(value, id_prefix=id_prefix)
        except ModelError as error:
            raise _error(error.reason, raw, path, row['json_start'], pointer=error.pointer) from error
        def absolute(pair):
            return SourceSpan(row['start'] + pair[0], row['start'] + pair[1])
        sections.append(PlanSection(projection, SourceSpan(row['start'], row['header_end']),
            SourceSpan(row['json_start'], row['json_end']), SourceSpan(row['body_start'], row['body_end']),
            absolute(row['title_span']), absolute(row['display_span']),
            None if row['status_span'] is None else absolute(row['status_span']), row['body_indent'], row['line']))
        data.append(value)
    try:
        PlanProjectionInventory(data, id_prefix=id_prefix or data[0]['id'].split('-')[0])
    except ModelError as error:
        raise _error(error.reason, raw, path, sections[-1].metadata.start, pointer=error.pointer) from error
    if path is not None and sections[0].artifact.path != path:
        raise _error('plan_carrier_identity_mismatch', raw, path, 0)
    return PlanSource(raw, path, tuple(sections))
