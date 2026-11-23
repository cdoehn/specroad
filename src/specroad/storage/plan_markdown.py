"""The sole plan-markdown-v1 carrier, parsed without writes or cached authority.

Offsets are UTF-8 byte offsets; diagnostics additionally expose physical line
and character column. A failed parse never returns a partially valid plan.
Source bytes remain the caller's original input, including ignored examples.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.plan_inventory import PlanProjectionInventory
from ..model.plan_projection import PlanProjection
from .plan_source_errors import PlanSourceError, _error
from ._plan_scan import _scan, _body


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
    # Locate identity/label collisions at the offending definition, before
    # a parent's derived child array can obscure the source of the failure.
    from ..model.paths import validate_artifact_address
    from .plan_json_spans import member_spans
    root_id = records[0]['meta'].get('id')
    prefix = id_prefix or (root_id.split('-')[0] if type(root_id) is str else None)
    identities, labels = set(), set()
    for index, row in enumerate(records):
        kind = 'plan_entry' if index else 'implementation_plan'
        identity = row['meta'].get('id')
        if row['meta'].get('artifact_type') == kind and type(prefix) is str and identity is not None:
            try:
                validate_artifact_address(kind, identity, prefix)
            except ModelError as error:
                fields = member_spans(raw[row['json_start']:row['json_end']])
                location = next((m[1] for m in fields if m[0] == 'id'), 0)
                raise _error(error.reason, raw, path, row['json_start']+location, pointer='/id') from error
            if identity in identities:
                raise _error('duplicate_artifact_id', raw, path, row['json_start'], pointer='/id')
            identities.add(identity)
        if row['display_id'] in labels:
            raise _error('duplicate_plan_display_id', raw, path, row['start'], pointer='/display_id')
        labels.add(row['display_id'])
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
            location = row['json_start']
            if error.pointer:
                from .plan_json_spans import member_spans
                key = error.pointer.split('/')[1].replace('~1', '/').replace('~0', '~')
                spans = member_spans(raw[row['json_start']:row['json_end']])
                matches = [m for m in spans if m[0] == key]
                if matches:
                    location += matches[-1][1]
                elif key in ('title', 'display_id', 'implemented'):
                    location = row['start']
            raise _error(error.reason, raw, path, location, pointer=error.pointer) from error
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
