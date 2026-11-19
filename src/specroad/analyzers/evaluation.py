"""Read-only observations and freshness, separate from all normative evidence."""
from dataclasses import dataclass
from hashlib import sha256

from ..bundles.errors import BundleError
from ..cli.results import OperationFailure
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..srx.errors import SrxError
from ._values import AnalyzerError, decode, encoded, require
from .packages import ReportPackage, read_bound_report, read_unbound_report
from .requests import AnalyzerRequest
from ._evaluation_source import ProjectObservation, source_failure
from ._evaluation_projection import disagreements








@dataclass(frozen=True, init=False)
class AnalysisEvaluation:
    _encoded: bytes
    originals: tuple
    _request: object

    def __init__(self, value, originals, request):
        object.__setattr__(self, '_encoded', encoded(value))
        object.__setattr__(self, 'originals', tuple(originals))
        object.__setattr__(self, '_request', request)

    def reevaluate(self, *, project=None, current_inputs=None, configuration_id=None):
        """Return a fresh separate view over exactly the same original input bytes."""
        return evaluate_reports(self.originals, request=self._request, project=project,
            current_inputs=current_inputs, configuration_id=configuration_id)

    @property
    def data(self):
        return decode(self._encoded)

    @property
    def canonical_bytes(self):
        return self._encoded


def evaluate_reports(inputs, *, request=None, project=None, current_inputs=None, configuration_id=None):
    """Evaluate explicit bytes. Current inputs are independent caller-supplied JSON.

    No paths in requests/reports are interpreted; no workers, writes or approvals.
    A valid unbound report remains unavailable, even with a readable project.
    """
    require(type(inputs) in (list, tuple) and bool(inputs) and all(type(x) is bytes for x in inputs),
            'analyzer_report_inputs_required', exit_code=2)
    require(request is None or type(request) is AnalyzerRequest, 'analyzer_request_required', exit_code=2)
    originals = tuple(inputs)
    rows, bindings = [], []
    for input_index, raw in enumerate(originals):
        source_hash = sha256(raw).hexdigest()
        try:
            parsed = decode(raw)
            if 'package_version' in parsed:
                package = ReportPackage(raw, request=request)
                values = [r.data for r in package.reports]
                bound = package.request
            else:
                values = [read_bound_report(raw, request).data if request is not None else read_unbound_report(raw)]
                bound = request
            for report_index, value in enumerate(values):
                rows.append(dict(input_index=input_index, report_index=report_index, source_sha256=source_hash,
                    currentness='unavailable', reason='analyzer_current_inputs_unavailable' if bound else 'analyzer_request_unavailable',
                    failure_code=None, request_binding_verified=bound is not None, report=value,
                    changed_subject_keys=[], changed_inputs=[]))
                bindings.append(bound)
        except AnalyzerError as error:
            rows.append(dict(input_index=input_index, report_index=None, source_sha256=source_hash,
                currentness='invalid', reason=error.reason, failure_code=error.exit_code,
                request_binding_verified=False, report=None, changed_subject_keys=[], changed_inputs=[]))
            bindings.append(None)
    candidates = [i for i, binding in enumerate(bindings) if binding is not None]
    if candidates and project is not None and current_inputs is not None:
        failures = (ModelError, BundleError, SrxError, OperationFailure, SafetyViolation, OSError)
        try:
            supplied = decode(encoded(current_inputs))
            observation = ProjectObservation(project, configuration_id)
            for index in candidates:
                keys, fields = observation.compare(bindings[index], supplied)
                rows[index].update(currentness='stale' if keys or fields else 'current',
                    reason='analyzer_inputs_changed' if keys or fields else None,
                    changed_subject_keys=keys, changed_inputs=fields)
            observation.finish()
        except failures as error:
            reason, code = source_failure(error)
            for index in candidates:
                rows[index].update(currentness='unavailable', reason=reason, failure_code=code,
                    changed_subject_keys=[], changed_inputs=[])
    value = dict(format_version='1.0.0', reports=rows, disagreements=disagreements(rows),
                 all_reports_current=all(r['currentness'] == 'current' for r in rows))
    return AnalysisEvaluation(value, originals, request)
