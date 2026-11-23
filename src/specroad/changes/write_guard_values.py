"""Closed write-guard and normal receipt data; no replayable write journal."""
from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID
import unicodedata
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..storage.json_syntax import parse_json_object as parsed
from ..model.audit_fields import _valid_utc
from ..model.paths import project_path
from .execution_values import ChangeExecutionError
from .lock_values import OwnerIdentity, text
from ._journal_codec import _hash, _transaction
from .receipt_values import (transaction_receipt_path, request_receipt_path,
                            completion_marker_path, _created_ids)
from .request_ids import normalize_request_id
from .authoring import normalize_authoring_actor

MARKER_PATH = '.specroad/write-state/pending.json'
MARKER_FIELDS = {'format_version','project_id','transaction_id','request_id','command_id',
                 'plan_sha256','base_model_root_sha256','target_model_root_sha256','owner','state'}


class WriteGuardError(ChangeExecutionError):
    def __init__(self, reason, *, exit_code=5):
        super().__init__(reason, exit_code=exit_code, write_state='unknown')


def require(condition, reason, *, exit_code=5):
    if not condition:
        raise WriteGuardError(reason, exit_code=exit_code)


def marker_value(value):
    require(type(value) is dict and set(value) == MARKER_FIELDS
        and value['format_version'] == 'write-guard-v1' and value['state'] == 'writing',
        'invalid_write_marker')
    for key in ('project_id','command_id'): text(value[key])
    _transaction(value['transaction_id']); normalize_request_id(value['request_id'])
    require(all(_hash(value[k]) for k in ('plan_sha256','base_model_root_sha256','target_model_root_sha256')),
            'invalid_write_marker_hash')
    owner = value['owner']
    require(type(owner) is dict and set(owner)=={'lock_id','host_id','process_id','process_start_id'},
            'invalid_write_marker_owner')
    try:
        uid=UUID(owner['lock_id'])
        require(uid.version==4 and str(uid)==owner['lock_id'], 'invalid_write_marker_owner')
        OwnerIdentity(owner['host_id'], owner['process_id'], owner['process_start_id'])
    except (ValueError,TypeError,AttributeError) as error:
        raise WriteGuardError('invalid_write_marker_owner') from error
    return value


def metadata(raw):
    return None if raw is None else {'size':len(raw),'sha256':sha256(raw).hexdigest()}


def inventory(files):
    return [dict(path=p, **metadata(raw)) for p,raw in sorted(files.items())]


def _binding(value):
    require(type(value) is dict and set(value)=={'size','sha256'}
        and type(value['size']) is int and value['size']>=0 and _hash(value['sha256']),
        'invalid_write_file_binding')


def _path(path):
    project_path(path)
    require(not path.startswith('.') and '/.' not in path and path!='specroad.json/'
        and (path=='specroad.json' or path.split('/')[0] in
             ('spec','profiles','rules','mappings','attachments','archive')),
        'invalid_write_resource_path', exit_code=7)


def _result(write):
    marker=write['marker']
    return dict(exit_code=0,status='success',write_state='committed',
        transaction_id=marker['transaction_id'],request_id=marker['request_id'],
        target_model_root_sha256=marker['target_model_root_sha256'],
        published_paths=[r['path'] for r in write['files']],created_ids=_created_ids(write['operations']))


def transaction_document(write):
    return dict(format_version='transaction-receipt-v2',outcome='committed',
                write=write,write_sha256=digest(write),result_object=_result(write))


def receipt_group(write):
    transaction=transaction_document(write); marker=write['marker']
    path=transaction_receipt_path(marker['transaction_id']); raw=jcs(transaction)
    refs={'transaction':{'path':path,'sha256':sha256(raw).hexdigest()},'request':None}
    files={path:raw}
    if marker['request_id'] is not None:
        path=request_receipt_path(marker['request_id'])
        request=dict(format_version='request-receipt-v2',namespace='normative_write',
            request_id=marker['request_id'],project_id=marker['project_id'],transaction_id=marker['transaction_id'],
            actor=write['actor'],operations_sha256=write['operations_sha256'],
            base_model_root_sha256=marker['base_model_root_sha256'],target_model_root_sha256=marker['target_model_root_sha256'],
            result='committed',created_ids=transaction['result_object']['created_ids'],
            result_object=transaction['result_object'],transaction_receipt=refs['transaction'])
        raw=jcs(request);files[path]=raw;refs['request']={'path':path,'sha256':sha256(raw).hexdigest()}
    completion=dict(format_version='write-completion-v1',project_id=marker['project_id'],
        transaction_id=marker['transaction_id'],write_sha256=transaction['write_sha256'],
        target_model_root_sha256=marker['target_model_root_sha256'],receipts=refs)
    files[completion_marker_path(marker['transaction_id'])]=jcs(completion)
    return files


