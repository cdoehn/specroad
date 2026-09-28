"""Fresh descriptor-relative observations, with no authority or write capability.

An explicit rights observer is shared by both calling phases. This module does
not acquire locks, evaluate a plan, invoke an authorizer or publish files.
"""
from hashlib import sha256
import os
import stat
from ..model.paths import CURRENT_JSON_CLASSES, PathClass
from ..validation import ModelDocument
from ..security import ProjectBoundary
from ..security.resource_access import opened_resource
from ..storage.byte_binding import fingerprint_reader
from ..storage.project import ProjectSource
from ..storage.resource_discovery import current_json_paths
from .publication_values import PublicationCheckError

def _stamp(info):
    # Timestamps do not establish content identity. Hash every byte on each pass.
    return {'device': str(info.st_dev), 'inode': str(info.st_ino),
            'mode': stat.S_IMODE(info.st_mode), 'uid': str(info.st_uid),
            'gid': str(info.st_gid), 'links': None if stat.S_ISDIR(info.st_mode) else info.st_nlink}


def _root(model):
    root = model.binding.source_root
    info = os.lstat(root)
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise PublicationCheckError('unsafe_publication_root', exit_code=7)
    if (info.st_dev, info.st_ino) != model.binding.root_identity:
        raise PublicationCheckError('publication_root_changed')
    boundary = ProjectBoundary(root)
    if boundary.read_bytes('specroad.json') != model.configuration_bytes:
        raise PublicationCheckError('publication_configuration_changed', path='specroad.json')
    source = ProjectSource(root, expected_project_id=model.binding.project_id)
    if (str(source.boundary.root) != root or
            source.boundary._root_identity != model.binding.root_identity):
        raise PublicationCheckError('publication_root_changed')
    if source.configuration_bytes != model.configuration_bytes:
        raise PublicationCheckError('publication_configuration_changed', path='specroad.json')
    return source


def _parent(source, path, *, check_rights, writable=True):
    parent = path.rsplit('/', 1)[0] if '/' in path else ''
    parts = parent.split('/') if parent else []
    observed = {}
    deepest = ''
    fd = os.open(source.boundary.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        root_info = os.fstat(fd)
        if (root_info.st_dev, root_info.st_ino) != source.boundary._root_identity:
            raise PublicationCheckError('publication_root_changed')
        observed[''] = _stamp(root_info)
        if not parts and writable:
            check_rights(fd, '')
        for index in range(len(parts)):
            relative = '/'.join(parts[:index + 1])
            try:
                with opened_resource(source.boundary, relative, directory=True) as (directory, info):
                    observed[relative] = _stamp(info)
            except FileNotFoundError:
                # Absence belongs to the observation; no mkdir or write probe.
                for j in range(index, len(parts)):
                    observed['/'.join(parts[:j + 1])] = None
                break
            deepest = relative
        if writable and parts:
            if deepest:
                with opened_resource(source.boundary, deepest, directory=True) as (directory, info):
                    if _stamp(info) != observed[deepest]:
                        raise PublicationCheckError('publication_parent_changed', path=deepest)
                    check_rights(directory, deepest)
            else:
                check_rights(fd, '')
    finally:
        os.close(fd)
    return observed


def _package_bindings(source, model, package_files):
    if type(package_files) not in (tuple, list) or any(type(d) is not ModelDocument for d in package_files):
        raise PublicationCheckError('explicit_package_file_bindings_required', exit_code=2)
    files = tuple(ModelDocument(d.path,d.content) for d in package_files)
    names = [d.path for d in files]
    if len(set(p.casefold() for p in names)) != len(names) or set(names) & set(model.source_files):
        raise PublicationCheckError('duplicate_publication_package_path', exit_code=2)
    if any(source.classify(d.path) not in (PathClass.PROFILE, PathClass.RULE) for d in files):
        raise PublicationCheckError('publication_package_path_unmanaged', exit_code=7)
    expected = sorted(sha256(p.source_bytes).hexdigest() for p in model.language_packages)
    actual = sorted(sha256(d.content).hexdigest() for d in files)
    if actual != expected:
        raise PublicationCheckError('live_language_package_bindings_required', exit_code=2)
    return files


def observe_publication_files(source, model, request, package_files=(), *, check_rights):
    source.check_current()
    files = {**model.source_files, **{d.path:d.content for d in package_files}}
    expected_json = tuple(sorted(p for p in files if source.classify(p) in CURRENT_JSON_CLASSES))
    if current_json_paths(source) != expected_json:
        raise PublicationCheckError('publication_inventory_changed')
    states, parents = {}, {}
    for path, expected in sorted(files.items()):
        parents.update(_parent(source, path, check_rights=check_rights, writable=False))
        with opened_resource(source.boundary, path) as (fd, info):
            if info.st_nlink != 1:
                raise PublicationCheckError('linked_publication_input', path=path, exit_code=7)
            actual = fingerprint_reader(lambda n: os.read(fd, n), info.st_size)
            if actual.size != len(expected) or actual.sha256 != sha256(expected).hexdigest():
                raise PublicationCheckError('publication_base_changed', path=path)
            states[path] = {**_stamp(info), 'size': actual.size, 'sha256': actual.sha256}
    for document in request.documents:
        path = document.path
        source.require_write_target(path)
        parents.update(_parent(source, path, check_rights=check_rights))
        if path not in files:
            try:
                with opened_resource(source.boundary, path):
                    pass
            except FileNotFoundError:
                pass
            else:
                raise PublicationCheckError('publication_create_target_exists', path=path)
    if current_json_paths(source) != expected_json:
        raise PublicationCheckError('publication_inventory_changed')
    source.check_current()
    return {'files': states, 'parents': parents,
            'root': _stamp(os.lstat(source.boundary.root))}


