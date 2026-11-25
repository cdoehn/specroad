"""Closed Force completion records for the existing guarded writer.

These records prove execution and preserve negative findings. They never
constitute an approval or replace an earlier transaction's evidence.
"""
import os
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


def marker_value(value, *, force=None, operational=None):
    if force is not None:
        value = {**value, 'format_version': 'force-write-guard-v1', 'force': validate_summary(force)}
    if operational is not None:
        value = {**value, 'format_version': 'force-write-guard-v2', 'operational': operational}
    fields = {'format_version', 'project_id', 'transaction_id', 'request_id', 'command_id',
        'plan_sha256', 'base_model_root_sha256', 'target_model_root_sha256', 'owner', 'state', 'force'}
    if value.get('format_version') == 'force-write-guard-v2':
        fields.add('operational')
        from .force_operational_receipts import check_observation
        check_observation(value['operational'])
    require(type(value) is dict and set(value) == fields and value['format_version'] in ('force-write-guard-v1', 'force-write-guard-v2')
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


def paths(marker):
    if marker['format_version'] == 'force-write-guard-v2':
        from .force_lock import attempt_root
        root = attempt_root(marker['transaction_id']) + '/receipts/'
        return root + 'transaction.json', root + 'committed.json', (
            None if marker['request_id'] is None else root + 'request.json')
    return (transaction_receipt_path(marker['transaction_id']),
        completion_marker_path(marker['transaction_id']),
        None if marker['request_id'] is None else request_receipt_path(marker['request_id']))


def receipt_group(write):
    marker = write['marker']; transaction = transaction_document(write)
    transaction_path, completed_path, request_path = paths(marker)
    path = transaction_path; raw = jcs(transaction)
    refs = {'transaction': {'path': path, 'sha256': sha256(raw).hexdigest()}, 'request': None}
    group = {path: raw}
    if marker['request_id'] is not None:
        path = request_path
        request = dict(format_version='force-request-receipt-v1', namespace='normative_write',
            request_id=marker['request_id'], project_id=marker['project_id'], transaction_id=marker['transaction_id'],
            actor=write['actor'], operations_sha256=write['operations_sha256'], plan_sha256=marker['plan_sha256'],
            force=write['force'], result='committed', result_object=transaction['result_object'],
            transaction_receipt=refs['transaction'])
        raw = jcs(request); group[path] = raw; refs['request'] = {'path': path, 'sha256': sha256(raw).hexdigest()}
    group[completed_path] = jcs(dict(format_version='force-write-completion-v1',
        project_id=marker['project_id'], transaction_id=marker['transaction_id'], write_sha256=digest(write),
        receipts=refs, force=write['force'], validation_status=write['validation']['validation_status']))
    return group


from ..qualification.errors import persisted_contract


@persisted_contract
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
    if marker['format_version'] == 'force-write-guard-v2':
        require(data['format_version'] == '1.5.0' and marker['operational']['plan_sha256'] == plan.sha256,
            'force_operational_plan_binding')
    require(data['force']['requested'] and marker['plan_sha256'] == plan.sha256
        and marker['project_id'] == data['project_id'] and marker['request_id'] == data['request_id']
        and write['actor'] == data['actor'] and write['planned_at'] == data['planned_at']
        and write['change_plan_id'] == data['change_plan_id'] and write['operations'] == data['operations']
        and write['operations_sha256'] == operations_hash(data)
        and marker['base_model_root_sha256'] == data['base']['model_root_sha256']
        and marker['target_model_root_sha256'] == data['expected_result']['model_root_sha256'], 'force_receipt_plan_binding')
    if data.get('native_intent') is not None:
        require(marker['command_id'] in ('change.apply', data['native_intent']['command_id']),
            'force_native_command_binding')
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
    from ..force import ForceDecisions
    from .force_target import record_findings
    ledger = ForceDecisions(ForceRequest.from_mapping(data['force']))
    requested_binding = {'plan_sha256': plan.sha256, 'target_inventory_sha256': digest(write['target_inventory']),
        'expected_model_root_sha256': data['expected_result']['model_root_sha256']}
    record_findings(ledger, write['validation'], operation=marker['command_id'], requested_binding=requested_binding)
    require(all(row in force['overrides'] for row in ledger.summary['overrides']), 'force_missing_negative_finding')
    from .resource_replace import target_bytes
    effects = {row['path']: row for row in write['files']}
    raw_operations = [op for op in data['operations'] if op['op'] == 'resource_replace']
    if raw_operations:
        require(set(effects) <= {op['path'] for op in raw_operations}, 'force_unrequested_effect')
        for operation in raw_operations:
            path = operation['path']; after = metadata(target_bytes(operation))
            require(targets.get(path) == after, 'force_raw_target_binding')
            observed = effects[path]['before'] if path in effects else after
            actual_hash = 'absent' if observed is None else observed['sha256']
            if actual_hash != operation['observed_byte_sha256']:
                require(any(row['gate_id'] == 'hash:resource_precondition' and row['subject'] == path
                    and row['observed_binding'] == actual_hash and row['requested_binding'] == operation['observed_byte_sha256']
                    for row in force['overrides']), 'force_missing_source_override')
    else:
        from .resource_replace import check_plan
        if check_plan(data):
            require(not effects, 'force_unrequested_effect')
        else:
            from .force_projection import check_recorded_effects
            check_recorded_effects(data, targets, effects, write['validation']['resources'])
    require(raw == jcs(transaction_document(write)), 'force_receipt_binding')
    return write


def completion(write, *, current):
    marker = write['marker']; group = receipt_group(write)
    proof = parsed(group[paths(marker)[1]])
    return WriteCompletion(jcs(dict(format_version='force-transaction-completion-v1', state='committed',
        transaction_id=marker['transaction_id'], request_id=marker['request_id'], project_id=marker['project_id'],
        receipts=proof['receipts'], result_object=result_object(write), force=write['force'],
        validation_status=write['validation']['validation_status'],
        target_model_root_sha256=write['validation']['model_root_sha256'],
        commit_completed=True, receipt_verified=True, current_target_verified=current,
        cleanup_completed=True, cleanup_required=False, replayed=not current,
        write_authorized=False, approval_granted=False, atomic_snapshot=False)))


def read_group(files, transaction_id, *, project_id, attempt=False):
    """Missing/unreadable originals are structured failures, never completion."""
    from .write_guard_values import WriteGuardError
    try:
        return _read_group(files, transaction_id, project_id=project_id, attempt=attempt)
    except FileNotFoundError as error:
        raise WriteGuardError('force_completion_missing', exit_code=6) from error
    except OSError as error:
        raise WriteGuardError('force_completion_read_failed', exit_code=5) from error


def _read_group(files, transaction_id, *, project_id, attempt=False):
    from ._guarded_io import _read_path
    if attempt:
        from .force_lock import attempt_root
        source_path = attempt_root(transaction_id) + '/receipts/transaction.json'
    else:
        source_path = transaction_receipt_path(transaction_id)
    raw = _read_path(files, source_path)
    write = validate_transaction(raw)
    require(write['marker']['transaction_id'] == transaction_id and write['marker']['project_id'] == project_id,
        'force_receipt_project_binding', exit_code=6)
    group = receipt_group(write)
    require(paths(write['marker'])[0] == source_path, 'force_receipt_location_binding')
    prefix = source_path.rsplit('/', 1)[0]
    from ..security import paths as guards
    from ._journal_io import _read
    identities = {}
    for repeat in range(2):
        with files.directory(tuple(prefix.split('/'))) as fd:
            require(fd is not None and set(os.listdir(fd)) == {p.rsplit('/', 1)[-1] for p in group if p.startswith(prefix + '/')},
                'force_completion_namespace_changed', exit_code=6)
        for path, expected in group.items():
            with files.directory(tuple(path.split('/')[:-1])) as fd:
                require(fd is not None, 'force_completion_missing', exit_code=6)
                name = path.rsplit('/', 1)[-1]
                ident = guards._identity(os.stat(name, dir_fd=fd, follow_symlinks=False))
                require(_read(fd, name, expected_identity=ident) == expected
                    and (repeat == 0 or identities[path] == ident), 'force_completion_changed', exit_code=6)
                identities[path] = ident
        files.check_root()
    return write
