"""Byte-proven interrupted Restore completion; never forward-resume a partial target."""
from base64 import b64decode
from uuid import uuid4

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.operational_paths import recovery_resource_role
from ..storage.json_syntax import parse_json_object
from ._codec import file_row
from ._execution_binding import checked_layout
from ._execution_events import event_files, observed_events
from ._execution_program import publication_program, match_prefix, parents
from ._validation import validate_project
from .values import require, RestoreError, persisted_contract


def discover(plan, project, request_id, inventory, contents):
    candidates = {}
    for path, raw in contents.items():
        if not (path.startswith('.specroad/recovery/restore-') or
                path.startswith('.specroad/recovery/transaction-audit/restore-')) or not path.endswith('/intent.json'):
            continue
        try:
            value = parse_json_object(raw)
        except Exception:
            # An arbitrary selected old journal may be damaged. It is not a
            # candidate; the original-inventory/owner checks still apply.
            continue
        value = value.get('original_execution', value)
        if type(value) is not dict or value.get('format_version') != 'restore-execution-v1':
            continue
        request = value.get('request')
        if type(request) is not dict:
            continue
        if request_id is not None and request.get('request_id') == request_id:
            require(request.get('plan_bytes_sha256') == plan.sha256,
                    'restore_request_binding_conflict', exit_code=6)
        if request.get('plan_bytes_sha256') != plan.sha256 or request.get('request_id') != request_id:
            continue
        layout = checked_layout(canonical_json_bytes(value), plan, project)
        require(path.startswith(layout['active'] + '/') or path.startswith(layout['terminal'] + '/'),
                'restore_execution_location_conflict', exit_code=6)
        candidates[layout['token']] = layout
    require(len(candidates) <= 1, 'restore_ambiguous_execution', exit_code=6)
    return next(iter(candidates.values()), None)


def full_target(state, layout):
    for path in layout['changes']:
        wanted = None if path not in layout['target'] else {
            **file_row(path, layout['target'][path]), 'kind': 'file'}
        row = state.get(path)
        if wanted is None:
            if row is not None and row['kind'] != 'missing':
                return False
        elif row != wanted:
            return False
    return all(state.get(p) == {**file_row(p, raw), 'kind': 'file'} for p, raw in layout['target'].items())


def rollback_program(plan, layout, initial):
    """Before images and reversals depend only on a checked forward prefix."""
    active, archive = layout['active'], layout['archive']
    roots = plan.data['inventory']['roots']
    original = {r['path']: r for r in plan.data['inventory']['entries']}
    objects = {r['sha256']: b64decode(r['data_base64'], validate=True) for r in plan.data['objects']}
    own, targets, program, changed = {}, {}, [], []
    intent = active + '/rollback/intent.json'
    program.append(('create', intent))
    for i, path in enumerate(reversed(layout['changes'])):
        before, current = original.get(path), initial.get(path)
        if before == current or before is None and (current is None or current['kind'] == 'missing'):
            continue
        changed.append(path)
        if before is not None and before['kind'] == 'file':
            raw = objects[before['sha256']]
            stage = active + '/rollback/staging/' + str(i)
            own[stage] = raw
            targets[path] = raw
            program += [('create', stage), ('publish', path, stage)]
        else:
            require(before is None or before['kind'] == 'missing', 'restore_rollback_original_kind_invalid')
            program.append(('remove', path))
        effect = active + '/rollback/effects/' + str(i) + '.json'
        own[effect] = canonical_json_bytes({'request_sha256': layout['token'], 'path': path,
                                          'before_recovery': current, 'original': before})
        program.append(('create', effect))
    new_directories = [p for p, r in initial.items() if r['kind'] == 'directory'
        and recovery_resource_role(p) is None and original.get(p, {}).get('kind') != 'directory']
    for path in sorted(new_directories, key=lambda p: (-len(p.split('/')), p.encode('utf-8'))):
        program.append(('rmdir', path))
    initial_rows = [initial[p] for p in sorted(initial, key=lambda p: p.encode('utf-8'))]
    completion = {'format_version': 'restore-rollback-completion-v1', 'request_sha256': layout['token'],
        'request': layout['binding']['request'], 'result': 'rolled_back', 'recovery_required': True,
        'forward_prefix_sha256': canonical_json_sha256(initial_rows), 'normative_paths': changed}
    own[archive + '/rolled_back.json'] = canonical_json_bytes(completion)
    program.append(('create', archive + '/rolled_back.json'))
    directories = sorted(set(p for operation in program if operation[0] in ('create', 'publish')
                             for p in parents(operation[1], roots)))
    binding = {'format_version': 'restore-rollback-v1', 'request_sha256': layout['token'],
        'forward_prefix': initial_rows, 'own_files': [file_row(p, raw) for p, raw in sorted(own.items())],
        'own_directories': directories, 'operations': [list(p) for p in program]}
    own[intent] = canonical_json_bytes(binding)
    return {**layout, 'own': {**layout['own'], **own}, 'target': targets}, program, completion