def _validate_native_report(native, targets):
    """Check the recorded pipeline report, not its separate CLI assessment."""
    from ..validation.values import HOOK_NAMES, _diagnostics
    fields={'format_version','input_sha256','validation_scope','source_count','structural_scope',
        'source_bindings','identified_ids','identified_sources','requested_ids','checked_ids','stages',
        'checks_complete','model_valid','approval_granted','write_authorized','project_files_verified','atomic_snapshot'}
    optional={'currentness','legacy_manifest_sha256','legacy_original_ids','legacy_current_evidence',
              'document_role_scope','selected_configuration','plan_sources'}
    require(type(native) is dict and fields<=set(native)<=fields|optional,'invalid_write_validation_report')
    require(native['format_version']=='model-validation-v1' and _hash(native['input_sha256'])
        and native['model_valid'] is True and native['checks_complete'] is True
        and native['validation_scope']=='loaded_model' and native['requested_ids'] is None
        and all(native[k] is False for k in ('approval_granted','write_authorized',
                                           'project_files_verified','atomic_snapshot')),
        'write_validation_incomplete')
    expected=[{'path':p,'sha256':row['sha256']} for p,row in targets.items()
              if p.startswith('spec/') and (p.endswith('.json') or p.endswith('.md'))]
    plan_sources = native.get('plan_sources', [])
    require(type(plan_sources) is list and all(type(s) is dict and set(s) == {'path', 'sha256', 'projections'}
        and type(s['path']) is str and type(s['projections']) is list and bool(s['projections']) for s in plan_sources),
        'write_validation_plan_binding')
    require([{'path': s['path'], 'sha256': s['sha256']} for s in plan_sources] == [s for s in expected if s['path'].endswith('.md')],
        'write_validation_plan_binding')
    for source in plan_sources:
        require(all(type(p) is dict and set(p) == {'id', 'sha256'} and type(p['id']) is str and _hash(p['sha256'])
            for p in source['projections']), 'write_validation_plan_binding')
    require(native['structural_scope']=='all_supplied_documents'
        and native['source_bindings']==expected and type(native['source_count']) is int
        and native['source_count']==len(expected),'write_validation_binding')
    ids=native['identified_ids']
    require(type(ids) is list and all(type(i) is str and i for i in ids)
        and ids==sorted(set(ids)) and native['checked_ids']==ids,'invalid_write_validation_ids')
    sources=native['identified_sources']
    require(type(sources) is list and all(type(s) is dict and set(s)=={'path','artifact_id'}
        and type(s['artifact_id']) is str for s in sources)
        and sorted(set(s['path'] for s in sources))==[s['path'] for s in expected]
        and all([s['artifact_id'] for s in sources if s['path']==p['path']] == sorted(r['id'] for r in p['projections'])
                for p in plan_sources)
        and all(sum(s['path']==p['path'] for s in sources)==1 for p in expected if p['path'].endswith('.json'))
        and sorted(s['artifact_id'] for s in sources)==ids,'write_validation_binding')
    stages=native['stages'];names=[]
    require(type(stages) is list and bool(stages),'write_validation_incomplete')
    for stage in stages:
        require(type(stage) is dict and set(stage)=={'stage','status','checked_ids','diagnostics'}
            and type(stage['stage']) is str and bool(stage['stage'])
            and stage['status'] in ('passed','not_applicable')
            and type(stage['checked_ids']) is list and all(type(i) is str for i in stage['checked_ids'])
            and len(set(stage['checked_ids']))==len(stage['checked_ids'])
            and set(stage['checked_ids'])<=set(ids) and type(stage['diagnostics']) is list,
            'write_validation_incomplete')
        _diagnostics(stage['diagnostics'])
        require(all(d.get('severity','error')!='error' for d in stage['diagnostics']),
                'write_validation_incomplete')
        names.append(stage['stage'])
    mandatory={'parsing','schema_types_identity_fields','identities_references','graph','scope',
               'profiles','minimum_relations','stored_lifecycle_fields',*HOOK_NAMES}
    require(len(set(names))==len(names) and mandatory<=set(names),'write_validation_incomplete')


