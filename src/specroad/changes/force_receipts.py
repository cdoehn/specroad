"""Closed Force completion records for the existing guarded writer.

These records prove execution and preserve negative findings. They never
constitute an approval or replace an earlier transaction's evidence.
"""
from hashlib import sha256
from uuid import UUID
from ..force import ForceRequest, validate_summary, operations_hash
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..storage.json_syntax import parse_json_object as parsed
from .write_guard_values import require, inventory, metadata, _binding, WriteCompletion
from .lock_values import OwnerIdentity, text
from ._journal_codec import _transaction, _hash
from .receipt_values import transaction_receipt_path, request_receipt_path, completion_marker_path, _created_ids
from .request_ids import normalize_request_id


def marker_value(value, *, force=None):
    if force is not None:
        value = {**value, 'format_version': 'force-write-guard-v1', 'force': validate_summary(force)}
    fields = {'format_version', 'project_id', 'transaction_id', 'request_id', 'command_id',
        'plan_sha256', 'base_model_root_sha256', 'target_model_root_sha256', 'owner', 'state', 'force'}
    require(type(value) is dict and set(value) == fields and value['format_version'] == 'force-write-guard-v1'
        and value['state'] == 'writing', 'force_marker_fields')
    text(value['project_id']); text(value['command_id']); _transaction(value['transaction_id'])
    normalize_request_id(value['request_id'])
    require(_hash(value['plan_sha256']) and all(value[k] is None or _hash(value[k])
        for k in ('base_model_root_sha256', 'target_model_root_sha256')), 'force_marker_hash')
    summary = validate_summary(value['force']); require(summary['requested'], 'force_marker_request')
    owner = value['owner']
    require(type(owner) is dict and set(owner) == {'lock_id', 'host_id', 'process_id', 'process_start_id'}, 'force_marker_owner')
    uid = UUID(owner['lock_id']); require(uid.version == 4 and str(uid) == owner['lock_id'], 'force_marker_owner')
    OwnerIdentity(owner['host_id'], owner['process_id'], owner['process_start_id'])
    return value


def result_object(write):
    marker = write['marker']; validation = write['validation']; force = write['force']
    return dict(exit_code=0, status='forced' if force['used'] else 'success', write_state='committed',
        transaction_id=marker['transaction_id'], request_id=marker['request_id'],
        target_model_root_sha256=validation['model_root_sha256'],
        published_paths=[row['path'] for row in write['files']], created_ids=_created_ids(write['operations']),
        validation_status=validation['validation_status'], force=force, approval_granted=False)


def transaction_document(write):
    return dict(format_version='force-transaction-receipt-v1', outcome='committed', write=write,
        write_sha256=digest(write), result_object=result_object(write))


def receipt_group(write):
    marker = write['marker']; transaction = transaction_document(write)
    path = transaction_receipt_path(marker['transaction_id']); raw = jcs(transaction)
    refs = {'transaction': {'path': path, 'sha256': sha256(raw).hexdigest()}, 'request': None}
    group = {path: raw}
    if marker['request_id'] is not None:
        path = request_receipt_path(marker['request_id'])
        request = dict(format_version='force-request-receipt-v1', namespace='normative_write',
            request_id=marker['request_id'], project_id=marker['project_id'], transaction_id=marker['transaction_id'],
            actor=write['actor'], operations_sha256=write['operations_sha256'], plan_sha256=marker['plan_sha256'],
            force=write['force'], result='committed', result_object=transaction['result_object'],
            transaction_receipt=refs['transaction'])
        raw = jcs(request); group[path] = raw; refs['request'] = {'path': path, 'sha256': sha256(raw).hexdigest()}
    group[completion_marker_path(marker['transaction_id'])] = jcs(dict(format_version='force-write-completion-v1',
        project_id=marker['project_id'], transaction_id=marker['transaction_id'], write_sha256=digest(write),
        receipts=refs, force=write['force'], validation_status=write['validation']['validation_status']))
    return group


