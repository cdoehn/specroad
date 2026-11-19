"""Passive complete reportpackages; import verifies data without a project."""
from dataclasses import dataclass
from hashlib import sha256

from ._values import decode, encoded, hash_value, require, shape
from .reports import AnalyzerReport
from ._report_protocol import read_bound_report, verify_worker_result, read_unbound_report

__all__ = ('ReportPackage', 'create_package', 'read_bound_report', 'verify_worker_result', 'read_unbound_report')
from .requests import AnalyzerRequest






@dataclass(frozen=True, init=False)
class ReportPackage:
    _encoded: bytes
    _original: bytes
    request: AnalyzerRequest
    reports: tuple

    def __init__(self, raw, *, request=None):
        value = decode(raw)
        shape(value, ('package_version', 'request', 'reports'))
        require(value['package_version'] == '1.0.0', 'analyzer_unsupported_package')
        embedded = AnalyzerRequest(encoded(value['request']))
        if request is not None:
            require(type(request) is AnalyzerRequest, 'analyzer_request_required', exit_code=2)
            require(request.canonical_bytes == embedded.canonical_bytes, 'analyzer_package_request_mismatch')
        require(type(value['reports']) is list and bool(value['reports']), 'analyzer_package_reports_required')
        reports = tuple(read_bound_report(encoded(item), embedded) for item in value['reports'])
        runs = [report.data['run_id'] for report in reports]
        require(len(set(runs)) == len(runs), 'analyzer_package_duplicate_run')
        expected = {a['descriptor']['analyzer_id'] for a in embedded.data['analyzers']}
        actual = {report.data['analyzer']['descriptor']['analyzer_id'] for report in reports}
        require(expected == actual, 'analyzer_package_missing_analyzer')
        object.__setattr__(self, '_encoded', encoded(value))
        object.__setattr__(self, '_original', bytes(raw))
        object.__setattr__(self, 'request', embedded)
        object.__setattr__(self, 'reports', reports)

    def require_transport_hash(self, expected):
        hash_value(expected, '/full_file_sha256')
        require(expected == self.full_file_sha256, 'analyzer_transport_hash_mismatch', exit_code=6)

    @property
    def data(self):
        return decode(self._encoded)

    @property
    def canonical_bytes(self):
        return self._encoded

    @property
    def original_bytes(self):
        return self._original

    @property
    def full_file_sha256(self):
        return sha256(self._original).hexdigest()


def create_package(request, reports):
    require(type(request) is AnalyzerRequest, 'analyzer_request_required', exit_code=2)
    require(type(reports) in (list, tuple) and all(type(r) is AnalyzerReport for r in reports),
            'analyzer_reports_required', exit_code=2)
    return ReportPackage(encoded(dict(package_version='1.0.0', request=request.data,
                                     reports=[r.data for r in reports])))
