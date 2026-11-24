"""Own the uninterrupted guard lifetime and normal durable completion.

File effects are delegated without changing any guard or synchronization order.
The fault boundary is a compiled adapter argument, never project-supplied code.
"""
from dataclasses import dataclass
from hashlib import sha256
from ..force import operations_hash
import os
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..security import paths as guards
from .locking import HeldProjectLock
from ._staging_files import _write_new, _image
from ._publication_observation import _stamp
from ._guarded_io import _read_path
from ._guarded_effects import publish_effect
from .write_guard_values import (WriteGuardError, require, marker_value, metadata,
    inventory, receipt_group, validate_transaction, completion)
from .receipt_values import transaction_receipt_path, completion_marker_path


@dataclass(frozen=True)
class _Inputs:
    plan: object
    project_id: str
    command_id: str
    before: dict
    target: dict
    inventory_check: object
    qualify: object
    effect_path: object = None
    force_record: object = None


class _Session:
    def __init__(self, inputs, held, checkpoint):
        self.checkpoint = checkpoint
        require(type(held) is HeldProjectLock,'native_write_lock_required',exit_code=7)
        held.check();self.held=held;self.files=held._files;self.inputs=inputs
        from . import write_guard_values
        self.codec = write_guard_values
        if inputs.force_record is not None:
            from . import force_receipts
            self.codec = force_receipts
        self.before=dict(inputs.before);self.target=dict(inputs.target);self.expected=dict(self.before)
        self.paths=sorted(p for p in self.before.keys()|self.target.keys() if self.before.get(p)!=self.target.get(p))
        from .write_guard_values import _path
        from ..storage.archive import validate_portable_archive_paths
        validate_portable_archive_paths(list(self.before.keys()|self.target.keys()))
        for p in self.paths:
            (_path if inputs.effect_path is None else inputs.effect_path)(p)
            require(not p.startswith('archive/objects/') or p not in self.before,'immutable_write_target',exit_code=7)
        require(bool(self.paths) or inputs.command_id == 'merge apply',
                'empty_write_program',exit_code=2)
        self.parents={};self.identities={};self.modes={};self.owners={};self.images={};self.records={}
        self.marker=None;self.marker_id=None;self.active=False;self.stage_created=False
        owner=held.record.data;plan=inputs.plan.data
        require(owner['kind']=='writer' and owner['project_id']==inputs.project_id
            and owner['request_id']==plan['request_id'] and owner['command'] in ('change apply',inputs.command_id),
            'write_lock_binding',exit_code=7)
        require(not self.files.journal_entries(),'write_state_blocked')
        self.marker_value=self.codec.marker_value(dict(format_version='write-guard-v1',project_id=inputs.project_id,
            transaction_id=owner['transaction_id'],request_id=plan['request_id'],command_id=inputs.command_id,
            plan_sha256=inputs.plan.sha256,base_model_root_sha256=plan['base']['model_root_sha256'],
            target_model_root_sha256=plan['expected_result']['model_root_sha256'],
            owner={k:owner[k] for k in ('lock_id','host_id','process_id','process_start_id')},state='writing'), force=inputs.force_record) if inputs.force_record is not None else marker_value(dict(
            format_version='write-guard-v1',project_id=inputs.project_id,transaction_id=owner['transaction_id'],
            request_id=plan['request_id'],command_id=inputs.command_id,plan_sha256=inputs.plan.sha256,
            base_model_root_sha256=plan['base']['model_root_sha256'],
            target_model_root_sha256=plan['expected_result']['model_root_sha256'],
            owner={k:owner[k] for k in ('lock_id','host_id','process_id','process_start_id')},state='writing'))
        self._parents(tuple(sorted(self.expected.keys()|set(self.paths))),capture=True)
        for p in self.expected:
            with self.files.directory(tuple(p.split('/')[:-1])) as fd:
                require(fd is not None,'write_source_missing')
                info=os.stat(p.rsplit('/',1)[-1],dir_fd=fd,follow_symlinks=False)
                guards._regular(info)
                require(info.st_dev==os.fstat(self.files.root_fd).st_dev and info.st_nlink==1
                    and not info.st_mode&0o7000,'unsafe_write_source',exit_code=7)
                self.identities[p]=guards._identity(info);self.modes[p]=info.st_mode&0o777
                self.owners[p]=(info.st_uid,info.st_gid)
        self.guard()

    def _parents(self,paths,*,capture=False):
        for path in paths:
            parts=tuple(path.split('/')[:-1])
            for i in range(len(parts)+1):
                key=parts[:i]
                with self.files.directory(key) as fd:
                    state=None if fd is None else _stamp(os.fstat(fd))
                    if fd is not None:require(os.fstat(fd).st_dev==os.fstat(self.files.root_fd).st_dev,'write_cross_device',exit_code=7)
                    if key in self.parents:require(self.parents[key]==state,'write_parent_changed',exit_code=6)
                    elif capture:self.parents[key]=state

    def guard(self):
        self.held.check()
        self._parents(tuple('/'.join((*key, '__guard__')) for key in self.parents))
        expected_active=('.specroad/write-state',) if self.active else ()
        require(self.files.journal_entries()==expected_active,'write_active_set_changed')
        self.inputs.inventory_check(self.expected)
        for p,raw in self.expected.items():
            with self.files.directory(tuple(p.split('/')[:-1])) as fd:
                require(fd is not None,'write_parent_changed',exit_code=6)
                _image(fd,p.rsplit('/',1)[-1],len(raw),sha256(raw).hexdigest(),identity=self.identities[p])
                info=os.stat(p.rsplit('/',1)[-1],dir_fd=fd,follow_symlinks=False)
                require(info.st_mode&0o777==self.modes[p] and not info.st_mode&0o7000
                    and (info.st_uid,info.st_gid)==self.owners[p],'write_mode_changed',exit_code=6)
        for p in self.paths:
            if p not in self.expected:require(_read_path(self.files,p,optional=True) is None,'write_absent_target_changed',exit_code=6)
        if self.marker is not None:
            with self.files.directory(('.specroad','write-state')) as fd:
                require(fd is not None,'write_marker_missing')
                require(set(os.listdir(fd))==({'pending.json','staging'} if self.stage_created else {'pending.json'}),'write_guard_namespace_changed')
                _image(fd,'pending.json',len(self.marker),sha256(self.marker).hexdigest(),identity=self.marker_id)
        if self.stage_created:
            with self.files.directory(('.specroad','write-state','staging')) as fd:
                require(fd is not None and set(os.listdir(fd))==set(self.images),'write_staging_changed')
                for name,(raw,ident) in self.images.items():_image(fd,name,len(raw),sha256(raw).hexdigest(),identity=ident)
        for path,(raw,ident) in self.records.items():
            with self.files.directory(tuple(path.split('/')[:-1])) as fd:
                require(fd is not None,'write_receipt_missing')
                _image(fd,path.rsplit('/',1)[-1],len(raw),sha256(raw).hexdigest(),identity=ident)
        receipt_parent=transaction_receipt_path(self.marker_value['transaction_id']).rsplit('/',1)[0]
        known={p.rsplit('/',1)[-1] for p in self.records if p.startswith(receipt_parent+'/')}
        with self.files.directory(tuple(receipt_parent.split('/'))) as fd:
            require((fd is None and not known) or (fd is not None and set(os.listdir(fd))==known),
                'write_receipt_namespace_changed')
        self.inputs.inventory_check(self.expected)
        self.held.check()

    def qualify(self):
        self.guard()
        report=self.inputs.qualify(dict(self.target))
        self.guard()
        return report

    def start(self):
        self.guard();self.qualify()
        self.checkpoint('before_marker')
        self.guard()
        # A failed unlink/fsync must not be hidden by context-manager cleanup.
        self.held._write_release_allowed=False
        with self.files.directory(('.specroad','write-state'),create=True) as fd:
            require(not os.listdir(fd),'write_state_not_empty')
            # Bind the marker parents/device before the first operational byte.
            self._parents(('.specroad/write-state/pending.json',),capture=True)
            self.marker=jcs(self.marker_value)
            self.marker_id=_write_new(fd,'pending.json',self.marker)
        self.active=True
        self._parents(('.specroad/write-state/pending.json',),capture=True)
        self.guard();self.checkpoint('marker_synced');self.guard()
        with self.files.directory(('.specroad','write-state')) as fd:
            os.mkdir('staging',mode=0o700,dir_fd=fd);os.fsync(fd)
        self.stage_created=True
        self._parents(('.specroad/write-state/staging/image',),capture=True)
        for index,path in enumerate(self.paths):
            if path not in self.target:continue
            self.guard();raw=self.target[path];name=str(index)+'.bin'
            with self.files.directory(('.specroad','write-state','staging')) as fd:
                ident=_write_new(fd,name,raw)
            self.images[name]=(raw,ident)
            self.guard();self.checkpoint('staged:'+str(index))
        self.qualify()

    def finish(self):
        require(self.expected==self.target,'write_target_incomplete')
        self.guard();validation=self.qualify();plan=self.inputs.plan.data
        write=dict(marker=self.marker_value,actor=plan['actor'],planned_at=plan['planned_at'],
            change_plan_id=plan['change_plan_id'],operations=plan['operations'],operations_sha256=operations_hash(plan),
            files=[dict(path=p,before=metadata(self.before.get(p)),after=metadata(self.target.get(p))) for p in self.paths],
            target_inventory=inventory(self.target),validation=validation)
        if self.inputs.force_record is not None:
            write['plan'] = plan
            write['force'] = self.inputs.force_record
        group=self.codec.receipt_group(write)
        self.codec.validate_transaction(group[transaction_receipt_path(self.marker_value['transaction_id'])])
        for path,raw in group.items():
            self.guard()
            with self.files.directory(tuple(path.split('/')[:-1]),create=True) as fd:
                self._parents((path,),capture=True)
                self.records[path]=(raw,_write_new(fd,path.rsplit('/',1)[-1],raw))
            self.guard();self.checkpoint('receipt:'+path.rsplit('/',1)[-1]);self.guard()
        self.guard();require(self.qualify()==validation,'write_validation_changed')
        self.checkpoint('receipts_synced');self.guard()
        with self.files.directory(('.specroad','write-state')) as fd:
            os.rmdir('staging',dir_fd=fd);self.stage_created=False
            self.parents.pop(('.specroad','write-state','staging'));os.fsync(fd)
            self.guard();self.checkpoint('before_marker_unlink');self.guard()
            os.unlink('pending.json',dir_fd=fd)
            self.checkpoint('marker_unlinked');os.fsync(fd)
            self.checkpoint('marker_removed')
            require(not os.listdir(fd),'write_guard_namespace_changed')
        self.marker=None;self.active=False
        self.guard();self.held._write_release_allowed=True
        return self.codec.completion(write,current=True)


def _run(inputs,held,*,checkpoint):
    session=_Session(inputs,held,checkpoint)
    # All future receipt paths must be absent before protection starts.
    transaction=held.record.data['transaction_id']
    paths=[transaction_receipt_path(transaction),completion_marker_path(transaction)]
    if inputs.plan.data['request_id'] is not None:
        from .receipt_values import request_receipt_path
        paths.append(request_receipt_path(inputs.plan.data['request_id']))
    for path in paths:require(_read_path(held._files,path,optional=True) is None,'write_receipt_collision',exit_code=6)
    with held._files.directory(tuple(paths[0].split('/')[:-1])) as fd:
        require(fd is None,'write_receipt_directory_collision',exit_code=6)
    session.start()
    for i,path in enumerate(session.paths):publish_effect(session,i,path)
    return session.finish()
