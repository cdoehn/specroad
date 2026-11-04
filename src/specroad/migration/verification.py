"""Complete native migration verification of owned bytes, never authorization."""
from dataclasses import dataclass
from hashlib import sha256

from ..bundles.migration_source import verify_source_backup
from ..changes.values import ChangePlan
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..storage.json_syntax import parse_json_object as parsed
from .plan_values import require, owned_files, file_bindings
from .plan_recheck import recheck_migration_plan, _expected_hash
from .planning import plan_migration
from .transaction_target import validate_transaction_target
from .history import verify_source_history, verify_migrated_history


@dataclass(frozen=True, init=False)
class MigrationVerification:
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use the native migration verifier')

    @property
    def data(self):
        return parsed(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Migration verification is not write or release authority')


def _result(value):
    result = object.__new__(MigrationVerification)
    object.__setattr__(result, '_encoded', jcs(value))
    return result


def verify_migration(backup_raw, plan_raw, report_raw, target_files, *,
        expected_backup_sha256, expected_source_files_sha256, expected_plan_sha256,
        expected_inputs_sha256, expected_report_sha256, expected_target_version, gates=()):
    """Recompute the report and all invariants from exact complete source/target bytes.

    This pure entrypoint verifies the provided snapshot. Only the separate live
    adapter observes a project root. Neither a receipt nor supplied flags can
    replace full source, plan, history and current native model validation.
    """
    require(type(report_raw) is bytes, 'migration_report_bytes_required')
    _expected_hash(expected_report_sha256)
    require(sha256(report_raw).hexdigest() == expected_report_sha256,
            'migration_report_hash_mismatch', exit_code=6)
    backup = verify_source_backup(backup_raw, expected_sha256=expected_backup_sha256,
                                 expected_source_files_sha256=expected_source_files_sha256)
    source = backup.files
    checked = recheck_migration_plan(plan_raw, source,
        expected_target_version=expected_target_version, expected_plan_sha256=expected_plan_sha256,
        expected_inputs_sha256=expected_inputs_sha256)
    plan = ChangePlan(plan_raw); value = plan.data; op = value['operations'][0]
    rebuilt = plan_migration(source, inputs=op['inputs'], actor=value['actor'],
        planned_at=value['planned_at'], change_plan_id=value['change_plan_id'],
        request_id=value['request_id'], target_version=expected_target_version)
    require(jcs(parsed(report_raw)) == rebuilt.canonical_bytes,
            'migration_report_recomputation_mismatch', exit_code=6)
    target = owned_files(target_files, passive=True)
    validation = validate_transaction_target(plan, source, target, gates=gates)
    before = verify_source_history(source).data
    after = verify_migrated_history(target, project_id=backup.manifest['project_id']).data
    require(before['historical'] == after['historical'], 'migration_history_changed', exit_code=6)
    require(all(target.get(path) == source[path] for path in op['protected_paths']),
            'migration_original_changed', exit_code=6)
    require(rebuilt.data['loss_report']['lossless'], 'migration_lossless_contract_violation')
    # Native plan recomputation proves the complete target manifest/root. Exact
    # equality of every actual target byte makes that root a target observation,
    # not a trusted self-reported value or a hash of navigation projections.
    return _result({'format_version': 'migration-verification-v1', 'verified': True,
        'observation': 'provided_target_bytes', 'atomic_snapshot': False,
        'binding': {'backup_sha256': backup.sha256,
            'source_files_sha256': checked.source_files_sha256,
            'plan_sha256': checked.plan_sha256, 'inputs_sha256': checked.inputs_sha256,
            'report_sha256': expected_report_sha256, 'target_version': expected_target_version,
            'target_model_root_sha256': checked.target_model_root_sha256},
        'source_files': file_bindings(source), 'target_files': file_bindings(target),
        'target_files_sha256': digest(file_bindings(target)),
        'protected_paths': op['protected_paths'], 'loss_report': rebuilt.data['loss_report'],
        'historical': after, 'validation': validation.data,
        'operational_evidence': None, 'current_context_verified': False,
        'external_run_verified': False, 'current_readiness_verified': False,
        'write_authorized': False, 'approval_granted': False, 'release_authorized': False})


def verify_migration_project(root, backup_raw, plan_raw, report_raw, *, transaction_id, **options):
    """Read a stable complete live target with its exact native completion proof.

    No project lock/file is created. Existing writer/recovery state, unsafe
    paths, unregistered extra files or changes across the observation refuse
    success. The report deliberately does not claim an atomic live snapshot.
    """
    from ..changes._lock_files import LockFiles
    from ..changes._schema_transition_io import project_files
    from ..changes.schema_transition import _exclude
    from ..changes.schema_transition_recovery import completion_proof, takeover_evidence
    from ._backup_source import _observe
    all_files, observed, check_current = _observe(root)
    with LockFiles(root) as files:
        require(files.boundary._root_identity == observed.boundary._root_identity,
                'migration_verification_root_changed', exit_code=6)
        journal = completion_proof(files, transaction_id)
        require(journal.plan.source_bytes == plan_raw, 'migration_verification_plan_changed', exit_code=6)
        descriptor = journal.data['backup']
        require(descriptor['sha256'] == options['expected_backup_sha256']
                and descriptor['source_files_sha256'] == options['expected_source_files_sha256'],
                'migration_verification_backup_changed', exit_code=6)
        extra = takeover_evidence(files, journal)
        excluded = (*_exclude(journal, journal.receipt_root), *extra)
        target, _, _ = project_files(files, exclude=excluded)
        result = verify_migration(backup_raw, plan_raw, report_raw, target, **options)
        require(completion_proof(files, transaction_id).source_bytes == journal.source_bytes,
                'migration_verification_receipt_changed', exit_code=6)
        check_current()
    value = result.data
    value['observation'] = 'stable_live_target'
    value['operational_evidence'] = {'transaction_id': transaction_id,
        'journal_sha256': journal.sha256,
        'files': file_bindings({p: raw for p, raw in all_files.items() if p not in target})}
    return _result(value)
