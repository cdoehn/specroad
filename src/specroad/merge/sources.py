"""Three complete owned sources; source acquisition is shared and read-only."""
from dataclasses import dataclass

from ..snapshots import SourceRequest, SourceSnapshot
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError


@dataclass(frozen=True)
class MergeSources:
    base: SourceSnapshot
    ours: SourceSnapshot
    theirs: SourceSnapshot

    def __post_init__(self):
        rows = (self.base, self.ours, self.theirs)
        if any(type(row) is not SourceSnapshot for row in rows):
            raise ModelError('merge_source_snapshot_required')
        if len({row.project_id for row in rows}) != 1:
            raise ModelError('merge_project_mismatch')
        if len({row.schema_version for row in rows}) != 1:
            raise ModelError('merge_schema_migration_required')

    @property
    def binding(self):
        return {name: getattr(self, name).binding for name in ('base', 'ours', 'theirs')}

    @property
    def sha256(self):
        return canonical_json_sha256(self.binding)


def load_merge_sources(base, ours, theirs):
    """Load three complete native sources without planning or publishing a merge."""
    result = MergeSources(*(SourceSnapshot(request) for request in (base, ours, theirs)))
    for source in (result.base, result.ours, result.theirs):
        source.verify_current()
    return result
