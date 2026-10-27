"""One explicitly authorized Restore publication, with durable original evidence.

The independently authorized continuation/rollback adapter is a separate
recovery operation, derived from the original binding and actual bytes.
It never converts its saved plan, actor label or journal into permission.
"""
from dataclasses import dataclass

from ..changes.authoring import normalize_authoring_actor, normalize_request_id
from ..changes._lock_files import LockFiles
from ..changes.recovery_values import RecoveryAuthority
from ..changes.receipt_values import request_receipt_path
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..storage.json_syntax import parse_json_object
from ._codec import file_row
from ._execution_layout import execution_layout
from ._execution_binding import restore_request, original_active
from ._execution_lock import restore_lock, takeover_options
from ._execution_resume import discover, classify, resume
from ._execution_events import unfinished_old_handoff
from ._inventory import boundary, read_source, observe
from ._journal_selection import journal_selection
from ._observations import verify_live
from ._validation import validate_project
from .values import RestorePlan, RestoreError, require, guarded


@dataclass(frozen=True, init=False)
class RestoreCompletion:
    _raw: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use execute_restore')

    @classmethod
    def _create(cls, data):
        value = object.__new__(cls)
        object.__setattr__(value, '_raw', canonical_json_bytes(data))
        return value

    @property
    def data(self):
        return parse_json_object(self._raw)

    def __bool__(self):
        raise TypeError('Inspect the actual Restore outcome')


def _authorize(authority, request):
    encoded = canonical_json_bytes(request)
    detached = parse_json_object(encoded)
    try:
        approved = authority.check(detached)
        unchanged = canonical_json_bytes(detached) == encoded
    except Exception as error:
        raise RestoreError('restore_authority_failed', exit_code=7) from error
    require(type(approved) is bool and approved and unchanged,
            'restore_not_authorized', exit_code=7)


def _source(data, origin):
    for row in [data['source'], *data['source']['dependencies']]:
        try:
            content = read_source(origin, row['path'])
        except FileNotFoundError as error:
            raise RestoreError('restore_input_disappeared', exit_code=6) from error
        require(file_row(row['path'], content) == {k: row[k] for k in ('path', 'size', 'sha256')},
                'restore_source_changed', path=row['path'], exit_code=6)


def execute_restore(raw, *, expected_target_root, authority, actor, request_id=None,
                    affected_journals=None, force=False, expected_lock_sha256=None,
                    reason=None, accept_remote_risk=False, owner_probe=None,
                    expected_original_actor=None):
    """Publish the exact supported full plan under fresh authorization and lock.

    No caller supplies substitute model checks. A failed/unfinished attempt
    leaves its exact plan, original bytes, target staging and active barrier.
    Existing owners require an explicit, independently authorized handoff.
    An optional independently bound original actor is a precondition, never a
    substitute for the current recovery actor or host authorization.
    """
    progress = {'mutation_possible': False, 'recovery_required': False}
    try:
        return _execute_restore(raw, expected_target_root=expected_target_root,
            authority=authority, actor=actor, request_id=request_id,
            affected_journals=affected_journals, progress=progress, force=force,
            expected_lock_sha256=expected_lock_sha256, reason=reason,
            accept_remote_risk=accept_remote_risk, owner_probe=owner_probe,
            expected_original_actor=expected_original_actor)
    except RestoreError as error:
        error.mutation_possible |= progress['mutation_possible']
        error.recovery_required |= error.mutation_possible or progress['recovery_required']
        raise


