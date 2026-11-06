"""Exact external before-image archive on the common ZIP/publication codec."""
from dataclasses import dataclass
from hashlib import sha256
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..storage.json_syntax import parse_json_object as parsed
from ..storage.archive import encode_archive, decode_zip, validate_portable_archive_paths, _inventory
from ..migration.plan_values import file_bindings
from ..bundles.migration_source import ADMIN_ROOTS, PASSIVE
from .publication_contract import require

MANIFEST='merge-source-manifest.json'


@dataclass(frozen=True)
class MergeBackup:
    source_bytes: bytes
    _files: tuple
    _manifest: bytes
    @property
    def files(self): return dict(self._files)
    @property
    def manifest(self): return parsed(self._manifest)
    @property
    def sha256(self): return sha256(self.source_bytes).hexdigest()


def source_files(files):
    require(type(files) is dict and all(type(p) is str and type(b) is bytes for p,b in files.items()),'merge_backup_bytes_required')
    validate_portable_archive_paths(list(files))
    for name in files:
        parts=name.split('/')
        require(not any(p.casefold() in ADMIN_ROOTS for p in parts),'merge_backup_protected_path')
        require('.specroad' not in [p.casefold() for p in parts[1:]],'merge_backup_protected_path')
        if parts[0].casefold()=='.specroad':
            require(any(name.startswith(p+'/') for p in PASSIVE),'merge_backup_active_state')
        require(name=='specroad.json' or parts[-1].casefold()!='specroad.json','merge_backup_nested_project')
    return dict(files)


def prepare_merge_backup(files):
    files=source_files(files)
    value={'backup_format_version':'merge-source-backup-v1','project_id':parsed(files['specroad.json'])['project_id'],
        'source_files_sha256':digest(file_bindings(files)), 'read_only':True}
    raw=encode_archive(MANIFEST,value,{'source/'+p:b for p,b in files.items()})
    return verify_merge_backup(raw,expected_sha256=sha256(raw).hexdigest(),expected_source_files_sha256=value['source_files_sha256'])


def verify_merge_backup(raw, *, expected_sha256, expected_source_files_sha256):
    require(type(raw) is bytes and sha256(raw).hexdigest()==expected_sha256,'merge_backup_hash')
    payload=decode_zip(raw,max_uncompressed_bytes=max(1,len(raw)),validate_paths=validate_portable_archive_paths)
    require(MANIFEST in payload,'merge_backup_manifest_missing')
    manifest=payload.pop(MANIFEST);value=parsed(manifest)
    require(manifest==jcs(value) and set(value)=={'backup_format_version','project_id','source_files_sha256','read_only','entries'}
        and value['backup_format_version']=='merge-source-backup-v1' and value['read_only'] is True
        and value['entries']==_inventory(payload) and all(p.startswith('source/') for p in payload),'merge_backup_manifest')
    files=source_files({p[7:]:b for p,b in payload.items()})
    require(value['source_files_sha256']==expected_source_files_sha256==digest(file_bindings(files))
        and value['project_id']==parsed(files['specroad.json'])['project_id'],'merge_backup_source_binding')
    return MergeBackup(raw,tuple(sorted(files.items())),manifest)


def create_merge_backup(root, raw, *, expected_plan_sha256, output, output_root):
    """Explicit immutable output outside the project; not a writer authorization."""
    from ..changes.values import ChangePlan
    from ..migration._backup_source import _observe
    from ..bundles.publication import _publish
    from ..documents._export_targets import _output_boundary
    from .publication_target import recheck_plan
    plan=ChangePlan(raw)
    require(plan.data['metadata_policy_version']=='merge-metadata-v1' and plan.sha256==expected_plan_sha256,'merge_backup_plan_binding')
    files,source,current=_observe(root)
    recheck_plan(plan,files)
    backup=prepare_merge_backup(files)
    require(output_root is not None,'merge_backup_external_output_required')
    boundary=_output_boundary(output_root,source)
    result=_publish(backup,source,current,output,output_root)
    published=boundary.read_bytes(result['file']['path'])
    require(published==backup.source_bytes,'merge_backup_published_changed');current()
    return {'file':{'path':str(boundary.root/result['file']['path']),'size':len(published),'sha256':backup.sha256},
        'output_root':str(boundary.root),'source_files_sha256':digest(file_bindings(files)),
        'backup_verified':True,'write_authorized':False,'approval_granted':False}
