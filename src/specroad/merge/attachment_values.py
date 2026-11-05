"""Immutable binary candidates and original conflict hash observations."""
from dataclasses import dataclass

from ..model.errors import ModelError


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
