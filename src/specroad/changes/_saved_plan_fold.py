"""Native saved-plan reduction shared by publication and historical readers.

No writer, authority, current verifier or target-success result is involved.
All operation order, preconditions, result declarations and metadata are checked
by the same native reducers used before publication.
"""
from .lifecycle import prepare_plan_lifecycle, prepare_change_lifecycle
from .reviews import review_mode, prepare_review_candidates
from ._normalization_target import normalization_mode
from .target_values import TargetError


def fold_saved_plan(plan, model, *, observed_base_root, observed_scope):
    from .baselines import baseline_mode, prepare_baseline_candidates
    from .evidence import evidence_mode, prepare_evidence_candidates
    from .evidence_import import import_mode, prepare_import_candidates
    value = plan.data
    normalize = normalization_mode(value['operations'])
    baseline = baseline_mode(value['operations'])
    evidence = evidence_mode(value['operations'])
    imported = import_mode(value['operations'])
    if evidence or imported:
        prepare = prepare_import_candidates if imported else prepare_evidence_candidates
        folded = prepare(model, value['operations'],
            metadata_policy_version=value['metadata_policy_version'], actor=value['actor'],
            planned_at=value['planned_at'], preconditions=value['preconditions'])
        if {c.id: c.candidate_sha256 for c in folded.candidates} != {
                r['artifact']['id']: r['sha256'] for r in value['result_artifacts']}:
            raise TargetError('declared_evidence_result_mismatch', pointer='/result_artifacts')
    elif baseline:
        folded = prepare_baseline_candidates(model, value['operations'],
            metadata_policy_version=value['metadata_policy_version'], actor=value['actor'],
            planned_at=value['planned_at'], preconditions=value['preconditions'])
        if {c.id: c.candidate_sha256 for c in folded.candidates} != {
                r['artifact']['id']: r['sha256'] for r in value['result_artifacts']}:
            raise TargetError('declared_baseline_result_mismatch')
    elif review_mode(value['operations']):
        folded = prepare_review_candidates(model.artifacts, value['operations'],
            metadata_policy_version=value['metadata_policy_version'], actor=value['actor'],
            planned_at=value['planned_at'], preconditions=value['preconditions'],
            source_files=model.source_files, profile=model.profile, **model.reservations)
        actual = {c.id: c.candidate_sha256 for c in folded.candidates}
        expected = {r['artifact']['id']: r['sha256'] for r in value['result_artifacts']}
        if actual != expected:
            raise TargetError('declared_review_result_mismatch', pointer='/result_artifacts')
    elif normalize:
        # Keep all ordinary source/precondition/history checks, but do not fold
        # representation changes as artifact edits or stamp revision/metadata.
        folded = prepare_change_lifecycle(model.artifacts, [],
            metadata_policy_version=value['metadata_policy_version'], actor=value['actor'],
            planned_at=value['planned_at'], preconditions=value['preconditions'],
            source_files=model.source_files, **model.reservations)
    else:
        folded = prepare_plan_lifecycle(plan, model.artifacts, observed_base_root=observed_base_root,
            observed_scope=observed_scope, source_files=model.source_files, **model.reservations)
    return folded, normalize, baseline
