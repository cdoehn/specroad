"""Explain run candidates and their context freshness without aggregating results.

Historical and unbound records remain visible. Only complete key/product/config
matches belong to a run; an absent expected observation is missing, not stale.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from .run_selection import select_verification_runs
from ._run_dispositions import selected_run_dispositions


@dataclass(frozen=True, init=False)
class VerificationRunAssessment:
    """Owned disposition report; neither a result aggregate nor an approval."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use assess_verification_runs')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Run dispositions are not verification success or approval')


def assess_verification_runs(model, evaluation, *, configuration_id,
                             scope_descriptor=None, scope_bindings=None):
    """Assess the native selection against original model and descriptor bytes.

    The native Appendix L projection covers Requirements, Verification and Test
    records. Other subject types retain candidates with unresolved freshness;
    their context hash is not guessed from an audit hash or a new projection.
    Input bytes/roles, replacement decisions and final results are separate gates.
    """
    from ..changes.target_model import TargetModel
    if type(model) is not TargetModel:
        raise ModelError('verification_target_model_required')
    model = model.snapshot()
    selection = select_verification_runs(model, evaluation, configuration_id=configuration_id,
        scope_descriptor=scope_descriptor, scope_bindings=scope_bindings)
    selected = selection.data
    eligible = selected['run_selection_evaluated']
    checks, dispositions, missing_runs, unresolved = selected_run_dispositions(
        selection._encoded, tuple((d.path, d.content) for d in model.documents), configuration_id)
    report = {'format_version': 'verification-run-assessment-v1',
        'validation_scope': 'supplied_model_run_dispositions',
        'selection_sha256': selection.sha256, 'selection': selected,
        'project_id': selected['project_id'], 'input_sha256': selected['input_sha256'],
        'evaluation_sha256': selected['evaluation_sha256'],
        'checks': checks, 'evidence_dispositions': dispositions,
        'missing_runs': missing_runs,
        'diagnostics': [{'code': 'SRV176', 'severity': 'warning',
                         'reason': 'required_run_missing', **row} for row in missing_runs],
        'assessment_status': 'assessed' if eligible else 'incomplete',
        'run_selection_evaluated': eligible, 'context_freshness_evaluated': eligible and not unresolved,
        'input_bytes_verified': False, 'input_roles_verified': False, 'project_files_verified': False,
        'project_required_checks_complete': False, 'run_replacements_evaluated': False,
        'result_aggregation_evaluated': False, 'full_verification_evaluated': False,
        'external_run_verified': False, 'release_readiness_evaluated': False,
        'test_code_executed': False, 'write_authorized': False, 'approval_granted': False}
    result = object.__new__(VerificationRunAssessment)
    object.__setattr__(result, '_encoded', canonical_json_bytes(report))
    return result
