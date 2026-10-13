"""Git-derived seeds with the existing loaded-model dependency checks.

Owned comparison sources and explicit profile paths only. No CLI discovery,
live-file freshness claim, persistent Work, full-project or full-lint approval.
"""
from hashlib import sha256

from ..graph.comparison_values import ComparisonResult
from ..lint import lint_core
from ..model.errors import ModelError
from ..model.paths import PathClass, classify_path
from ..profiles import ProfileResource, compose_profiles
from ..validation import ModelDocument, ValidationResources, assess_validation, validate_model
from .comparison_sources import ComparisonSourceSnapshot
from .semantic_diff import compare_semantic


def _profiles(snapshot, profile_paths, core_key, cli_profiles):
    if (type(profile_paths) is not dict or not profile_paths
            or any(type(key) is not str or type(path) is not str for key, path in profile_paths.items())):
        raise ModelError('changed_profile_paths_required')
    if len({path.casefold() for path in profile_paths.values()}) != len(profile_paths):
        raise ModelError('changed_duplicate_profile_path')
    files = dict(snapshot.resources)
    profiles = []
    for key, path in sorted(profile_paths.items()):
        if classify_path(path, snapshot.configuration) is not PathClass.PROFILE or path not in files:
            raise ModelError('changed_profile_source_missing', path=path)
        profile = ProfileResource(files[path])
        if profile.key != key:
            raise ModelError('changed_profile_identity_mismatch', path=path)
        profiles.append(profile)
    resources = ValidationResources(files['specroad.json'], profile_resources=profiles,
        core_key=core_key, cli_profiles=cli_profiles)
    profile = compose_profiles(profiles, core_key=core_key,
        project_profiles=snapshot.configuration.data['profiles'], cli_profiles=cli_profiles)
    if set(profile_paths) != set(profile.profile_chain):
        raise ModelError('changed_profile_paths_mismatch')
    return profile, resources


def check_changed_sources(before, after, *, profile_paths, core_key,
                          cli_profiles=(), gates=(), fail_on='error', strict=False):
    """Run loaded-model validation and Core lint over dependency-expanded seeds.

    The base must be a captured Git commit. Profiles come from exact current
    snapshot bytes, never caller-substituted or current-tree fallback data.
    Profile/configuration changes and removals conservatively seed all current
    artifacts; unsupported changed normative resource kinds fail explicitly.
    Literal/linguistic lint and unavailable semantic services remain unclaimed.
    """
    if type(before) is not ComparisonSourceSnapshot or type(after) is not ComparisonSourceSnapshot:
        raise ModelError('changed_comparison_sources_required')
    if before.kind != 'git' or before.commit_id is None:
        raise ModelError('changed_git_base_required')
    if (before.configuration.project_id != after.configuration.project_id
            or before.configuration.id_prefix != after.configuration.id_prefix):
        raise ModelError('comparison_project_mismatch')
    if type(fail_on) is not str or fail_on not in ('error', 'warning') or type(strict) is not bool:
        raise ModelError('changed_fail_policy_invalid')
    difference = compare_semantic(before.inputs, after.inputs,
        before_configuration=before.configuration, after_configuration=after.configuration).data
    profile, resources = _profiles(after, profile_paths, core_key, cli_profiles)
    left, right = dict(before.uncompared_resources), dict(after.uncompared_resources)
    resource_changes = sorted(path for path in left.keys() | right.keys() if left.get(path) != right.get(path))
    profile_files = set(profile_paths.values())
    for path in resource_changes:
        if path not in profile_files:
            raise ModelError('changed_resource_semantics_unavailable', path=path)
    current = {record.identity.id for record in after.inputs.records}
    changed = sorted(item['artifact_id'] for item in difference['changes'])
    removed = difference['inventory_delta']['removed_ids']
    seeds = current.intersection(changed)
    reasons = ['changed_artifacts'] if seeds else []
    if difference['project_configuration']['changed']:
        seeds.update(current)
        reasons.append('project_configuration_changed_conservative')
    if resource_changes:
        seeds.update(current)
        reasons.append('profile_resources_changed_conservative')
    if removed:
        # A removed target can affect incoming references or arbitrary rule
        # reads. Without narrower certified dependency observations, retain all.
        seeds.update(current)
        reasons.append('removed_artifacts_conservative')
    selected = tuple(sorted(seeds))
    details = {'observation_version': 'changed-checks-v1', 'mode': 'changed_only',
        'check_scope': 'loaded_model_validation_and_core_lint',
        'project_id': after.configuration.project_id, 'base_commit': before.commit_id,
        'before_source_sha256': before.sha256, 'after_source_sha256': after.sha256,
        'comparison_sha256': ComparisonResult(difference).sha256,
        'profile_resources_sha256': resources.sha256,
        'profile_paths': dict(sorted(profile_paths.items())),
        'changed_artifact_ids': changed, 'removed_artifact_ids': removed,
        'changed_resource_paths': resource_changes,
        'configuration_changed': difference['project_configuration']['changed'],
        'seed_artifact_ids': list(selected), 'seed_reasons': reasons,
        'checked_artifact_ids': [], 'dependency_artifact_ids': [],
        'structural_scope': 'not_run', 'validation_scope': 'not_run',
        'supplied_artifact_ids': sorted(current),
        'artifact_bindings': [{'path': record.path, 'sha256': sha256(record.source_bytes).hexdigest()}
                              for record in sorted(after.inputs.records, key=lambda record: record.path)],
        'validation': None, 'validation_assessment': None, 'core_lint': None,
        'checks_complete': False, 'passed': None,
        'full_project_validation': False, 'full_lint': False,
        'project_files_verified': False, 'atomic_snapshot': False,
        'approval_granted': False, 'write_authorized': False}
    if not selected:
        details['status'] = 'no_current_artifacts' if changed or reasons else 'no_changes'
        return ComparisonResult(details)
    documents = tuple(ModelDocument(record.path, record.source_bytes) for record in after.inputs.records)
    report = validate_model(documents, profile=profile, selected_ids=selected,
                            gates=gates, resources=resources)
    assessment = assess_validation(report, fail_on=fail_on, strict=strict, documents=documents)
    validation = report.data
    checked = validation['checked_ids']
    scope_checked = any(stage['stage'] == 'scope' and stage['status'] == 'passed'
                        for stage in validation['stages'])
    lint = (lint_core(after.inputs.records, selected_ids=checked, profile=profile,
                      fail_on=fail_on, strict=strict) if scope_checked and checked else None)
    complete = report.complete and lint is not None
    assessed = assessment.as_dict()
    # Missing services keep completion unknown, but do not erase an already
    # observed warning that reaches the effective failure threshold.
    warning_failed = (assessed['fail_on'] == 'warning'
                      and any(d.severity == 'warning' for d in assessment.diagnostics))
    failed = (validation['model_valid'] is False or (complete and not assessment.passed)
              or warning_failed
              or (lint is not None and not lint['core_checks_passed']))
    details.update(status='completed' if complete else 'incomplete',
        validation=validation, validation_assessment=assessed, core_lint=lint, checks_complete=complete,
        passed=False if failed else True if complete else None,
        structural_scope=validation['structural_scope'], validation_scope=validation['validation_scope'],
        checked_artifact_ids=checked if scope_checked else [],
        dependency_artifact_ids=sorted(set(checked) - set(selected)) if scope_checked else [])
    return ComparisonResult(details)
