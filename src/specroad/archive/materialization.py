"""Read-only Baseline views and explicitly isolated native snapshot restoration.

The supported whole-project snapshot is reconstructed from its own bytes. No
Git, current-project fallback, release approval or historical validation claim.
Native restoration creates only a new root under a private external parent;
failures retain their actual partial output and never replace an existing root.
"""
from hashlib import sha256
import os
from pathlib import Path
import unicodedata

from ..model.canonical import canonical_json_bytes
from ..model.configuration import ProjectConfiguration
from ..model.errors import ModelError
from ..model.paths import project_path
from ..model.record_schemas import validate_record_fields
from ..model.semantic_configuration import semantic_configuration
from ..security import ProjectBoundary, SafetyViolation
from ..security import paths as guards
from ..storage.json_syntax import parse_json_object
from .objects import ObjectReference, SnapshotObject, read_snapshot_object
from .verification import verify_baseline_objects, verify_baseline_snapshot

_VALUES = frozenset(('semantic_configuration', 'effective_profile', 'model_manifest'))


def _record(boundary, raw):
    if type(boundary) is not ProjectBoundary:
        raise ModelError('snapshot_object_boundary_required')
    if type(raw) is not bytes:
        raise ModelError('baseline_record_bytes_required')
    value = parse_json_object(raw)
    validate_record_fields(value, expected_type='baseline')
    return value


def show_baseline_snapshot(boundary, baseline_record):
    """Return stored data and a freshly computed status, without writing.

    A well-formed record can be shown with a failed integrity check. Malformed
    records, unsafe paths and host I/O failures retain their normal exceptions.
    No prior observation is accepted as a substitute for fresh verification.
    """
    record = _record(boundary, baseline_record)
    try:
        checked = verify_baseline_snapshot(boundary, baseline_record)
    except ModelError as error:
        integrity = {'status': 'failed', 'snapshot_integrity_verified': False,
                     'diagnostics': [error.diagnostic()], 'verification': None}
    else:
        integrity = {'status': 'verified', 'snapshot_integrity_verified': True,
                     'diagnostics': [], 'verification': checked}
    return {'format_version': 'baseline-show-v1', 'baseline': record,
            'integrity': integrity}


def _snapshot(boundary, raw, *, default_locale, generated_path):
    record = _record(boundary, raw)
    checked = verify_baseline_snapshot(boundary, raw)
    objects = {}
    for row in record['manifest']:
        reference = ObjectReference(row['sha256'], row['size'])
        if reference.path not in objects:
            objects[reference.path] = SnapshotObject(read_snapshot_object(boundary, reference))
    if verify_baseline_objects(raw, tuple(objects.values())) != checked:
        raise ModelError('baseline_snapshot_changed')
    files, semantic = {}, None
    for row in record['manifest']:
        content = objects[row['object_path']].content
        if row['role'] == 'semantic_configuration':
            semantic = content
        elif row['role'] not in _VALUES:
            path = project_path(row['source_path'])
            if path in files:
                raise ModelError('baseline_materialization_path_collision', path=path)
            files[path] = content
    configuration = ProjectConfiguration({**parse_json_object(semantic),
        'default_locale': default_locale, 'generated_path': generated_path})
    if canonical_json_bytes(semantic_configuration(configuration)) != semantic:
        raise ModelError('baseline_materialization_configuration_changed')
    files['specroad.json'] = canonical_json_bytes(configuration.data)
    # Collect every directory prefix; files and directories share one namespace.
    directories = {'/'.join(name.split('/')[:i]) for name in files
                   for i in range(1, len(name.split('/')))}
    aliases = {}
    for name in sorted(set(files) | directories):
        project_path(name)
        key = unicodedata.normalize('NFC', name).casefold()
        if key in aliases or name in files and name in directories:
            raise ModelError('baseline_materialization_path_collision', path=name)
        aliases[key] = name
    return record, objects, files, directories, checked


def _external_parent(target, protected):
    parent = target.parent
    if parent.resolve(strict=True) != parent:
        raise SafetyViolation('A canonical external parent is required')
    info = parent.lstat()
    guards._regular(info, directory=True)
    if not hasattr(os, 'getuid') or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise SafetyViolation('The materialization parent must be private and owned')
    for boundary in protected:
        boundary._check_root()
        if target.is_relative_to(boundary.root) or boundary.root.is_relative_to(target):
            raise SafetyViolation('Materialization and protected paths overlap')
    for ancestor in (parent, *parent.parents):
        try:
            (ancestor / 'specroad.json').lstat()
        except FileNotFoundError:
            continue
        raise SafetyViolation('Materialization cannot nest inside a project')


