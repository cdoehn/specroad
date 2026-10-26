"""Closed immutable event inventories, never a blanket audit-directory exemption."""
from base64 import b64decode, b64encode
from uuid import UUID

from ..changes._journal_codec import _text, _transaction
from ..changes.lock_values import LockRecord
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..storage.json_syntax import parse_json_object
from ._codec import file_row
from ._execution_program import parents
from .values import require, persisted_contract


def owner_binding(old, layout, *, resuming):
    request, data = layout['binding']['request'], old.data
    require(data['project_id'] == request['project_id'] and data['root_identity'] == {
        'device': str(request['root_identity'][0]), 'inode': str(request['root_identity'][1])},
        'restore_owner_project_conflict', exit_code=6)
    _transaction(data['transaction_id'])
    if resuming:
        require(data['kind'] == 'recovery' and data['command'] == 'recover restore'
                and data['transaction_id'] == 'restore-' + layout['token']
                and data['request_id'] == request['request_id'],
                'restore_owner_execution_conflict', exit_code=6)
        return {'case': 'resume', 'execution_sha256': canonical_json_sha256(layout['binding'])}
    require(data['kind'] in ('writer', 'recovery') and data['command'] != 'recover restore',
            'restore_owner_not_old_transaction', exit_code=6)
    selected = {r['path']: r for r in request['affected_journals']['entries']}
    path = '.specroad/transactions/' + data['transaction_id']
    require(path in selected, 'restore_owner_not_selected', exit_code=6)
    return {'case': 'new', 'original_entry': selected[path]}


def unfinished_old_handoff(owner, layout, contents):
    """Only the original pre-journal handoff can retain an ordinary owner."""
    if any(layout[k] + '/intent.json' in contents for k in ('active', 'terminal')):
        return False
    prefix = layout['active'] + '/takeovers/'
    for path, raw in contents.items():
        parts = path[len(prefix):].split('/') if path.startswith(prefix) else []
        if len(parts) != 2 or parts[1] != 'intent.json':
            continue
        value = parse_json_object(raw)
        details = value['details']
        # classify()/observed_events() has already reconstructed every byte;
        # the live inventory and owner are checked again under the mutex.
        if (details['request']['binding']['case'] == 'new'
                and b64decode(details['old_bytes'], validate=True) == owner.source_bytes
                and path.rsplit('/', 1)[0] + '/completed.json' not in contents):
            return True
    return False


