"""Read-only binary candidates from actual bytes, never deletion by absence."""
from dataclasses import dataclass
from hashlib import sha256

from ..model.errors import ModelError
from ..model.paths import project_path


@dataclass(frozen=True)
class AttachmentConflict:
    path: str
    kind: str
    base_sha256: str | None
    ours_sha256: str | None
    theirs_sha256: str | None


@dataclass(frozen=True, init=False, eq=False)
class AttachmentMergeResult:
    _files: tuple
    conflicts: tuple

    @classmethod
    def _create(cls, files, conflicts):
        result = object.__new__(cls)
        object.__setattr__(result, '_files', () if conflicts else tuple(sorted(files.items())))
        object.__setattr__(result, 'conflicts', tuple(conflicts))
        return result

    @property
    def merged(self):
        return not self.conflicts

    @property
    def files(self):
        if self.conflicts:
            raise ModelError('unresolved_attachment_merge')
        return dict(self._files)

    @property
    def ready(self):
        return False

    @property
    def write_authorized(self):
        return False

    def __bool__(self):
        raise TypeError('An attachment candidate is not a merge plan or write authority')


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


def merge_attachments(base, ours, theirs, *, removed_ours=(), removed_theirs=()):
    """Compare complete qualified attachment maps; never read or write a path."""
    base, ours, theirs = (_source(value) for value in (base, ours, theirs))
    _check_paths(set(base) | set(ours) | set(theirs))
    removed_ours = _removals(removed_ours, base, ours)
    removed_theirs = _removals(removed_theirs, base, theirs)
    hashes = [{path: sha256(raw).hexdigest() for path, raw in source.items()} for source in (base, ours, theirs)]
    conflicts, files = [], {}
    for path in sorted(set(base) | set(ours) | set(theirs)):
        old, left, right = (source.get(path) for source in (base, ours, theirs))
        kind = None
        if old is not None and ((left is None and path not in removed_ours) or (right is None and path not in removed_theirs)):
            kind = 'attachment_absence_unproven'
        elif left == right:
            target = left
        elif old == left:
            target = right
        elif old == right:
            target = left
        else:
            kind = 'attachment_remove_edit' if left is None or right is None else 'attachment_binary_change'
        if kind is not None:
            conflicts.append(AttachmentConflict(path, kind, *(mapping.get(path) for mapping in hashes)))
        elif target is not None:
            files[path] = target
    return AttachmentMergeResult._create(files, conflicts)
