"""Pure, source-bound candidate bytes. No writer, audit or revision authority."""
from .plan_edit_values import SourceEdit

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from .json_syntax import parse_json_object
from .plan_markdown import PlanSource, parse_plan, _body




def _bound(source, expected):
    if type(source) is not PlanSource or type(expected) is not str or expected != source.file_sha256:
        raise ModelError('plan_source_changed')


def replace_spans(source, edits, *, expected_file_sha256):
    _bound(source, expected_file_sha256)
    if type(edits) not in (list, tuple):
        raise ModelError('plan_edits_required', path=source.path)
    spans = [span for section in source.sections for span in (section.header, section.metadata, section.body)]
    for edit in edits:
        if (type(edit) is not SourceEdit or type(edit.start) is not int or type(edit.end) is not int
                or type(edit.before) is not bytes or type(edit.after) is not bytes
                or not 0 <= edit.start <= edit.end <= len(source.source_bytes)):
            raise ModelError('plan_edit_invalid', path=source.path)
        if not any(s.start <= edit.start <= edit.end <= s.end for s in spans):
            raise ModelError('plan_edit_outside_spans', path=source.path)
        if source.source_bytes[edit.start:edit.end] != edit.before:
            raise ModelError('plan_edit_preimage_mismatch', path=source.path)
    ordered = sorted(edits, key=lambda e: (e.start, e.end))
    for left, right in zip(ordered, ordered[1:]):
        if left.end > right.start or left.start == right.start:
            raise ModelError('plan_edits_overlap', path=source.path)
    raw = source.source_bytes
    for edit in reversed(ordered):
        raw = raw[:edit.start] + edit.after + raw[edit.end:]
    return parse_plan(raw, path=source.path, id_prefix=source.projections[0].data['id'].split('-')[0])


def _indented(text, indent):
    parts = text.split('\n')
    lines = [line + '\n' for line in parts[:-1]] + ([parts[-1]] if parts[-1] else [])
    return ''.join((' ' * indent + line if line.strip(' \t\n') else line)
                   for line in lines).encode('utf-8')


def replace_fields(source, updates, *, expected_file_sha256):
    _bound(source, expected_file_sha256)
    if type(updates) is not dict or any(type(k) is not str or type(v) is not dict for k, v in updates.items()):
        raise ModelError('plan_field_updates_required', path=source.path)
    edits, expected = [], {p.data['id']: p.data for p in source.projections}
    fixed = {'id', 'artifact_type', 'schema_version', 'id_scheme', 'parent_id', 'plan_id', 'children'}
    for identity, fields in updates.items():
        section = source.section(identity)
        value = section.artifact.data
        metadata_bytes = section.metadata.read(source.source_bytes)
        meta = parse_json_object(_body(metadata_bytes, section.indent, source=source.source_bytes,
            path=source.path, offset=section.metadata.start).encode('utf-8'))
        old_meta = dict(meta)
        for field, replacement in fields.items():
            if type(field) is not str or field in fixed:
                raise ModelError('plan_structural_edit_required', path=source.path)
            if field in value and canonical_json_bytes(value[field]) == canonical_json_bytes(replacement):
                continue
            expected[identity][field] = replacement
            span = {'title': section.title, 'display_id': section.display_id, 'implemented': section.checkbox,
                    'description': section.body}.get(field)
            if field in ('title', 'display_id', 'description'):
                if type(replacement) is not str or (field != 'description' and ('\n' in replacement or '\r' in replacement or not replacement.strip())):
                    raise ModelError('plan_text_required', path=source.path)
                raw = _indented(replacement, section.indent) if field == 'description' else replacement.encode('utf-8')
            elif field == 'implemented':
                if type(replacement) is not bool or span is None:
                    raise ModelError('plan_checkbox_required', path=source.path)
                raw = b'x' if replacement else b' '
            if span is not None:
                edits.append(SourceEdit(span.start, span.end, span.read(source.source_bytes), raw))
            if span is None or field in meta:
                meta[field] = replacement
        if canonical_json_bytes(meta) != canonical_json_bytes(old_meta):
            from .plan_json_spans import metadata_edits
            edits.extend(metadata_edits(section, metadata_bytes, old_meta, meta))
    result = replace_spans(source, edits, expected_file_sha256=expected_file_sha256)
    actual = {p.data['id']: p.data for p in result.projections}
    if canonical_json_bytes(actual) != canonical_json_bytes(expected):
        raise ModelError('plan_unrequested_projection_change', path=source.path)
    return result
