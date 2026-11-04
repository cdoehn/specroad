"""Native migration adapter for the common schema-transition writer.

Public commands delegate to this adapter. Hosts supply real authority and any
required semantic services, never project code or persisted success flags.
"""
from ..changes.values import ChangePlan
from ..changes.locking import project_lock
from ..changes.publication_values import PublicationAuthority
from ..changes.schema_transition import publish_schema_transition
from ..changes.schema_transition_values import authoring, require
from ..changes._journal_codec import _transaction
from ..model.canonical import canonical_json_sha256 as digest
from ..storage.json_syntax import parse_json_object
from .plan_values import unb64


def apply_migration_plan(root, raw, *, expected_plan_sha256, expected_inputs_sha256,
        expected_target_version, transaction_id, backup_path, backup_root,
        backup_sha256, backup_size, backup_source_files_sha256, authority, gates=()):
    """Execute exact native plan bytes; failures preserve the real journal state.

    No saved readiness/backup report is admitted. No implicit rollback, retry,
    ID allocation, clock-derived target data or downgrade is available.
    """
    require(type(raw) is bytes and type(authority) is PublicationAuthority,
            'migration_explicit_execution_inputs_required', exit_code=2)
    require(type(gates) in (tuple, list), 'migration_registered_gates_required', exit_code=2)
    gates = tuple(gates)
    plan = ChangePlan(raw); authoring(plan)
    op = plan.data['operations'][0]
    require(expected_target_version == '0.2.0' and expected_plan_sha256 == plan.sha256
        and expected_inputs_sha256 == op['inputs_sha256']
        and backup_source_files_sha256 == digest(op['source_files']), 'migration_execution_binding_changed')
    _transaction(transaction_id)
    config = parse_json_object(unb64(op['inputs']['target_configuration']))
    descriptor = {'path': backup_path, 'output_root': backup_root, 'sha256': backup_sha256,
        'size': backup_size, 'source_files_sha256': backup_source_files_sha256}
    from ..changes._lock_files import LockFiles
    from ..changes.schema_transition_recovery import historical_request
    from ..storage.operational_preflight import observe_operational_preflight
    with LockFiles(root) as files:
        require(observe_operational_preflight(files.boundary)['consistency_state'] == 'consistent',
                'migration_recovery_required', exit_code=5)
        actual = parse_json_object(files.boundary.read_bytes('specroad.json'))
        require(actual.get('project_id') == config['project_id'], 'transition_project_binding')
        historical = historical_request(files, plan, config['project_id'])
        if historical is not None:
            return historical
        actual = parse_json_object(files.boundary.read_bytes('specroad.json'))
        if actual.get('schema_version') == expected_target_version:
            from ..storage.project import ProjectSource
            source = ProjectSource(root, expected_project_id=config['project_id'])
            source.check_current()
            require(observe_operational_preflight(source.boundary)['consistency_state'] == 'consistent',
                    'migration_recovery_required', exit_code=5)
            return {'format_version':'migration-transaction-v1','status':'not_required','exit_code':0,
                'write_state':'not_committed','no_change':True,'replayed':False,
                'current_target_verified':False,'approval_granted':False,'write_authorized':False}
    with project_lock(root, kind='writer' , command='migrate apply', project_id=config['project_id'],
            request_id=plan.data['request_id'], transaction_id=transaction_id) as held:
        historical = historical_request(held._files, plan, config['project_id'])
        if historical is not None: return historical
        try:
            return publish_schema_transition(plan, held_lock=held, backup_descriptor=descriptor,
                                             authority=authority, gates=gates)
        except Exception as error:
            from ..changes.schema_transition_values import SchemaTransitionError
            if isinstance(error, SchemaTransitionError): raise
            raise SchemaTransitionError(getattr(error,'reason','migration_publication_interrupted'),
                exit_code=getattr(error,'exit_code',6),write_state='unknown') from error
