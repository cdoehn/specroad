"""Migration/merge qualification around the common guarded publication session."""
from ._snapshot_dispatch import materialized_files, validate_target, command_for, is_merge
from .schema_transition_values import require, authoring, TransitionRequest
from ._schema_transition_io import external_backup, project_files
from .locking import HeldProjectLock
from .publication_values import PublicationAuthority
from .receipt_values import transaction_receipt_path, request_receipt_path
from ._guarded_publication import _Inputs, _run
from ._guarded_io import _read_path
from .snapshot_write_values import validation, effect_path, result


def publish_snapshot(plan, *, held_lock, backup_descriptor, authority, gates=(),
                     merge_context=None, checkpoint):
    require(type(held_lock) is HeldProjectLock and type(authority) is PublicationAuthority,
            'transition_native_inputs_required', exit_code=7)
    held_lock.check();authoring(plan)
    owner=held_lock.record.data;files=held_lock._files
    require(owner['kind']=='writer' and owner['command']==command_for(plan),
            'transition_writer_lock_required',exit_code=7)
    backup=external_backup(files,backup_descriptor,plan=plan)
    source,modes,_=project_files(files,exclude=('.specroad/locks/project.json',))
    require(source==backup.files,'transition_source_changed')
    target=materialized_files(plan,source)
    tx=owner['transaction_id'];request_id=plan.data['request_id']
    receipt_root=transaction_receipt_path(tx).rsplit('/',1)[0]
    excluded=[receipt_root,'.specroad/write-state','.specroad/locks/project.json']
    if request_id is not None:excluded.append(request_receipt_path(request_id))
    initial=validate_target(plan,source,target,gates=tuple(gates),merge_context=merge_context).data
    def request():
        return TransitionRequest.from_snapshot(plan, backup_descriptor,
            list(files.boundary._root_identity),backup.manifest['project_id'],tx,initial)
    def check_inputs():
        held_lock.check()
        current=external_backup(files,backup_descriptor,plan=plan)
        require(current.source_bytes==backup.source_bytes,'transition_backup_changed')
        if merge_context is not None:merge_context.check()
    def authorize():
        before=request();raw=before._raw
        allowed=authority.check(before)
        require(type(allowed) is bool and allowed and raw==before._raw==request()._raw,
                'transition_not_authorized',exit_code=7)
        check_inputs()
    def inventory_check(expected):
        actual,current_modes,_=project_files(files,exclude=tuple(excluded))
        require(actual==expected,'transition_file_prefix_changed')
        require(all(mode==modes.get(p,0o644) for p,mode in current_modes.items()),'transition_file_mode_changed')
        check_inputs()
    def qualify(proposed):
        require(proposed==target,'transition_target_changed')
        check_inputs();authorize()
        report=validate_target(plan,source,target,gates=tuple(gates),merge_context=merge_context).data
        require(report==initial,'transition_validation_changed')
        check_inputs()
        return validation(plan,backup_descriptor,report)
    authorize()
    require(not files.journal_entries(),'transition_recovery_required',exit_code=5)
    require(project_files(files,exclude=('.specroad/locks/project.json',))[:2]==(source,modes),
            'transition_source_changed')
    inputs=_Inputs(plan,backup.manifest['project_id'],command_for(plan),source,target,
                   inventory_check,qualify,lambda p:effect_path(plan,p))
    _run(inputs,held_lock,checkpoint=checkpoint)
    # Preserve the final native external-input freshness boundary for merge.
    check_inputs()
    if is_merge(plan):
        require(validate_target(plan,source,target,merge_context=merge_context).data==initial,
                'transition_validation_changed')
    raw=_read_path(files,transaction_receipt_path(tx))
    from .write_guard_values import validate_transaction
    write=validate_transaction(raw)
    return result(write,current=True,evidence_current=is_merge(plan))
