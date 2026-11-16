"""Read-only write-state and normal receipt observations, never recovery."""
from contextlib import nullcontext
from hashlib import sha256
import os
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..storage.json_syntax import parse_json_object as parsed
from ..model.canonical import canonical_json_bytes as jcs
from ._lock_files import LockFiles
from ._lock_process import LinuxOwnerProbe
from ._lock_owner_policy import observe_owner
from .write_guard_values import (MARKER_PATH, marker_value, validate_transaction,
    receipt_group, completion, require, WriteGuardError)
from ._guarded_io import _read_path
from .receipt_values import transaction_receipt_path, request_receipt_path
from ._journal_io import _read
from ..security import paths as guards


def inspect_write_state(root, *, expected_project_id=None, _held_files=None):
    """Bounded marker/owner diagnosis; a PID alone never proves a live writer."""
    state='unknown';marker=None;owner=None;guard_present=False
    try:
        if _held_files is not None:
            from ..security import ProjectBoundary
            boundary = ProjectBoundary(root)
            require(type(_held_files) is LockFiles, 'native_read_mutex_required')
            _held_files.require_held()
            require(_held_files.boundary.root == boundary.root
                and _held_files.boundary._root_identity == boundary._root_identity,
                'read_mutex_root_changed', exit_code=6)
        with (LockFiles(root) if _held_files is None else nullcontext(_held_files)) as files:
            with files.directory(('.specroad','write-state')) as fd:
                names=[] if fd is None else sorted(os.listdir(fd))
                guard_present=bool(names)
                raw=None if 'pending.json' not in names else files._read(fd,'pending.json')[0]
                if raw is not None:
                    marker=marker_value(parsed(raw))
                    require(jcs(marker)==raw,'noncanonical_write_marker')
                    if expected_project_id is not None:require(marker['project_id']==expected_project_id,'write_marker_project_mismatch')
            record,ident=files.read_record();active=files.journal_entries()
            # Unclassified operational entries block but do not prove an
            # interrupted transaction. Only actual journal/marker namespaces do.
            guard_present |= any(p.startswith(('.specroad/transactions/',
                                                  '.specroad/recovery/')) for p in active)
            mutex_busy=False
            from .lock_values import ProjectLockError
            try:
                if _held_files is None:files.acquire()
                else:files.require_held()
            except ProjectLockError as error:
                if error.reason!='project_lock_busy':raise
                mutex_busy=True
            if record is not None:
                owner=observe_owner(record,LinuxOwnerProbe())
                if expected_project_id is not None:require(record.data['project_id']==expected_project_id,'write_owner_project_mismatch')
                if marker is not None:
                    require(marker['owner']=={k:record.data[k] for k in ('lock_id','host_id','process_id','process_start_id')}
                        and marker['transaction_id']==record.data['transaction_id']
                        and marker['request_id']==record.data['request_id']
                        and marker['project_id']==record.data['project_id'],'write_marker_owner_mismatch')
                if owner=='alive' and mutex_busy:state='writer_active'
                elif owner in ('foreign','unverifiable'):state='unknown'
                else:state='corrupted'
            elif mutex_busy:state='unknown'
            elif guard_present:state='corrupted'
            elif active:state='unknown'
            else:state='clean'
            latest,latest_id=files.read_record()
            require((None if latest is None else latest.source_bytes)==(None if record is None else record.source_bytes)
                and latest_id==ident and files.journal_entries()==active,'write_state_changed')
            with files.directory(('.specroad','write-state')) as fd:
                require(([] if fd is None else sorted(os.listdir(fd)))==names,'write_state_changed')
            if raw is not None:require(_read_path(files,MARKER_PATH)==raw,'write_marker_changed')
    except (ModelError,SafetyViolation,OSError,ValueError,TypeError):
        state='corrupted' if guard_present else 'unknown'
    return dict(format_version='write-state-v1',state=state,owner_state=owner,
        project_corrupted=state=='corrupted',manual_git_restore_required=state=='corrupted',
        normal_operation_started=False,write_authorized=False,observation_only=True,
        exit_code=0 if state=='clean' else 5)


def read_guarded_completion(root, transaction_id, *, expected_project_id):
    """Return an intact historical result only while no active state is observed."""
    require(inspect_write_state(root,expected_project_id=expected_project_id)['state']=='clean','write_state_blocked')
    with LockFiles(root) as files:
        raw=_read_path(files,transaction_receipt_path(transaction_id))
        write=validate_transaction(raw);marker=write['marker']
        require(marker['project_id']==expected_project_id and marker['transaction_id']==transaction_id,
                'write_completion_binding',exit_code=6)
        group=receipt_group(write)
        prefix=transaction_receipt_path(transaction_id).rsplit('/',1)[0]
        with files.directory(tuple(prefix.split('/'))) as fd:
            require(fd is not None and set(os.listdir(fd))=={'transaction.json','committed.json'},'write_completion_namespace_changed')
        identities={}
        for path,expected in group.items():
            with files.directory(tuple(path.split('/')[:-1])) as fd:
                require(fd is not None,'write_completion_missing')
                name=path.rsplit('/',1)[-1]
                identity=guards._identity(os.stat(name,dir_fd=fd,follow_symlinks=False))
                actual=_read(fd,name,expected_identity=identity)
                require(actual==expected,'write_completion_changed',exit_code=6);identities[path]=identity
        for path,expected in group.items():
            with files.directory(tuple(path.split('/')[:-1])) as fd:
                name=path.rsplit('/',1)[-1]
                identity=guards._identity(os.stat(name,dir_fd=fd,follow_symlinks=False))
                actual=_read(fd,name,expected_identity=identity)
                require(actual==expected and identity==identities[path],'write_completion_changed',exit_code=6)
        require(inspect_write_state(root,expected_project_id=expected_project_id)['state']=='clean','write_state_blocked')
        files.check_root()
        return completion(write,current=False)


def resolve_guarded_request(root,request,*,expected_project_id):
    """A verified same-intent retry, or None; no execution or marker cleanup."""
    from .authoring_values import AuthoringRequest
    from ._request_identity import request_identity
    require(type(request) is AuthoringRequest,'native_write_request_required',exit_code=2)
    identity=request_identity(request)
    require(inspect_write_state(root,expected_project_id=expected_project_id)['state']=='clean','write_state_blocked')
    if not identity.applicable:return None
    with LockFiles(root) as files:
        path=request_receipt_path(identity.request_id);raw=_read_path(files,path,optional=True)
        if raw is None:return None
        value=parsed(raw)
        require(value.get('format_version')=='request-receipt-v2' and set(value)=={
            'format_version','namespace','request_id','project_id','transaction_id','actor',
            'operations_sha256','base_model_root_sha256','target_model_root_sha256','result',
            'created_ids','result_object','transaction_receipt'},'unsupported_write_request_receipt')
        result=read_guarded_completion(root,value['transaction_id'],expected_project_id=expected_project_id)
        require(value['request_id']==identity.request_id and value['operations_sha256']==identity.operations_sha256,
                'write_request_conflict',exit_code=6)
        require(result.data['receipts']['request']=={'path':path,'sha256':sha256(raw).hexdigest()}
            and _read_path(files,path)==raw,'write_request_changed',exit_code=6)
        return result
