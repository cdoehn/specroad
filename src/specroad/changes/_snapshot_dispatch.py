"""Compiled adapters for the shared full-image writer; no data-loaded code."""
from ..migration.transaction_target import materialized_files
from .schema_transition_values import require


def is_merge(plan):
    return plan.data['metadata_policy_version']=='merge-metadata-v1'


def command_for(plan):
    return 'merge apply' if is_merge(plan) else 'migrate apply'


def format_for(plan):
    return 'merge-transition-journal-v1' if is_merge(plan) else 'schema-transition-journal-v1'


def verify_backup(plan,raw,descriptor):
    if is_merge(plan):
        from ..merge.publication_backup import verify_merge_backup as verify
    else:
        from ..bundles.migration_source import verify_source_backup as verify
    return verify(raw,expected_sha256=descriptor['sha256'],
                  expected_source_files_sha256=descriptor['source_files_sha256'])


def recheck_source(plan,source):
    if is_merge(plan):
        from ..merge.publication_target import recheck_plan
        recheck_plan(plan,source)
    else:
        from ..migration.plan_recheck import recheck_migration_plan
        recheck_migration_plan(plan.source_bytes,source,expected_target_version='0.2.0',
            expected_inputs_sha256=plan.data['operations'][0]['inputs_sha256'],expected_plan_sha256=plan.sha256)


def validate_target(plan,source,target,*,gates=(),merge_context=None):
    if is_merge(plan):
        from ..merge.publication import MergePublicationContext
        from ..merge.publication_target import validate_publication_target
        require(not gates and type(merge_context) is MergePublicationContext,'merge_native_context_required',exit_code=7)
        merge_context.check()
        try:
            return validate_publication_target(plan,source,target,services=merge_context.services)
        finally:
            merge_context.check()
    require(merge_context is None,'migration_unexpected_merge_context',exit_code=7)
    from ..migration.transaction_target import validate_transaction_target
    return validate_transaction_target(plan,source,target,gates=gates)