@persisted_contract
def event_files(layout, event_id, kind, details, *, terminal=False, location='active'):
    """Reconstruct all permitted bytes/parents; the intent only names itself."""
    require(type(event_id) is str and str(UUID(event_id)) == event_id and UUID(event_id).version == 4,
            'restore_event_identity_invalid')
    require(kind in ('takeovers', 'actions'), 'restore_event_kind_invalid')
    require(location in ('active', 'terminal'), 'restore_event_location_invalid')
    root = layout[location] + '/' + kind + '/' + event_id
    request = details.get('request')
    require(type(details) is dict and _text(details.get('authority_id'))
            and _text(details.get('authority_version')) and type(request) is dict,
            'restore_event_attribution_invalid')
    if kind == 'takeovers':
        require(set(details) == {'authority_id', 'authority_version', 'request', 'old_bytes', 'new_bytes'},
                'restore_handoff_shape_invalid')
        old_raw, new_raw = (b64decode(details[k], validate=True) for k in ('old_bytes', 'new_bytes'))
        require(all(b64encode(raw).decode('ascii') == details[k] for raw, k in
                    ((old_raw, 'old_bytes'), (new_raw, 'new_bytes'))), 'restore_handoff_encoding_invalid')
        old, new = LockRecord(old_raw), LockRecord(new_raw)
        require(new.data['lock_id'] == event_id, 'restore_handoff_identity_conflict', exit_code=6)
        owner_binding(new, layout, resuming=True)
        require(set(request) == {'action', 'command', 'project_id', 'root_identity', 'restore_request',
                    'actor', 'lock_record', 'lock_sha256', 'observed_owner_state', 'reason', 'force',
                    'accept_remote_risk', 'binding'}
                and request['action'] == 'takeover' and request['command'] == 'recover restore'
                and request['restore_request'] == layout['binding']['request']
                and request['project_id'] == layout['binding']['request']['project_id']
                and request['root_identity'] == layout['binding']['request']['root_identity']
                and request['lock_record'] == old.data and request['lock_sha256'] == old.sha256
                and request['force'] is True and type(request['accept_remote_risk']) is bool
                and request['observed_owner_state'] in ('dead', 'foreign', 'unverifiable', 'pid_reused')
                and (request['observed_owner_state'] == 'dead' or request['accept_remote_risk'])
                and _text(request['reason']), 'restore_handoff_request_invalid')
        from ..changes.authoring import normalize_authoring_actor
        require(normalize_authoring_actor(request['actor']).as_fields() == request['actor'],
                'restore_handoff_actor_invalid')
        case = request['binding'].get('case') if type(request['binding']) is dict else None
        require(case in ('new', 'resume') and request['binding'] == owner_binding(old, layout,
                    resuming=case == 'resume'), 'restore_handoff_owner_conflict', exit_code=6)
        files = {root + '/owner.before.json': old_raw, root + '/owner.pending.json': new_raw,
            root + '/completed.json': canonical_json_bytes({'format_version': 'restore-owner-handoff-v1',
                'phase': 'completed', 'event_id': event_id, 'request_sha256': layout['token'],
                'old_record_sha256': old.sha256, 'new_record_sha256': new.sha256, 'normative_writes': 0})}
    else:
        require(set(details) == {'authority_id', 'authority_version', 'request', 'source_observation'},
                'restore_action_shape_invalid')
        require(request.get('action') in ('rollback', 'complete', 'replay')
                and request.get('original_request') == layout['binding']['request']
                and set(request) == {'action', 'original_request', 'actor', 'observed_inventory_sha256'},
                'restore_action_request_invalid')
        from ..changes.authoring import normalize_authoring_actor
        require(normalize_authoring_actor(request['actor']).as_fields() == request['actor'],
                'restore_action_actor_invalid')
        from ._codec import digest
        digest(request['observed_inventory_sha256'])
        observation = details['source_observation']
        require(type(observation) is dict and set(observation) == {'status', 'reason'}
                and observation['status'] in ('unchanged', 'unavailable_or_changed')
                and (observation['reason'] is None if observation['status'] == 'unchanged'
                     else _text(observation['reason'])), 'restore_source_observation_invalid')
        files = {}
    directories = sorted(set(p for path in [*files, root + '/intent.json']
        for p in parents(path, layout['binding']['original_plan']['inventory']['roots'])))
    files[root + '/intent.json'] = canonical_json_bytes({
        'format_version': 'restore-owner-handoff-v1' if kind == 'takeovers' else 'restore-recovery-action-v1',
        'event_id': event_id, 'kind': kind, 'location_at_creation': location,
        'original_execution': layout['binding'], 'details': details,
        'own_files': [file_row(p, raw) for p, raw in sorted(files.items())],
        'own_directories': directories})
    if terminal and location == 'active':
        files = {layout['terminal'] + p[len(layout['active']):]: raw for p, raw in files.items()}
        directories = [layout['terminal'] + p[len(layout['active']):]
                       if p == layout['active'] or p.startswith(layout['active'] + '/') else p
                       for p in directories]
        directories += list(parents(layout['terminal'] + '/intent.json',
                                   layout['binding']['original_plan']['inventory']['roots']))
    return files, directories


def observed_events(layout, inventory, contents, owner=None):
    """Only exact members of complete immutable event intents are explainable."""
    result = {}
    expected = {r['path']: r for r in inventory['entries']}
    for location in ('active', 'terminal'):
        prefix = layout[location] + '/'
        for path, raw in contents.items():
            if not path.startswith(prefix):
                continue
            parts = path[len(prefix):].split('/')
            if len(parts) != 3 or parts[0] not in ('takeovers', 'actions') or parts[2] != 'intent.json':
                continue
            value = parse_json_object(raw)
            require(type(value.get('details')) is dict, 'restore_event_details_missing')
            files, directories = event_files(layout, parts[1], parts[0], value['details'],
                                            terminal=location == 'terminal', location=value.get('location_at_creation'))
            require(files[path] == raw, 'restore_event_binding_conflict', path=path, exit_code=6)
            for own_path, own_raw in files.items():
                if own_path in expected:
                    row = {**file_row(own_path, own_raw), 'kind': 'file'}
                    require(expected[own_path] == row, 'restore_event_bytes_conflict', path=own_path, exit_code=6)
                    result[own_path] = row
            for directory in directories:
                if directory in expected:
                    require(expected[directory]['kind'] == 'directory', 'restore_event_directory_conflict',
                            path=directory, exit_code=6)
                    result[directory] = expected[directory]
            if parts[0] == 'takeovers':
                prefix = path.rsplit('/', 1)[0]
                old_raw, new_raw = (b64decode(value['details'][k], validate=True) for k in ('old_bytes', 'new_bytes'))
                if owner is not None and owner.source_bytes == new_raw:
                    require(prefix + '/owner.before.json' in expected, 'restore_handoff_original_missing')
                    require(prefix + '/owner.pending.json' not in expected,
                            'restore_handoff_owner_stage_conflict', exit_code=6)
                if prefix + '/completed.json' in expected:
                    require(prefix + '/owner.before.json' in expected and prefix + '/owner.pending.json' not in expected,
                            'restore_handoff_completion_conflict', exit_code=6)
                    require(owner is None or owner.source_bytes != old_raw,
                            'restore_handoff_completed_owner_conflict', exit_code=6)
                if prefix + '/owner.pending.json' in expected:
                    require(prefix + '/owner.before.json' in expected, 'restore_handoff_original_missing')
    return result
