"""Closed passive records for a Restore Work owner handoff, never permission."""
from base64 import b64decode, b64encode
from hashlib import sha256
import re

from ..changes.lock_values import OwnerIdentity, ProjectLockError
from ..model.canonical import canonical_json_bytes
from ..recovery.values import RestoreError, require
from ..storage.json_syntax import parse_json_object


def digest(raw):
    return sha256(raw).hexdigest()


def reference(raw):
    return {'size': len(raw), 'sha256': digest(raw)}


def blob(raw):
    return {**reference(raw), 'base64': b64encode(raw).decode('ascii')}


def unblob(value):
    require(type(value) is dict and set(value) == {'size', 'sha256', 'base64'},
            'restore_work_handoff_blob_invalid')
    require(type(value['size']) is int and type(value['base64']) is str,
            'restore_work_handoff_blob_invalid')
    raw = b64decode(value['base64'], validate=True)
    require(blob(raw) == value, 'restore_work_handoff_bytes_changed', exit_code=6)
    return raw


def owner(raw, work_id):
    value = parse_json_object(raw)
    require(set(value) == {'format_version', 'work_id', 'owner_nonce', 'host_id',
                           'process_id', 'process_start_id'}
            and value['format_version'] in ('work-lock-v1', 'restore-work-lock-v1')
            and type(value['owner_nonce']) is str
            and re.fullmatch('[0-9a-f]{32}', value['owner_nonce']) is not None,
            'restore_work_owner_invalid')
    require(value['work_id'] == work_id, 'restore_work_owner_binding_changed', exit_code=6)
    try:
        return OwnerIdentity(value['host_id'], value['process_id'], value['process_start_id'])
    except ProjectLockError as error:
        raise RestoreError('restore_work_owner_invalid') from error


def file_binding(raw, identity):
    return {'bytes': blob(raw), 'device': str(identity[0]), 'inode': str(identity[1])}


def read_file_binding(value):
    require(type(value) is dict and set(value) == {'bytes', 'device', 'inode'},
            'restore_work_owner_file_binding_invalid')
    require(all(type(value[k]) is str and value[k].isascii() and value[k].isdecimal()
                and len(value[k]) <= 30 for k in ('device', 'inode')),
            'restore_work_owner_file_binding_invalid')
    return unblob(value['bytes']), (int(value['device']), int(value['inode']))


def completion(raw, value):
    return canonical_json_bytes({'format_version': 'restore-work-owner-complete-v1',
        'handoff': reference(raw), 'new_owner': value['new_owner'],
        'root_binding': value['root_binding'], 'checkpoint': value['checkpoint']})


def read_intent(raw, held, store):
    value = parse_json_object(raw)
    require(set(value) == {'format_version', 'root_binding', 'checkpoint',
                           'old_owner', 'new_owner', 'observation', 'reason'}
            and value['format_version'] == 'restore-work-owner-handoff-v1'
            and canonical_json_bytes(value) == raw, 'restore_work_handoff_invalid')
    require(value['root_binding'] == parse_json_object(held._binding),
            'restore_work_handoff_root_changed', exit_code=6)
    pointer = unblob(value['checkpoint'])
    # Historical generations remain independently anchored, not just hash-shaped.
    store._read_chain(held, pointer)
    old, _ = read_file_binding(value['old_owner'])
    new, _ = read_file_binding(value['new_owner'])
    old_identity, new_identity = owner(old, held.work_id), owner(new, held.work_id)
    require(parse_json_object(new)['format_version'] == 'restore-work-lock-v1'
            and old != new and old_identity.host_id is not None
            and old_identity.host_id == new_identity.host_id
            and old_identity.process_start_id is not None
            and new_identity.process_start_id is not None, 'restore_work_handoff_owner_invalid')
    observed = value['observation']
    require(type(observed) is dict and set(observed) == {'host_id', 'state', 'process_start_id'}
            and observed['host_id'] == old_identity.host_id, 'restore_work_handoff_observation_invalid')
    state, start = observed['state'], observed['process_start_id']
    require((state == 'absent' and start is None)
            or (state in ('alive', 'dead') and type(start) is str and bool(start)
                and (state == 'dead' or start != old_identity.process_start_id)),
            'restore_work_handoff_observation_invalid')
    require(type(value['reason']) is str and bool(value['reason'].strip())
            and value['reason'] == value['reason'].strip(), 'restore_work_handoff_reason_invalid')
    return value