@persisted_contract
def classify(plan, layout, inventory, contents, owner=None):
    roots, original = (plan.data['inventory'][k] for k in ('roots', 'entries'))
    forward = publication_program(layout)
    events = observed_events(layout, inventory, contents, owner)
    if (layout['active'] + '/committing.json' in contents or layout['terminal'] + '/committing.json' in contents):
        required = [p for p in layout['own'] if p.startswith(layout['archive'] + '/')
                    and not p.endswith('/completed.json')]
        require(all(p in contents for p in required), 'restore_required_backup_missing')
    rollback_path = layout['active'] + '/rollback/intent.json'
    if rollback_path in contents:
        value = parse_json_object(contents[rollback_path])
        require(type(value.get('forward_prefix')) is list, 'restore_rollback_prefix_missing')
        _, initial = match_prefix(value['forward_prefix'], original, forward, layout, roots)
        committing = layout['active'] + '/committing.json' in initial
        require(not committing or not full_target(initial, layout), 'restore_rollback_full_target_forbidden', exit_code=6)
        reverse, program, completion = rollback_program(plan, layout, initial)
        require(contents[rollback_path] == reverse['own'][rollback_path], 'restore_rollback_binding_conflict', exit_code=6)
        index, state = match_prefix(inventory['entries'], value['forward_prefix'], program, reverse, roots, evidence=events)
        return {'action': 'replay' if index == len(program) else 'rollback', 'index': index,
                'state': state, 'layout': reverse, 'program': program, 'completion': completion, 'events': events}
    index, state = match_prefix(inventory['entries'], original, forward, layout, roots, evidence=events)
    if index == len(forward):
        require(layout['active'] not in {r['path'] for r in inventory['entries']},
                'restore_terminal_active_conflict', exit_code=6)
        return {'action': 'replay', 'index': index, 'state': state, 'layout': layout,
                'program': forward, 'completion': layout['completed'], 'events': events}
    require(layout['terminal'] not in {r['path'] for r in inventory['entries']},
            'restore_active_terminal_conflict', exit_code=6)
    if layout['active'] + '/committing.json' in state and full_target(state, layout):
        return {'action': 'complete', 'index': index, 'state': state, 'layout': layout,
                'program': forward, 'completion': layout['completed'], 'events': events}
    reverse, program, completion = rollback_program(plan, layout, state)
    return {'action': 'rollback', 'index': 0, 'state': state, 'layout': reverse,
            'program': program, 'completion': completion, 'events': events}


def resume(store, plan, original_layout, classified, *, authority, actor, authorize, source_observation):
    request = {'action': classified['action'], 'original_request': original_layout['binding']['request'],
               'actor': actor.as_fields(), 'observed_inventory_sha256':
                   canonical_json_sha256([store.expected[p] for p in sorted(store.expected)])}
    authorize(authority, request)
    store.check()
    if classified['action'] != 'replay':
        details = {'authority_id': authority.authority_id, 'authority_version': authority.version,
                   'request': request, 'source_observation': source_observation}
        location = 'terminal' if original_layout['terminal'] in store.expected else 'active'
        own, _ = event_files(original_layout, str(uuid4()), 'actions', details, location=location)
        store.own = {**store.own, **own}
        path = next(iter(own))
        store.create(path, own[path])
    layout = classified['layout']
    store.own = {**store.own, **layout['own']}
    store.targets = layout['target']
    for operation in classified['program'][classified['index']:]:
        kind, path, *rest = operation
        if classified['action'] != 'rollback':
            require(kind in ('create', 'move'), 'restore_forward_resume_forbidden', exit_code=7)
        if kind == 'create':
            if '/rollback/staging/' in path:
                raw = store.own[path]
                from hashlib import sha256
                require(store.read(original_layout['archive'] + '/objects/' + sha256(raw).hexdigest()) == raw,
                        'restore_backup_bytes_conflict', exit_code=6)
            if path == original_layout['archive'] + '/completed.json':
                actual = {p: store.read(p) for p in original_layout['target']}
                require(actual == original_layout['target'] and validate_project(actual)[1] == plan.data['expected_target_root'],
                        'restore_actual_target_conflict', exit_code=6)
            store.create(path, store.own[path])
        elif kind == 'publish':
            store.publish(rest[0], path, store.targets[path])
        elif kind == 'remove':
            store.remove(path)
        elif kind == 'rmdir':
            store.remove_directory(path)
        elif kind == 'move':
            store.archive(path, rest[0])
    store.check()
    completion = classified['completion']
    if completion['result'] == 'restored':
        actual = {p: store.read(p) for p in original_layout['target']}
        require(actual == original_layout['target'] and validate_project(actual)[1] == plan.data['expected_target_root'],
                'restore_actual_target_conflict', exit_code=6)
        require(not store.files.journal_entries(), 'restore_remaining_journals', exit_code=5)
    return {**completion, 'recovery_required': completion['result'] != 'restored',
            'replayed': classified['action'] == 'replay', 'source_observation': source_observation,
            'audit_path': original_layout['archive'] + ('/completed.json' if completion['result'] == 'restored'
                                                       else '/rolled_back.json')}
