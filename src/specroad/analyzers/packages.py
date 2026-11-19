"""Passive complete reportpackages; import verifies data without a project."""
from dataclasses import dataclass
from hashlib import sha256

from ._values import decode, digest, encoded, extensions, hash_value, require, shape
from .identities import AnalysisRequestId
from .descriptors import AnalyzerDescriptor
from ._subject_binding import SUBJECT_BINDING, subject_header
from ._report_projection import RESULT_FIELDS, observation
from ._report_values import (check_findings, coverage_status, engine_values,
                             report_subjects, run_identity)
from .reports import AnalyzerReport
from .requests import AnalyzerRequest


def read_bound_report(raw, request):
    """The same request-bound validation for imported and worker observations."""
    return AnalyzerReport(raw, request)


def verify_worker_result(raw, request, *, analyzer, engine):
    """Validate an explicit worker response, without discovering/starting workers."""
    report = read_bound_report(raw, request)
    report.require_provenance(analyzer=analyzer, engine=engine)
    return report


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


def read_unbound_report(raw):
    """Check intrinsic integrity only; a missing request never becomes authority."""
    value = decode(raw)
    shape(value, (*RESULT_FIELDS, 'run_id', 'request_id', 'operational', 'result_sha256'))
    require(value['contract_version'] == value['report_version'] == '1.0.0', 'analyzer_unsupported_report')
    AnalysisRequestId(value['request_id'])
    hash_value(value['snapshot_sha256'], '/snapshot_sha256')
    run_identity(value['run_id'])
    entry = value['analyzer']
    shape(entry, ('descriptor', 'descriptor_sha256', 'capabilities'), '/analyzer')
    descriptor = AnalyzerDescriptor(encoded(entry['descriptor']))
    require(entry['descriptor_sha256'] == descriptor.sha256, 'analyzer_descriptor_hash_mismatch')
    descriptor.select_capabilities(entry['capabilities'])
    engine_values(value['engine'], entry)
    subjects = value['subjects']
    require(type(subjects) is list and bool(subjects), 'analyzer_subject_results_required')
    for index, subject in enumerate(subjects):
        at = '/subjects/' + str(index)
        shape(subject, (*SUBJECT_BINDING, 'subject_key', 'value_sha256', 'declared_language', 'status', 'payload'),
              at, optional=('normative_force', 'findings'))
        subject_header(subject, at)
    keys = {s['subject_key'] for s in subjects}
    findings = check_findings(value['findings'], keys)
    # This checks the report's own subject partition, not membership in an absent request.
    headers = [{k:v for k,v in s.items() if k not in ('status', 'payload', 'findings')} for s in subjects]
    report_subjects(subjects, {'subjects':headers}, findings)
    coverage_status(value)
    require(type(value['operational']) is dict, 'analyzer_operational_object_required', '/operational')
    extensions(value['extensions'])
    hash_value(value['result_sha256'], '/result_sha256')
    require(value['result_sha256'] == digest(observation(value)), 'analyzer_result_hash_mismatch')
    return value
