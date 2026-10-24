"""Exact time and closed manifest projection from an evaluated export."""
from hashlib import sha256

from ..model.audit_values import UtcTimestamp
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError


def snapshot_time(artifacts):
    """Compare UTC calendar fields and decimal digits without numeric rounding."""
    greatest = None
    for artifact in artifacts:
        value = artifact.get('updated_at')
        UtcTimestamp(value)
        calendar = tuple(int(value[start:end]) for start, end in
                         ((0, 4), (5, 7), (8, 10), (11, 13), (14, 16), (17, 19)))
        fraction = value[20:-1].rstrip('0') if value[19:20] == '.' else ''
        candidate = calendar, tuple(int(digit) for digit in fraction)
        if greatest is None or candidate > greatest:
            greatest = candidate
    if greatest is None:
        return '1970-01-01T00:00:00Z'
    (year, month, day, hour, minute, second), digits = greatest
    fraction = ''.join(str(digit) for digit in digits)
    return (f'{year:04}-{month:02}-{day:02}T{hour:02}:{minute:02}:{second:02}'
            + ('.' + fraction if fraction else '') + 'Z')


class ExportLossConflict(ModelError):
    exit_code = 6


class ExportLosses:
    def __init__(self):
        self._items = {}

    def add(self, identity, pointer, reason, details=None):
        import re
        if (type(identity) is not str or not identity or type(pointer) is not str
                or pointer and not pointer.startswith('/') or re.search(r'~(?![01])', pointer)
                or type(reason) is not str or re.fullmatch('[a-z][a-z0-9_]*', reason) is None):
            raise ModelError('export_loss_identity_invalid')
        details = {} if details is None else details
        if type(details) is not dict:
            raise ModelError('export_loss_details_invalid')
        encoded = canonical_json_bytes(details)
        key = identity, pointer, reason
        if key in self._items and self._items[key] != encoded:
            raise ExportLossConflict('export_loss_conflict')
        self._items[key] = encoded

    @property
    def rows(self):
        import json
        return [{'resource_id': key[0], 'pointer': key[1], 'reason': key[2],
                 'format_details': json.loads(self._items[key])}
                for key in sorted(self._items, key=lambda k: tuple(s.encode('utf-8') for s in k))]


def manifest_bytes(*, output_format, mapping, format_profile, native, artifacts,
                   losses, attachments, include_attachments, fail_on_loss, output):
    from .. import __version__
    rows = losses.rows
    return canonical_json_bytes({
        'manifest_version': 'exchange-export-v1', 'format': output_format,
        'format_version': {'reqif': '1.2', 'reqifz': 'reqifz-container-v1',
                           'csv': 'csv-profile-v1', 'ndjson': '1.0.0'}[output_format],
        'mapping': mapping.binding(), 'format_profile': format_profile,
        'scope_descriptor': native.data['scope_descriptor'],
        'boundary_references': native.data['boundary_references'],
        'model_root_sha256': native.sha256, 'snapshot_at': snapshot_time(artifacts),
        'tool_version': __version__,
        'options': {'include_attachments': include_attachments, 'fail_on_loss': fail_on_loss},
        'included_ids': sorted((a['id'] for a in artifacts), key=lambda s: s.encode('utf-8')),
        'excluded_contents': [{k: r[k] for k in ('resource_id', 'pointer', 'reason')} for r in rows],
        'losses': rows, 'attachments': [{**a.data, 'included': include_attachments} for a in attachments],
        'output_sha256': sha256(output).hexdigest()})