def validate_transaction(raw):
    value=parsed(raw)
    require(set(value)=={'format_version','outcome','write','write_sha256','result_object'}
        and value['format_version']=='transaction-receipt-v2' and value['outcome']=='committed',
        'invalid_write_receipt')
    write=value['write']
    require(type(write) is dict and set(write)=={'marker','actor','planned_at','change_plan_id',
        'operations','operations_sha256','files','target_inventory','validation'}, 'invalid_write_record')
    marker_value(write['marker']);normalize_authoring_actor(write['actor']);text(write['change_plan_id'])
    require(_valid_utc(write['planned_at']), 'invalid_write_audit_time')
    from .values import ChangeOperation
    require(type(write['operations']) is list, 'invalid_write_operations')
    operations=[ChangeOperation(op).data for op in write['operations']]
    require(write['operations_sha256']==digest(operations), 'write_operations_binding')
    validation=write['validation']
    snapshot=type(validation) is dict and validation.get('format_version')=='snapshot-write-validation-v1'
    if snapshot:
        from .snapshot_write_values import checked_plan, effect_path, check_write
        from ..migration.plan_values import source_path
        snapshot_plan=checked_plan(validation)
    targets={}
    require(type(write['target_inventory']) is list and type(write['files']) is list, 'invalid_write_inventory')
    for row in write['target_inventory']:
        require(type(row) is dict and set(row)=={'path','size','sha256'},'invalid_write_inventory')
        (source_path if snapshot else _path)(row['path']);_binding({k:row[k] for k in ('size','sha256')})
        require(row['path'] not in targets,'duplicate_write_resource');targets[row['path']]={k:row[k] for k in ('size','sha256')}
    require(len({unicodedata.normalize('NFC',p).casefold() for p in targets})==len(targets),'write_inventory_alias')
    paths=[]
    for row in write['files']:
        require(type(row) is dict and set(row)=={'path','before','after'},'invalid_write_effect')
        if snapshot:effect_path(snapshot_plan,row['path'])
        else:_path(row['path'])
        paths.append(row['path'])
        for field in ('before','after'):
            if row[field] is not None:_binding(row[field])
        require(row['before']!=row['after'] and targets.get(row['path'])==row['after'],'write_effect_binding')
    require(paths==sorted(set(paths)) and list(targets)==sorted(targets)
        and len({unicodedata.normalize('NFC',p).casefold() for p in paths})==len(paths),'write_inventory_order')
    native=validation.get('native',validation) if type(validation) is dict else {}
    _validate_native_report(native,targets)
    if snapshot:check_write(write)
    require(raw==jcs(transaction_document(write)),'write_receipt_binding')
    return write


@dataclass(frozen=True)
class WriteCompletion:
    """Verified normal result data, never permission to remove a marker."""
    _raw: bytes
    @property
    def data(self):return parsed(self._raw)
    def __bool__(self):raise TypeError('Inspect the verified completion fields')


def completion(write, *, current):
    marker=write['marker'];group=receipt_group(write)
    proof=parsed(group[completion_marker_path(marker['transaction_id'])])
    return WriteCompletion(jcs(dict(format_version='transaction-completion-v2',state='committed',
        transaction_id=marker['transaction_id'],request_id=marker['request_id'],project_id=marker['project_id'],
        receipts=proof['receipts'],target_model_root_sha256=marker['target_model_root_sha256'],
        result_object=_result(write),commit_completed=True,receipt_verified=True,
        current_target_verified=current,cleanup_completed=True,cleanup_required=False,
        replayed=not current,write_authorized=False,atomic_snapshot=False)))
