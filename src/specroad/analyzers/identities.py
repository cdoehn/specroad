"""Analysis identity allocation is separate from normative write identities."""
from dataclasses import dataclass
import re
import secrets

from ..changes.request_ids import NormativeRequestId as WriteRequestId
from ..model.identity_tokens import encode128
from ._values import AnalyzerError, require


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


__all__ = ('AnalysisRequestId', 'WriteRequestId', 'prepare_analysis_id')
