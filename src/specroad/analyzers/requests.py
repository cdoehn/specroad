"""Owned datatransport requests; no write idempotency, reports or worker launch."""
from dataclasses import dataclass
import re
import secrets

from ..changes.request_ids import NormativeRequestId as WriteRequestId
from ..model.identity_tokens import encode128
from ._values import AnalyzerError, decode, digest, encoded, hash_value, require
from .descriptors import AnalyzerDescriptor
from ._request_values import SNAPSHOT_FIELDS, validate_snapshot


@dataclass(frozen=True)
class AnalysisRequestId:
    value: str

    def __post_init__(self):
        require(type(self.value) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', self.value) is not None,
                'invalid_analysis_request_id', '/request_id', exit_code=2)

    @property
    def namespace(self):
        return 'analysis'


def prepare_analysis_id(value=None):
    """Allocate once before snapshot work; callers can retain this owned token."""
    if value is None:
        try:
            return AnalysisRequestId('AN-' + encode128(secrets.token_bytes(16)))
        except OSError as error:
            raise AnalyzerError('analysis_entropy_unavailable', exit_code=5) from error
    if type(value) is AnalysisRequestId:
        return value
    return AnalysisRequestId(value)


@dataclass(frozen=True, init=False)
class AnalyzerRequest:
    _encoded: bytes

    def __init__(self, raw):
        value = decode(raw)
        validate_snapshot(value)
        try:
            AnalysisRequestId(value['request_id'])
        except AnalyzerError as error:
            raise AnalyzerError(error.reason, pointer='/request_id') from error
        hash_value(value['snapshot_sha256'], '/snapshot_sha256')
        require(value['snapshot_sha256'] == digest({k:value[k] for k in SNAPSHOT_FIELDS}),
                'analyzer_snapshot_hash_mismatch', '/snapshot_sha256')
        object.__setattr__(self, '_encoded', encoded(value))

    def require_binding(self, *, request_id, snapshot_sha256):
        # Two independent coordinates, never a write-idempotency lookup.
        supplied = request_id if type(request_id) is AnalysisRequestId else AnalysisRequestId(request_id)
        hash_value(snapshot_sha256, '/snapshot_sha256')
        expected = self.binding
        require(supplied.value == expected['request_id'], 'analysis_id_mismatch', exit_code=6)
        require(snapshot_sha256 == expected['snapshot_sha256'], 'analysis_snapshot_mismatch', exit_code=6)

    @property
    def data(self):
        return decode(self._encoded)

    @property
    def canonical_bytes(self):
        return self._encoded

    @property
    def analysis_id(self):
        return AnalysisRequestId(self.data['request_id'])

    @property
    def binding(self):
        value = self.data
        return {'request_id':value['request_id'], 'snapshot_sha256':value['snapshot_sha256']}


def analyzer_binding(descriptor, capabilities):
    require(type(descriptor) is AnalyzerDescriptor, 'analyzer_descriptor_required', exit_code=2)
    return {'descriptor':descriptor.data, 'descriptor_sha256':descriptor.sha256,
            'capabilities':list(descriptor.select_capabilities(capabilities))}


def create_request(*, analyzers, subjects, context, settings, extensions, analysis_id=None):
    """Use complete explicit data; parsing and repeated reads never mint IDs."""
    identity = prepare_analysis_id(analysis_id)
    value = {'contract_version':'1.0.0', 'analyzers':analyzers, 'subjects':subjects,
             'context':context, 'settings':settings, 'extensions':extensions}
    value = decode(encoded(value))
    value.update(request_id=identity.value, snapshot_sha256=digest(value))
    return AnalyzerRequest(encoded(value))


__all__ = ('AnalysisRequestId', 'WriteRequestId', 'AnalyzerRequest', 'prepare_analysis_id',
           'analyzer_binding', 'create_request')