def _verify_materialized(boundary, raw, record, objects):
    """Rebuild the same root from the output's actual independent file bytes."""
    current = []
    for row in record['manifest']:
        role = row['role']
        if role == 'semantic_configuration':
            configuration = ProjectConfiguration(parse_json_object(boundary.read_bytes('specroad.json')))
            content = canonical_json_bytes(semantic_configuration(configuration))
        elif role in _VALUES:
            content = objects[row['object_path']].content
        else:
            content = boundary.read_bytes(row['source_path'])
        current.append(SnapshotObject(content))
    return verify_baseline_objects(raw, tuple({o.reference.path: o for o in current}.values()))


def materialize_baseline_snapshot(boundary, baseline_record, destination, *,
                                  default_locale, generated_path, protected_roots):
    """Restore to a missing native Linux destination under a private parent.

    Supply every other protected project/input/output root. The archive boundary
    is protected automatically. Locale/output location are explicit operational
    choices; no missing historical semantic value comes from the current tree.
    Configuration is written last. Interrupted output is retained, not resumed
    or silently reused. The resulting project is not an authorized publication.
    """
    from ..changes._lock_files import LockFiles
    from ..changes._staging_files import _write_new
    from ..authoring._bootstrap_io import metadata, verify_tree

    if (type(protected_roots) is not tuple or not protected_roots or
            any(type(p) is not ProjectBoundary for p in protected_roots)):
        raise ModelError('baseline_materialization_protected_roots_required')
    _record(boundary, baseline_record)
    value = os.fspath(destination)
    if type(value) is not str or not value.startswith('/') or value.startswith('//'):
        raise SafetyViolation('An absolute new materialization path is required')
    project_path(value[1:])
    target = Path(value)
    protected = (boundary, *protected_roots)
    _external_parent(target, protected)
    record, objects, files, directories, checked = _snapshot(boundary, baseline_record,
        default_locale=default_locale, generated_path=generated_path)
    with LockFiles(target.parent) as parent:
        parent.acquire()
        _external_parent(target, protected)
        # mkdir is exclusive even for an empty directory or a dangling link.
        os.mkdir(target.name, mode=0o700, dir_fd=parent.root_fd)
        expected = guards._identity(os.stat(target.name, dir_fd=parent.root_fd,
                                           follow_symlinks=False))
        os.fsync(parent.root_fd)
        with LockFiles(target) as held:
            held.acquire()
            inventory = {}

            def current():
                parent.require_held(); held.require_held()
                _external_parent(target, protected)
                now = os.stat(target.name, dir_fd=parent.root_fd, follow_symlinks=False)
                guards._regular(now, directory=True)
                if (guards._identity(now) != expected or
                        held.boundary._root_identity != expected):
                    raise SafetyViolation('Materialization root changed')
                if now.st_uid != os.getuid() or now.st_mode & 0o077:
                    raise SafetyViolation('Materialization root is no longer private and owned')

            current()
            for path in sorted(directories, key=lambda p: (p.count('/'), p)):
                parts = tuple(path.split('/'))
                with held.directory(parts, create=True) as fd:
                    current(); inventory[path] = metadata(os.fstat(fd))
            for path in [*sorted(set(files) - {'specroad.json'}), 'specroad.json']:
                if path == 'specroad.json':
                    verify_tree(held.root_fd, inventory)
                    for item in objects.values():
                        if read_snapshot_object(boundary, item.reference) != item.content:
                            raise ModelError('baseline_snapshot_changed')
                parts = path.split('/')
                with held.directory(tuple(parts[:-1])) as fd:
                    current(); _write_new(fd, parts[-1], files[path])
                    inventory[path] = metadata(os.stat(parts[-1], dir_fd=fd,
                                                       follow_symlinks=False), files[path])
            current(); verify_tree(held.root_fd, inventory)
            if _verify_materialized(held.boundary, baseline_record, record, objects) != checked:
                raise ModelError('baseline_materialization_root_mismatch')
            current(); verify_tree(held.root_fd, inventory)
    return {'format_version': 'baseline-materialization-v1', 'project_root': str(target),
        'baseline_id': record['id'], 'model_root_sha256': checked['model_root_sha256'],
        'configuration_hash': checked['configuration_hash'], 'profile_sha256': checked['profile_sha256'],
        'files': [{'path': p, 'size': len(raw), 'sha256': sha256(raw).hexdigest()}
                  for p, raw in sorted(files.items())],
        'operational_configuration': {'default_locale': default_locale, 'generated_path': generated_path},
        'snapshot_integrity_verified': True, 'materialization_complete': True,
        'validation_scope': 'verified_baseline_snapshot_and_exact_materialized_bytes',
        'atomic_publication': False, 'full_validation_passed': False,
        'write_authorized': False, 'release_authorized': False}
