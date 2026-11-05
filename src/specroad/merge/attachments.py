"""Read-only binary candidates from actual bytes, never deletion by absence."""
from hashlib import sha256

from .attachment_values import AttachmentConflict, AttachmentMergeResult
from .attachment_inputs import _source, _removals, _check_paths


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
