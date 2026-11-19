"""Read-only observations and freshness, separate from all normative evidence."""
from dataclasses import dataclass
from hashlib import sha256

from ..bundles.errors import BundleError
from ..changes._patch_pointer import _pointer
from ..cli.results import OperationFailure
from ..model.errors import ModelError
from ..query.selection import NormalizedQuery, select_query
from ..security import SafetyViolation
from ..srx import MISSING
from ..srx.errors import SrxError
from ..srx.pointers import resolve_tokens
from ._subject_source import _observe, _finish
from ._values import AnalyzerError, decode, digest, encoded, require, shape
from .packages import ReportPackage, read_bound_report, read_unbound_report
from .requests import AnalyzerRequest, create_request


class ProjectObservation:
    """One native observation for every selected report in an evaluation."""
    def __init__(self, root, configuration_id):
        self.source, self.snapshot, records = _observe(root)
        selected = select_query(records, NormalizedQuery(filters={}),
            project=self.source.configuration.data, configuration_id=configuration_id,
            partial=self.source if self.source is self.snapshot else None)
        self.artifacts = {r.identity.id:r.data for r in records if r.identity.id in selected.artifact_ids}

    def compare(self, request, supplied):
        shape(supplied, ('analyzers', 'settings', 'context', 'extensions'), '/current_inputs')
        require(type(supplied['context']) is list, 'analyzer_context_array_required')
        original = request.data
        # Validate independently supplied input values using the native request contract.
        # Keeping old subjects here validates the inputs; freshness is checked below.
        current = create_request(analyzers=supplied['analyzers'], subjects=original['subjects'],
            context=dict(resources=supplied['context'], subject_keys=original['context']['subject_keys']),
            settings=supplied['settings'], extensions=supplied['extensions'],
            analysis_id=request.analysis_id).data
        changed_inputs = [k for k in ('analyzers', 'context', 'settings', 'extensions')
                          if encoded(current[k]) != encoded(original[k])]
        changed_subjects = []
        for subject in original['subjects']:
            artifact = self.artifacts.get(subject['artifact_id'])
            changed = artifact is None
            if artifact is not None:
                tokens = _pointer(subject['field_pointer'], '/field_pointer')
                try:
                    value = resolve_tokens(artifact, tokens, rule_id='analyzer-currentness')
                except SrxError:
                    value = MISSING
                changed = (value is MISSING or artifact['revision'] != subject['artifact_revision']
                    or digest(artifact) != subject['artifact_sha256']
                    or (value is not MISSING and (digest(value) != subject['value_sha256']
                        or encoded(value) != encoded(subject['value'])))
                    or artifact.get('language') != subject['declared_language']
                    or ('normative_force' in artifact) != ('normative_force' in subject)
                    or artifact.get('normative_force') != subject.get('normative_force'))
            if changed:
                changed_subjects.append(subject['subject_key'])
        return sorted(changed_subjects), changed_inputs

    def finish(self):
        _finish(self.source, self.snapshot)


def source_failure(error):
    if isinstance(error, AnalyzerError):
        return error.reason, error.exit_code
    if isinstance(error, SafetyViolation):
        return 'analyzer_project_security_boundary', 7
    if isinstance(error, OperationFailure):
        return 'analyzer_project_preflight_failed', int(error.kind)
    if isinstance(error, OSError):
        return 'analyzer_project_environment', 5
    changed = {'configuration_changed', 'relation_source_changed', 'relation_index_project_mismatch',
        'relation_index_membership_changed', 'relation_index_source_changed',
        'show_source_changed', 'show_source_disappeared', 'bundle_partial_read_changed'}
    return error.reason, 6 if error.reason in changed else getattr(error, 'exit_code', 3)


def disagreements(rows):
    """Expose structural differences without guessing adapter semantics or voting."""
    groups = {}
    for index, row in enumerate(rows):
        report = row['report']
        if report is None:
            continue
        for subject in report['subjects']:
            key = subject['subject_key']
            findings = [{k:v for k,v in f.items() if k != 'finding_id'}
                        for f in report['findings'] if key in f['subject_keys']]
            projection = dict(status=subject['status'], payload=subject['payload'],
                              findings=sorted(findings, key=encoded))
            for capability in report['analyzer']['capabilities']:
                groups.setdefault((key, capability), []).append(dict(
                    report_index=index, run_id=report['run_id'], analyzer=report['analyzer'],
                    engine=report['engine'], observation=projection, observation_sha256=digest(projection)))
    return [dict(code='analyzer_disagreement', comparison='structural_subject_observation',
                 subject_key=key, capability=capability, variants=variants)
            for (key, capability), variants in sorted(groups.items())
            if len({v['observation_sha256'] for v in variants}) > 1]


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
