"""Stored Baseline projection with fresh read-only integrity observation."""
from ..model.errors import ModelError
from ..model.record_schemas import validate_record_fields
from ..security import ProjectBoundary
from ..storage.json_syntax import parse_json_object
from .verification import verify_baseline_snapshot


def _record(boundary, raw):
    if type(boundary) is not ProjectBoundary:
        raise ModelError('snapshot_object_boundary_required')
    if type(raw) is not bytes:
        raise ModelError('baseline_record_bytes_required')
    value = parse_json_object(raw)
    validate_record_fields(value, expected_type='baseline')
    return value


def show_baseline_snapshot(boundary, baseline_record):
    """Return stored data and a freshly computed status, without writing.

    A well-formed record can be shown with a failed integrity check. Malformed
    records, unsafe paths and host I/O failures retain their normal exceptions.
    No prior observation is accepted as a substitute for fresh verification.
    """
    record = _record(boundary, baseline_record)
    try:
        checked = verify_baseline_snapshot(boundary, baseline_record)
    except ModelError as error:
        integrity = {'status': 'failed', 'snapshot_integrity_verified': False,
                     'diagnostics': [error.diagnostic()], 'verification': None}
    else:
        integrity = {'status': 'verified', 'snapshot_integrity_verified': True,
                     'diagnostics': [], 'verification': checked}
    return {'format_version': 'baseline-show-v1', 'baseline': record,
            'integrity': integrity}
