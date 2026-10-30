"""Read an existing private Work chain without treating it as authorization.

The local root binding anchors the read under the existing native mutex. All
continuations still enter an installed adapter with current host authority and
native project gates. Neither root.json nor a checkpoint authenticates an actor.
"""
from pathlib import Path

from ..model.canonical import canonical_json_bytes
from ..recovery._inventory import boundary, read_source
from ..recovery.values import RestorePlan, require, guarded, persisted_contract
from ..storage.json_syntax import parse_json_object
from ._data_contract import _object, _hash
from ._root_lock import _HeldWorkRoot
from .checkpoints import CheckpointStore, _reference
from .packages import _capture, _decode
from .restore_execution import _build
from .root import WorkDirectory, _path
from ._public_errors import work_errors


def protected_paths(initial):
    value = initial.as_dict()
    require(value['command_id'] == 'recover.restore', 'work_command_adapter_unavailable', exit_code=2)
    options = value['normalized_arguments']['options']
    paths = {options['--project']}
    if '--from' in options:
        paths.update(options[key] for key in ('--source-root', '--output-root'))
    else:
        from .manifest import _bytes
        plan = RestorePlan(_bytes(value['plan_binding']['plan_source'], initial.objects))
        paths.update((plan.data['source']['root'], options['--plan-root']))
        if '--selection-root' in options:
            paths.add(options['--selection-root'])
    return tuple(sorted(paths))


@guarded
@persisted_contract
@work_errors
def open_restore_work(path, *, registry):
    """Bind the complete retained chain; no owner takeover or file creation."""
    path = _path(path)
    observed = boundary(path)
    raw = read_source(observed, 'root.json')
    root = parse_json_object(raw)
    _object(root, ('format_version', 'work_id', 'initial_checkpoint_sha256', 'device', 'inode'))
    _hash(root['initial_checkpoint_sha256'])
    require(root['format_version'] == 'work-root-v1' and canonical_json_bytes(root) == raw,
            'work_root_binding_invalid')
    # Bootstrap is inspection-only, before we know the saved protected roots.
    # The native lease validates private ownership, inode and every file type.
    location = object.__new__(WorkDirectory)
    location._work_id = root['work_id']
    location._initial_hash = root['initial_checkpoint_sha256']
    location._protected = location._reserved = ()
    location._requested = location._path = path
    location._temporary = None
    location._allocated_identity = observed._root_identity
    bootstrap = object.__new__(CheckpointStore)
    bootstrap._location = location
    build = _build()
    with _HeldWorkRoot(location, path, exclusive=False, inspection=True) as held:
        require(held._read('root.json')[0] == raw, 'work_root_binding_changed', exit_code=6)
        pointer = bootstrap._pointer(held)
        require(pointer is not None, 'restore_published_work_required', exit_code=5)
        payloads = _capture(bootstrap, held, pointer)
        current = bootstrap._pointer_value(pointer[0])
        records = [parse_json_object(content) for name, content in payloads.items()
                   if name.startswith('checkpoints/')]
        origins = [record for record in records if record['parent'] is None]
        require(len(origins) == 1, 'work_initial_checkpoint_missing')
        metadata = {'format_version': 'work-package-v1', 'package_kind': 'work',
            **{key: current[key] for key in ('work_id', 'checkpoint_generation', 'checkpoint_sha256')},
            'initial_manifest': origins[0]['manifest'],
            'initial_checkpoint_sha256': root['initial_checkpoint_sha256'], 'tool_build': build}
        chain = _decode(metadata, payloads, registry, build)
        initial = chain[0]
        require(initial.as_dict()['command_id'] == 'recover.restore',
                'work_command_adapter_unavailable', exit_code=2)
        checked_location = WorkDirectory(initial, protected_roots=(),
            protected_paths=protected_paths(initial), directory=path)
        checked_location._outside(path)
        checked_location._allocated_identity = observed._root_identity
        checked_location._path = path
        store = CheckpointStore(checked_location, initial)
        require(store._read_chain(held, pointer[0]).raw == chain[-1].raw
                and store._pointer(held) == pointer, 'work_checkpoint_changed', exit_code=6)
        held.check()
    return store