@guarded
def _execute_restore(raw, *, expected_target_root, authority, actor, request_id,
                     affected_journals, progress, force, expected_lock_sha256,
                     reason, accept_remote_risk, owner_probe, expected_original_actor):
    takeover_options(force, expected_lock_sha256, reason, accept_remote_risk)
    require(type(authority) is RecoveryAuthority, 'restore_authority_required', exit_code=2)
    actor = normalize_authoring_actor(actor)
    original_actor = (None if expected_original_actor is None else
                      normalize_authoring_actor(expected_original_actor).as_fields())
    request_id = normalize_request_id(request_id)
    request_id = None if request_id is None else request_id.value
    require(actor.actor_type not in ('ai', 'ci') or request_id is not None,
            'restore_request_id_required', exit_code=2)
    require(type(expected_target_root) is str and len(expected_target_root) == 64
            and all(c in '0123456789abcdef' for c in expected_target_root),
            'restore_expected_target_required', exit_code=2)
    plan = RestorePlan(raw)
    data = plan.data
    require(expected_target_root == data['expected_target_root'], 'restore_target_binding_conflict', exit_code=6)
    project = boundary(data['project_root'])
    if request_id is not None:
        require(all(r['path'] != request_receipt_path(request_id) for r in data['inventory']['entries']),
                'restore_request_binding_conflict', exit_code=6)
    with LockFiles(project.root) as files:
        # Preserve an observed blocker even when original-inventory freshness
        # subsequently fails (for example after a prior interrupted attempt).
        progress['recovery_required'] = True
        active_entries = files.journal_entries()
        owner = files.read_record()[0]
        progress['recovery_required'] = bool(active_entries) or owner is not None
        inventory, contents = observe(project, data['inventory']['roots'])
        previous = discover(plan, project, request_id, inventory, contents)
        if previous is not None:
            require(original_actor is None or previous['binding']['request']['actor'] == original_actor,
                    'restore_original_actor_conflict', exit_code=6)
            selection = journal_selection(plan, affected_journals, original_active(plan))
            require(selection == previous['binding']['request']['affected_journals'],
                    'restore_selection_changed', exit_code=6)
            classification = classify(plan, previous, inventory, contents, owner)
            if owner is not None and owner.data['command'] != 'recover restore':
                require(unfinished_old_handoff(owner, previous, contents),
                        'restore_owner_execution_conflict', exit_code=6)
            if owner is not None and classification['action'] == 'replay' and classification['completion']['result'] == 'restored':
                classification['action'] = 'complete'
            expected = {r['path']: r for r in inventory['entries']}
            recovery_request = {'action': classification['action'], 'original_request': previous['binding']['request'],
                                'actor': actor.as_fields(), 'observed_inventory_sha256': canonical_json_sha256(inventory['entries'])}
            _authorize(authority, recovery_request)

            def fresh_recovery(locked):
                require(locked.boundary._root_identity == project._root_identity,
                        'restore_root_changed', exit_code=7)
                _authorize(authority, recovery_request)
                current, _ = observe(project, data['inventory']['roots'])
                require(current == inventory, 'restore_recovery_inventory_changed', exit_code=6)
                require(locked.journal_entries() == active_entries, 'restore_active_set_changed', exit_code=6)

            observation = {'status': 'unchanged', 'reason': None}
            try:
                _source(data, boundary(data['source']['root']))
            except (OSError, ModelError, SafetyViolation) as error:
                observation = {'status': 'unavailable_or_changed', 'reason': getattr(error, 'reason', 'restore_source_unavailable')}
            with restore_lock(project, plan, previous, expected, authority=authority, actor=actor,
                    refresh=fresh_recovery, authorize=_authorize, progress=progress, resuming=True,
                    force=force, expected_lock_sha256=expected_lock_sha256, reason=reason,
                    accept_remote_risk=accept_remote_risk, owner_probe=owner_probe) as store:
                store.synchronize()
                return RestoreCompletion._create(resume(store, plan, previous, classification,
                    authority=authority, actor=actor, authorize=_authorize, source_observation=observation))
        require(original_actor is None or actor.as_fields() == original_actor,
                'restore_original_actor_conflict', exit_code=6)
        origin = boundary(data['source']['root'])
        verify_live(plan, project, origin)
        selection = journal_selection(plan, affected_journals, active_entries)
        if owner is not None and not force:
            raise RestoreError('restore_owner_recovery_required', exit_code=5, recovery_required=True)
    request = restore_request(plan, project, actor, request_id, selection)
    _authorize(authority, request)
    layout = execution_layout(plan, request, authority)
    token, active, archive, terminal = (layout[k] for k in ('token', 'active', 'archive', 'terminal'))
    target, changes, own = (layout[k] for k in ('target', 'changes', 'own'))
    original = {r['path'] for r in data['inventory']['entries']}
    require(not original.intersection(own) and active not in original and terminal not in original,
            'restore_own_path_collision', exit_code=6)

    def fresh(files):
        require(files.boundary._root_identity == project._root_identity,
                'restore_root_changed', exit_code=7)
        verify_live(plan, project, origin)
        require(journal_selection(plan, affected_journals, files.journal_entries()) == selection,
                'restore_selection_changed', exit_code=6)
        _authorize(authority, request)
        verify_live(plan, project, origin)

    with restore_lock(project, plan, layout, {r['path']: r for r in data['inventory']['entries']},
            authority=authority, actor=actor, refresh=fresh, authorize=_authorize, progress=progress, resuming=False,
            force=force, expected_lock_sha256=expected_lock_sha256, reason=reason,
            accept_remote_risk=accept_remote_risk, owner_probe=owner_probe,
            source_check=lambda: _source(data, origin)) as store:
        held = store.held
        store.check()
        def save(path):
            store.create(path, own[path])
        save(active + '/intent.json')
        # Exact immutable plan, original directories and byte objects survive
        # independently of target replacement and journal cleanup.
        save(archive + '/plan.json')
        for path in sorted(p for p in own if p.startswith(archive + '/objects/')):
            save(path)
        save(archive + '/manifest.json')
        for path in layout['staged'].values():
            save(path)
        save(active + '/prepared.json')
        _source(data, origin)
        _authorize(authority, request)
        _source(data, origin)
        store.check()
        store.before_create = lambda path: _source(data, origin) if path == active + '/committing.json' else None
        save(active + '/committing.json')
        store.before_mutation = lambda: _source(data, origin)
        for index, path in enumerate(changes):
            _source(data, origin)
            if path in target:
                store.publish(layout['staged'][path], path, target[path])
            else:
                store.remove(path)
            save(active + '/effects/' + str(index) + '.json')
        actual = {path: store.read(path) for path in target}
        require(actual == target and validate_project(actual)[1] == expected_target_root,
                'restore_actual_target_conflict', exit_code=6)
        store.check()
        save(archive + '/completed.json')
        for index, move in enumerate(layout['binding']['archive_moves']):
            store.archive(move['source'], move['target'])
            save(active + '/archived/' + str(index) + '.json')
        save(layout['terminal_barrier'])
        store.archive(active, terminal)
        # No normative publication remains. Source loss cannot invalidate a
        # proven full target or prevent release of its durable terminal gate.
        store.before_mutation = lambda: None
        store.remove(layout['terminal_barrier'])
        require(not held._files.journal_entries(), 'restore_remaining_journals', exit_code=5)
        store.check()
        return RestoreCompletion._create({**layout['completed'], 'audit_path': archive + '/completed.json',
            'recovery_required': False, 'normative_paths': changes})
