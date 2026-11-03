"""Saved-plan recomputation before any later lock/backup/write authorization."""
from dataclasses import dataclass
import re
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..model.errors import ModelError
from ..changes.values import ChangePlan
from .plan_values import (POLICY, MigrationPlanError, require, owned_files, file_bindings)
from .planning import plan_migration, target_contract


@dataclass(frozen=True)
class RecheckedMigration:
    plan_sha256: str
    inputs_sha256: str
    source_files_sha256: str
    target_model_root_sha256: str

    @property
    def write_authorized(self):
        return False

    @property
    def validation_scope(self):
        return 'owned_source_and_native_plan_recomputation'

    @property
    def live_snapshot_atomic(self):
        return False

    def __bool__(self):
        raise TypeError('A plan recheck is not write authorization')


def _expected_hash(value):
    require(type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value) is not None,
            'migration_expected_hash_required')
    return value


def recheck_migration_plan(raw, files, *, expected_target_version,
                           expected_inputs_sha256, expected_plan_sha256):
    """Rebuild from real supplied bytes and explicit request bindings, never write.

    No old readiness flags, cached projections, self-hashes or valid-looking
    source labels replace native qualification. The caller must still obtain
    an atomic locked observation and all later migration publication gates.
    """
    try:
        require(type(raw) is bytes, 'migration_plan_bytes_required')
        expected_inputs_sha256 = _expected_hash(expected_inputs_sha256)
        expected_plan_sha256 = _expected_hash(expected_plan_sha256)
        plan = ChangePlan(raw); value = plan.data
        require(value['metadata_policy_version'] == POLICY, 'migration_plan_required')
        op = value['operations'][0]
        require(plan.sha256 == expected_plan_sha256, 'migration_plan_request_changed', exit_code=6)
        require(type(expected_target_version) is str and expected_target_version == '0.2.0'
                and op['target_contract']['schema_version'] == expected_target_version,
                'migration_target_version_mismatch', exit_code=6)
        require(op['inputs_sha256'] == expected_inputs_sha256, 'migration_mapping_request_changed', exit_code=6)
        require(op['target_contract'] == target_contract(), 'migration_target_contract_changed', exit_code=6)
        sources = owned_files(files); binding = file_bindings(sources)
        require(binding == op['source_files'], 'migration_source_files_changed', exit_code=6)
        rebuilt = plan_migration(sources, inputs=op['inputs'], actor=value['actor'],
            planned_at=value['planned_at'], change_plan_id=value['change_plan_id'],
            request_id=value['request_id'], target_version=expected_target_version)
        require(rebuilt.ready, 'migration_saved_plan_incomplete')
        require(rebuilt.change_plan.canonical_bytes == plan.canonical_bytes,
                'migration_native_plan_mismatch', exit_code=6)
        return RecheckedMigration(plan.sha256, op['inputs_sha256'], digest(binding),
                                  op['target_model_root_sha256'])
    except MigrationPlanError:
        raise
    except ModelError as error:
        raise MigrationPlanError(error.reason, path=error.path, pointer=error.pointer,
                                 exit_code=getattr(error, 'exit_code', 3)) from error
