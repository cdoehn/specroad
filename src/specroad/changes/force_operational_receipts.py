"""Passive validation of complete, separately owned operational attempts."""
from hashlib import sha256
import os

from ..model.canonical import canonical_json_bytes as jcs
from ..storage.json_syntax import parse_json_object as parsed
from .write_guard_values import require, inventory
from ._guarded_io import _read_path
from ._journal_codec import _hash
from .force_lock import ATTEMPTS, attempt_root


def check_observation(value):
    require(type(value) is dict and set(value) == {'format_version', 'plan_sha256',
        'root_identity', 'operational_inventory', 'operational_identities',
        'exclusive_access_proven', 'foreign_operation_completed'}, 'force_observation_fields')
    require(value['format_version'] == 'force-attempt-before-v1' and _hash(value['plan_sha256'])
        and type(value['exclusive_access_proven']) is bool and value['foreign_operation_completed'] is False,
        'force_observation_binding')
    require(type(value['root_identity']) is dict and set(value['root_identity']) == {'device', 'inode'}
        and all(type(v) is str and v.isdigit() for v in value['root_identity'].values()), 'force_root_identity')
    rows = value['operational_inventory']; identities = value['operational_identities']
    require(type(rows) is list and type(identities) is dict, 'force_original_inventory')
    paths = []
    from ..force_operations import explicit_path
    for row in rows:
        require(type(row) is dict and set(row) == {'path', 'size', 'sha256'}, 'force_original_inventory')
        path = explicit_path(row['path']); paths.append(path)
        from .force_bootstrap import PREFIXES
        require((path.startswith('.specroad/') or any(path == p + n for p in PREFIXES
            for n in ('pending.json', 'owner.json'))) and type(row['size']) is int and row['size'] >= 0
            and _hash(row['sha256']), 'force_original_inventory')
        require(type(identities.get(path)) is list and len(identities[path]) == 5
            and all(type(n) is int and n >= 0 for n in identities[path]), 'force_original_identity')
    require(paths == sorted(set(paths)) and set(paths) == set(identities), 'force_original_inventory')
    return value


def completion_seal(write, before_raw, owner_raw):
    from .force_receipts import receipt_group
    from ..model.canonical import canonical_json_sha256 as digest
    return jcs({'format_version': 'force-attempt-completed-v1',
        'transaction_id': write['marker']['transaction_id'],
        'plan_sha256': write['marker']['plan_sha256'], 'write_sha256': digest(write),
        'before_sha256': sha256(before_raw).hexdigest(), 'owner_sha256': sha256(owner_raw).hexdigest(),
        'receipts': {p: sha256(raw).hexdigest() for p, raw in sorted(receipt_group(write).items())}})


def read_attempt(files, transaction, *, project_id, check_originals=True):
    from .force_receipts import read_group
    root = attempt_root(transaction)
    with files.directory(tuple(root.split('/'))) as fd:
        require(fd is not None and set(os.listdir(fd)) == {'owner.json', 'before.json', 'complete.json', 'receipts'},
            'force_attempt_incomplete', exit_code=6)
    write = read_group(files, transaction, project_id=project_id, attempt=True)
    before_raw = _read_path(files, root + '/before.json')
    before = parsed(before_raw)
    require(set(before) == {'observation', 'inventory'} and jcs(before) == before_raw
        and before['observation'] == write['marker']['operational'], 'force_before_binding', exit_code=6)
    # Reconstruct the actual pre-effect inventory, not the plan's requested hashes.
    old = {row['path']: {k: row[k] for k in ('size', 'sha256')} for row in write['target_inventory']}
    for effect in write['files']:
        if effect['before'] is None:
            old.pop(effect['path'], None)
        else:
            old[effect['path']] = effect['before']
    require(before['inventory'] == [dict(path=p, **v) for p, v in sorted(old.items())],
        'force_before_inventory_binding', exit_code=6)
    from .lock_values import LockRecord
    owner = LockRecord(_read_path(files, root + '/owner.json')).data
    marker = write['marker']
    require(owner['transaction_id'] == transaction and owner['request_id'] == marker['request_id']
        and owner['project_id'] == project_id and owner['root_identity'] == before['observation']['root_identity']
        and marker['owner'] == {k: owner[k] for k in marker['owner']}, 'force_attempt_owner_binding', exit_code=6)
    require(_read_path(files, root + '/complete.json') == completion_seal(write, before_raw,
        _read_path(files, root + '/owner.json')), 'force_attempt_completion_binding', exit_code=6)
    if check_originals:
        for row in before['observation']['operational_inventory']:
            from .force_bootstrap import addressed
            with addressed(files, row['path']) as (observed_files, observed_path):
                raw = _read_path(observed_files, observed_path)
            require(len(raw) == row['size'] and sha256(raw).hexdigest() == row['sha256'],
                'force_original_changed', exit_code=6)
    require(_read_path(files, root + '/before.json') == before_raw, 'force_before_changed', exit_code=6)
    return write


