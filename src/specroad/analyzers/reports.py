"""Request-bound reports are observations, never Evidence or write authority."""
from dataclasses import dataclass
from hashlib import sha256
import secrets

from ..model.identity_tokens import encode128
from ._values import AnalyzerError, decode, digest, encoded, extensions, hash_value, require, shape
from ._report_values import (check_findings, coverage_status, engine_values,
                             exact_coverage, report_subjects, run_identity)
from .requests import AnalyzerRequest

RESULT_FIELDS = ('contract_version', 'report_version', 'snapshot_sha256', 'analyzer',
                 'engine', 'subjects', 'coverage', 'run_status', 'findings', 'extensions')


def observation(value):
    return {key:value[key] for key in RESULT_FIELDS}


def provenance(value):
    return {key:value[key] for key in ('analyzer', 'engine')}


def operational(value):
    return value['operational']


@dataclass(frozen=True, init=False)
class AnalyzerReport:
    _encoded: bytes
    _original: bytes

    def __init__(self, raw, request):
        require(type(request) is AnalyzerRequest, 'analyzer_request_required', exit_code=2)
        value = decode(raw)
        shape(value, (*RESULT_FIELDS, 'run_id', 'request_id', 'operational', 'result_sha256'))
        require(value['contract_version'] == value['report_version'] == '1.0.0', 'analyzer_unsupported_report')
        run_identity(value['run_id'])
        expected = request.data
        require(value['request_id'] == expected['request_id'] and value['snapshot_sha256'] == expected['snapshot_sha256'],
                'analyzer_report_request_mismatch')
        require(type(value['analyzer']) is dict and any(
                encoded(value['analyzer']) == encoded(a) for a in expected['analyzers']),
                'analyzer_report_descriptor_mismatch', '/analyzer')
        engine_values(value['engine'], value['analyzer'])
        findings = check_findings(value['findings'], {s['subject_key'] for s in expected['subjects']})
        report_subjects(value['subjects'], expected, findings)
        coverage_status(value)
        require(type(value['operational']) is dict, 'analyzer_operational_object_required', '/operational')
        extensions(value['extensions'])
        hash_value(value['result_sha256'], '/result_sha256')
        require(value['result_sha256'] == digest(observation(value)), 'analyzer_result_hash_mismatch', '/result_sha256')
        object.__setattr__(self, '_encoded', encoded(value))
        object.__setattr__(self, '_original', bytes(raw))

    def require_provenance(self, *, analyzer, engine):
        # Expected data cannot mutate owned observations or select a winner.
        expected = decode(encoded(dict(analyzer=analyzer, engine=engine)))
        actual = self.provenance
        require(encoded(expected['analyzer']) == encoded(actual['analyzer']), 'analyzer_provenance_mismatch', exit_code=6)
        require(encoded(expected['engine']) == encoded(actual['engine']), 'analyzer_engine_mismatch', exit_code=6)

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
    def full_file_sha256(self):
        return sha256(self._original).hexdigest()

    @property
    def result_sha256(self):
        return self.data['result_sha256']

    @property
    def observation(self):
        return observation(self.data)

    @property
    def provenance(self):
        return provenance(self.data)

    @property
    def operational(self):
        return operational(self.data)


def subject_result(subject, *, status, payload, findings=None):
    """Copy original bindings without copying the complete value a second time."""
    value = {k:v for k,v in subject.items() if k != 'value'}
    value.update(status=status, payload=payload)
    if findings is not None:
        value['findings'] = findings
    return decode(encoded(value))


def create_report(request, *, analyzer_id, engine, subjects, run_status, findings=(),
                  operational=None, extensions=None, run_id=None):
    require(type(request) is AnalyzerRequest, 'analyzer_request_required', exit_code=2)
    require(type(findings) in (list, tuple), 'analyzer_findings_array_required', exit_code=2)
    matches = [a for a in request.data['analyzers'] if a['descriptor']['analyzer_id'] == analyzer_id]
    require(len(matches) == 1, 'analyzer_not_requested', exit_code=2)
    if run_id is None:
        try:
            run_id = 'AR-' + encode128(secrets.token_bytes(16))
        except OSError as error:
            raise AnalyzerError('analysis_entropy_unavailable', exit_code=5) from error
    value = decode(encoded(dict(contract_version='1.0.0', report_version='1.0.0', run_id=run_id,
        **request.binding, analyzer=matches[0], engine=engine, subjects=subjects,
        run_status=run_status, findings=list(findings), operational={} if operational is None else operational,
        extensions={} if extensions is None else extensions)))
    # Bad subject shape remains a model error, never an accidental KeyError.
    finding_map = check_findings(value['findings'], {s['subject_key'] for s in request.data['subjects']})
    report_subjects(value['subjects'], request.data, finding_map)
    value['coverage'] = exact_coverage(value['subjects'])
    value['result_sha256'] = digest(observation(value))
    return AnalyzerReport(encoded(value), request)
