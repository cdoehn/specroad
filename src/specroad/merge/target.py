"""Native complete-project validation of exact virtual merge candidates."""
from hashlib import sha256

from ..model.canonical import canonical_json_bytes as jcs
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object as parsed
from ..validation import assess_validation
from ..recovery._validation import project_validation_report
from .metadata import verify_merge_metadata
from .conflict_schema import ROLES


from .target_values import MergeTarget


def _bound_bytes(raw, expected, label):
    if type(raw) is not bytes:
        raise ModelError('merge_target_' + label + '_bytes_required')
    if type(expected) is not str or sha256(raw).hexdigest() != expected:
        raise ModelError('merge_target_' + label + '_hash_mismatch')


def prepare_merge_target(metadata_raw, plan_raw, sources, *, history,
                         expected_metadata_sha256, expected_plan_sha256, services=None):
    """Rebuild all candidates, then execute native checks without a project write."""
    _bound_bytes(metadata_raw, expected_metadata_sha256, 'metadata')
    _bound_bytes(plan_raw, expected_plan_sha256, 'plan')
    candidate = verify_merge_metadata(metadata_raw, plan_raw, sources, history=history,
                                     expected_plan_sha256=expected_plan_sha256)
    metadata = candidate.data
    conflicts = list(metadata['conflicts'])
    validation, complete, valid, files = None, False, False, {}
    try:
        if metadata['metadata_complete']:
            files = candidate.files
            try:
                model, root, report = project_validation_report(files, services=services)
                if root != metadata['expected_target_model_root_sha256']:
                    raise ModelError('merge_target_model_root_mismatch')
                assessment = assess_validation(report,
                    fail_on=model.configuration.data['validation_policy'].get('fail_on', 'error'),
                    documents=model.documents)
                validation = assessment.as_dict()
                complete = report.complete
                valid = complete and report.data['model_valid'] is True and assessment.passed
                if not valid:
                    for stage in report.data['stages']:
                        for item in stage['diagnostics']:
                            conflicts.append({'stage': stage['stage'], **item})
                    if not conflicts:
                        conflicts.append({'reason': 'merge_target_validation_incomplete'})
            except ModelError as error:
                conflicts.append({'stage': 'native_project', **error.diagnostic()})
    finally:
        # Reobserve every native source even after a negative check or provider
        # failure. A stale source must never leave an apparently current result.
        for role in ROLES:
            verify_observation(getattr(sources, role))
    data = {'target_format_version': 'merge-target-validation-v1',
        'metadata_candidate_sha256': expected_metadata_sha256,
        'input_plan_sha256': expected_plan_sha256,
        'source_bindings_sha256': sources.sha256,
        'target_files_sha256': metadata['target_files_sha256'],
        'expected_target_model_root_sha256': metadata['expected_target_model_root_sha256'],
        'validation': validation, 'conflicts': conflicts,
        'checks_complete': complete, 'target_validated': bool(valid),
        'pending_gates': ([] if valid else ['target_validation']) + ['publication'],
        'ready': False, 'write_authorized': False, 'approval_granted': False}
    return MergeTarget._create(data, files if valid else {})


def verify_merge_target(target_raw, metadata_raw, plan_raw, sources, *, history,
                        expected_target_sha256, expected_metadata_sha256,
                        expected_plan_sha256, services=None):
    """Recompute a saved observation; neither its hashes nor success flags grant trust."""
    _bound_bytes(target_raw, expected_target_sha256, 'observation')
    stored = parsed(target_raw)
    current = prepare_merge_target(metadata_raw, plan_raw, sources, history=history,
        expected_metadata_sha256=expected_metadata_sha256,
        expected_plan_sha256=expected_plan_sha256, services=services)
    if jcs(stored) != current.canonical_bytes:
        raise ModelError('merge_target_binding_mismatch')
    return current

from ._recorded import verify_observation
