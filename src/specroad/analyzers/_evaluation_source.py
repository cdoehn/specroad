"""Native current-input observation; no writes or report authority."""
from ..changes._patch_pointer import _pointer
from ..query.selection import NormalizedQuery, select_query
from ..srx import MISSING
from ..srx.pointers import resolve_tokens
from ._subject_source import _observe, _finish
from ..security import SafetyViolation
from ..cli.results import OperationFailure
from ..srx.errors import SrxError
from ._values import AnalyzerError, digest, encoded, require, shape
from .requests import create_request

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