def validate_transaction(raw):
    from .values import ChangePlan
    from .force_target import effect_path, validate_report
    value = parsed(raw)
    require(set(value) == {'format_version', 'outcome', 'write', 'write_sha256', 'result_object'}
        and value['format_version'] == 'force-transaction-receipt-v1' and value['outcome'] == 'committed', 'force_receipt_fields')
    write = value['write']
    require(type(write) is dict and set(write) == {'marker', 'actor', 'planned_at', 'change_plan_id',
        'operations', 'operations_sha256', 'files', 'target_inventory', 'validation', 'plan', 'force'}, 'force_write_fields')
    marker = marker_value(write['marker']); plan = ChangePlan(jcs(write['plan'])); data = plan.data
    require(data['force']['requested'] and marker['plan_sha256'] == plan.sha256
        and marker['project_id'] == data['project_id'] and marker['request_id'] == data['request_id']
        and write['actor'] == data['actor'] and write['planned_at'] == data['planned_at']
        and write['change_plan_id'] == data['change_plan_id'] and write['operations'] == data['operations']
        and write['operations_sha256'] == operations_hash(data)
        and marker['base_model_root_sha256'] == data['base']['model_root_sha256']
        and marker['target_model_root_sha256'] == data['expected_result']['model_root_sha256'], 'force_receipt_plan_binding')
    force = validate_summary(write['force'])
    require(force == marker['force'] and {k: force[k] for k in ('requested', 'reason')} == data['force'], 'force_receipt_request_binding')
    require(type(write['target_inventory']) is list and type(write['files']) is list, 'force_inventory_fields')
    targets = {}
    for row in write['target_inventory']:
        require(type(row) is dict and set(row) == {'path', 'size', 'sha256'}, 'force_inventory_fields')
        effect_path(row['path']); _binding({k: row[k] for k in ('size', 'sha256')})
        require(row['path'] not in targets, 'force_duplicate_resource')
        targets[row['path']] = {k: row[k] for k in ('size', 'sha256')}
    paths = []
    for row in write['files']:
        require(type(row) is dict and set(row) == {'path', 'before', 'after'}, 'force_effect_fields')
        effect_path(row['path']); paths.append(row['path'])
        for side in ('before', 'after'):
            if row[side] is not None: _binding(row[side])
        require(row['before'] != row['after'] and targets.get(row['path']) == row['after'], 'force_effect_binding')
    require(paths == sorted(set(paths)) and list(targets) == sorted(targets), 'force_inventory_order')
    validate_report(write['validation'], write['target_inventory'])
    require(raw == jcs(transaction_document(write)), 'force_receipt_binding')
    return write


def completion(write, *, current):
    marker = write['marker']; group = receipt_group(write)
    proof = parsed(group[completion_marker_path(marker['transaction_id'])])
    return WriteCompletion(jcs(dict(format_version='force-transaction-completion-v1', state='committed',
        transaction_id=marker['transaction_id'], request_id=marker['request_id'], project_id=marker['project_id'],
        receipts=proof['receipts'], result_object=result_object(write), force=write['force'],
        validation_status=write['validation']['validation_status'],
        target_model_root_sha256=write['validation']['model_root_sha256'],
        commit_completed=True, receipt_verified=True, current_target_verified=current,
        cleanup_completed=True, cleanup_required=False, replayed=not current,
        write_authorized=False, approval_granted=False, atomic_snapshot=False)))


def read_group(files, transaction_id, *, project_id):
    from ._guarded_io import _read_path
    raw = _read_path(files, transaction_receipt_path(transaction_id))
    write = validate_transaction(raw)
    require(write['marker']['transaction_id'] == transaction_id and write['marker']['project_id'] == project_id,
        'force_receipt_project_binding', exit_code=6)
    group = receipt_group(write)
    require(all(_read_path(files, path) == expected for path, expected in group.items()), 'force_completion_changed', exit_code=6)
    return write
