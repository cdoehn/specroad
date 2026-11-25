"""Fork a checked Work continuation into its own native, durable Work store.

The old directory is an input, never a writable recovery target. Existing
adapters still verify current source, unit evidence and real transport results.
"""
from hashlib import sha256
from uuid import uuid4

from ..force_operations import current, permit
from ..security import ProjectBoundary
from .packages import _export_held, restore_work_package
from .resume import _runtime_build


def own_attempt(store):
    call = current()
    if call is None or not call.decisions.request.requested:
        return store
    with store._location.inspect_checkpoint() as held:
        from ._root_lock import WorkBindingViolation
        selected = dict(call.owners).get('work-lock.json')
        actual = None if held._owner is None else sha256(held._owner[0]).hexdigest()
        if selected is not None and selected != actual:
            raise WorkBindingViolation('The explicitly selected Work owner changed')
        if held._owner is None:
            return store
        from ._root_lock import WorkBindingViolation
        from ..storage.json_syntax import parse_json_object
        from ..changes.lock_values import OwnerIdentity
        from ..changes._lock_process import LinuxOwnerProbe
        from ..changes._lock_owner_policy import observe_owner
        from types import SimpleNamespace
        from ..force_operations import selected_owner
        owner = parse_json_object(held._owner[0])
        try:
            state = observe_owner(SimpleNamespace(owner=OwnerIdentity(*(owner[k] for k in
                ('host_id', 'process_id', 'process_start_id')))), LinuxOwnerProbe())
        except (KeyError, ValueError, TypeError):
            state = 'unknown'
        if state in ('alive', 'foreign', 'unverifiable', 'unknown') and not selected_owner('work-lock.json', held._owner[0]):
            raise WorkBindingViolation('An explicit observed concurrent Work owner is required')
        raw, pointer, previous = _export_held(store, held, _runtime_build())
        target = held.path.parent / (held.path.name + '.force-' + str(uuid4()))
        permit(False, gate='work_marker:retained_owner', subject=str(held.path),
            observed={'checkpoint_sha256': previous.as_dict()['checkpoint_sha256'],
                      'owner_sha256': sha256(held._owner[0]).hexdigest()},
            requested={'work_dir': str(target), 'checkpoint_sha256': previous.as_dict()['checkpoint_sha256']},
            effect='preserve_original_work_and_resume_separate_attempt')
        def recheck():
            held.check()
            if store._pointer(held) != pointer or store._read_chain(held, pointer[0]).raw != previous.raw:
                from ._root_lock import WorkBindingViolation
                raise WorkBindingViolation('Original Force Work changed')
        clone = restore_work_package(raw, expected_sha256=sha256(raw).hexdigest(),
            registry=store._registry, protected_roots=(*store._location._protected, ProjectBoundary(held.path)),
            directory=target, _recheck_input=recheck)
        recheck()
        return clone
