"""Compile native snapshot inputs for the common Create/Replace/Delete engine.

This is the shared writer primitive, not migration/merge command dispatch.
Existing public adapters are switched separately in the planned 18.v group.
"""
from .guarded_write import _Inputs, _run
from .schema_transition_values import TransitionJournal, TransitionRequest, authoring
from ._snapshot_dispatch import (validate_target,materialized_files,command_for,format_for,recheck_source)
from ._schema_transition_io import external_backup,project_files
from ..model.canonical import canonical_json_bytes as jcs
from ..migration.plan_values import b64
from .publication_values import PublicationAuthority
from .write_guard_values import require


def publish_guarded_snapshot(plan, *, held_lock, backup_descriptor, authority, gates=(), merge_context=None):
    authoring(plan)
    require(type(authority) is PublicationAuthority,'write_authority_required',exit_code=7)
    held_lock.check();files=held_lock._files
    require(held_lock.record.data['command']==command_for(plan),'write_command_binding',exit_code=7)
    backup=external_backup(files,backup_descriptor,plan=plan)
    source,modes,_=project_files(files,exclude=('.specroad/locks/project.json',))
    require(source==backup.files,'write_snapshot_source_changed',exit_code=6)
    # Historical operational import is integrated by the later adapter change.
    require(not any(p.startswith('.specroad/') for p in source),'write_snapshot_operational_input_unsupported')
    recheck_source(plan,source)
    target=materialized_files(plan,source)
    report=validate_target(plan,source,target,gates=tuple(gates),merge_context=merge_context)
    value=dict(format_version=format_for(plan),state='building',transaction_id=held_lock.record.data['transaction_id'],
        project_id=backup.manifest['project_id'],root_identity=list(files.boundary._root_identity),
        plan_bytes_base64=b64(plan.source_bytes),request_id=plan.data['request_id'],plan_sha256=plan.sha256,
        backup=backup_descriptor,source_modes=modes,published_count=0,images_prepared=False,validation=report.data)
    journal=TransitionJournal(jcs(value))  # existing native validation, never persisted
    def inventory_check(expected):
        actual,_,_=project_files(files,exclude=('.specroad',))
        require(actual==expected,'write_snapshot_changed',exit_code=6)
    def qualify(actual):
        require(external_backup(files,backup_descriptor,plan=plan).source_bytes==backup.source_bytes,
                'write_snapshot_backup_changed',exit_code=6)
        current=validate_target(plan,source,actual,gates=tuple(gates),merge_context=merge_context)
        request=TransitionRequest.from_journal(journal);raw=request._raw
        allowed=authority.check(request)
        require(type(allowed) is bool and allowed and request._raw==raw,'write_authority_denied',exit_code=7)
        return current.data
    inputs=_Inputs(plan,backup.manifest['project_id'],command_for(plan),source,target,inventory_check,qualify)
    return _run(inputs,held_lock)
