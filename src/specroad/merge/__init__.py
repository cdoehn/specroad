"""Read-only prerequisites for the planned semantic three-way merge."""
from .sources import MergeSources, SourceRequest, SourceSnapshot, load_merge_sources
from .inventory import MergeInventory, build_merge_inventory, read_merge_inventory
from .fields import FieldValue, FieldConflict, FieldMergeResult, merge_fields
from .field_values import CollectionConflict
from .attachments import AttachmentConflict, AttachmentMergeResult, merge_attachments

__all__ = ['MergeSources', 'SourceRequest', 'SourceSnapshot', 'load_merge_sources',
           'MergeInventory', 'build_merge_inventory', 'read_merge_inventory',
           'FieldValue', 'FieldConflict', 'FieldMergeResult', 'merge_fields', 'CollectionConflict',
           'AttachmentConflict', 'AttachmentMergeResult', 'merge_attachments',
           'merge_relations', 'inspect_merge_identities', 'RelationMergeResult',
           'inspect_merge_lifecycle', 'LifecycleMergeResult']
from .relations import merge_relations, inspect_merge_identities, RelationMergeResult
from .lifecycle import inspect_merge_lifecycle, LifecycleMergeResult

from .conflicts import MergeConflicts, build_merge_conflicts, parse_merge_conflicts, read_merge_conflicts
__all__ += ['MergeConflicts', 'build_merge_conflicts', 'parse_merge_conflicts', 'read_merge_conflicts']

from .resolutions import (MergeResolutions, parse_merge_resolutions, parse_resolution_plan,
                          parse_resolution_value, read_merge_resolutions, resolve_merge_conflict)
__all__ += ['MergeResolutions', 'parse_merge_resolutions', 'parse_resolution_plan',
            'parse_resolution_value', 'read_merge_resolutions', 'resolve_merge_conflict']
