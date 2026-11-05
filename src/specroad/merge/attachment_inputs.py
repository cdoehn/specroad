"""Strict byte-map, path and explicit-removal boundaries; no filesystem I/O."""
from ..model.errors import ModelError
from ..model.paths import project_path


def _path(path):
    if type(path) is not str or project_path(path) != path or not path.startswith('attachments/'):
        raise ModelError('invalid_merge_attachment_path')
    return path


def _source(value):
    if type(value) is not dict:
        raise ModelError('invalid_merge_attachment_source')
    result = {}
    for path, content in value.items():
        _path(path)
        if type(content) is not bytes:
            raise ModelError('invalid_merge_attachment_bytes')
        result[path] = content
    return result


def _removals(value, base, side):
    if type(value) not in (tuple, list) or any(type(path) is not str for path in value):
        raise ModelError('invalid_attachment_removal')
    if len(set(value)) != len(value):
        raise ModelError('invalid_attachment_removal')
    result = set(value)
    for path in result:
        _path(path)
        if path not in base or path in side:
            raise ModelError('invalid_attachment_removal')
    return result


def _check_paths(paths):
    """Reject aliases at every component and file/descendant collisions."""
    folded_files = {path.casefold() for path in paths}
    prefixes = {}
    for path in sorted(paths):
        parts = path.split('/')
        for index in range(1, len(parts)+1):
            prefix = '/'.join(parts[:index]); folded = prefix.casefold()
            if (folded in prefixes and prefixes[folded] != prefix) or (index < len(parts) and folded in folded_files):
                raise ModelError('merge_attachment_path_collision')
            prefixes[folded] = prefix