def completed_attempts(files, *, include_incomplete=False, check_originals=False):
    with files.directory(tuple(ATTEMPTS.split('/'))) as fd:
        if fd is None:
            return []
        names = sorted(os.listdir(fd))
    result = []
    for transaction in names:
        root = attempt_root(transaction)
        if include_incomplete:
            complete = _read_path(files, root + '/complete.json', optional=True)
            if complete is None:
                continue
        raw = _read_path(files, root + '/receipts/transaction.json')
        value = parsed(raw)
        project_id = value.get('write', {}).get('marker', {}).get('project_id')
        result.append(read_attempt(files, transaction, project_id=project_id, check_originals=check_originals))
    with files.directory(tuple(ATTEMPTS.split('/'))) as fd:
        require(fd is not None and sorted(os.listdir(fd)) == names, 'force_attempt_set_changed', exit_code=6)
    return result


def replay(files, plan, command):
    if plan.data['request_id'] is None:
        return None
    from .force_receipts import completion
    from .force_outcome import _outcome
    matches = [w for w in completed_attempts(files, include_incomplete=True, check_originals=True) if w['marker']['request_id'] == plan.data['request_id']]
    if not matches:
        return None
    require(len(matches) == 1 and matches[0]['plan'] == plan.data
        and matches[0]['marker']['command_id'] == command, 'request_force_binding_conflict', exit_code=6)
    write = matches[0]
    return _outcome(plan, write['validation'], write['force'],
        completion=completion(write, current=False), replayed=True, command_id=command)


def read_force_attempt(root, transaction, *, expected_project_id):
    """Inspect an original complete attempt without clearing an older blocker."""
    from ._lock_files import LockFiles
    from .force_receipts import completion
    with LockFiles(root) as files:
        return completion(read_attempt(files, transaction, project_id=expected_project_id), current=False)


def validate_original_records(write, before_raw, owner_raw):
    before = parsed(before_raw)
    require(set(before) == {'observation', 'inventory'} and jcs(before) == before_raw
        and before['observation'] == write['marker']['operational'], 'force_before_binding', exit_code=6)
    # Reconstruct the actual pre-effect inventory, not the plan's requested hashes.
    old = {row['path']: {k: row[k] for k in ('size', 'sha256')} for row in write['target_inventory']}
    for effect in write['files']:
        if effect['before'] is None:
            old.pop(effect['path'], None)
        else:
            old[effect['path']] = effect['before']
    require(before['inventory'] == [dict(path=p, **v) for p, v in sorted(old.items())],
        'force_before_inventory_binding', exit_code=6)
    from .lock_values import LockRecord
    owner = LockRecord(owner_raw).data
    marker = write['marker']
    require(owner['transaction_id'] == marker['transaction_id'] and owner['request_id'] == marker['request_id']
        and owner['project_id'] == marker['project_id'] and owner['root_identity'] == before['observation']['root_identity']
        and marker['owner'] == {k: owner[k] for k in marker['owner']}, 'force_attempt_owner_binding', exit_code=6)


def reject_normal_request(files, request_id):
    """A Force completion cannot be reused as an ordinary request identity."""
    if request_id is None:
        return
    require(not any(write['marker']['request_id'] == request_id for write in
        completed_attempts(files, include_incomplete=True)), 'request_force_binding_conflict', exit_code=6)
