"""Pure JSON field merging, before identity, metadata and target-validation gates.

The caller supplies three present JSON values of the same logical resource.
Missing object members are distinct from JSON null; a missing RESOURCE is not
an input to this function. Results neither change the source inventory nor
authorize deletion/publication. Concurrent arrays await schema-aware merging.
"""
from .field_values import FieldValue, FieldConflict, FieldMergeResult
from ._field_merge import merge_owned


__all__ = ['FieldValue', 'FieldConflict', 'FieldMergeResult', 'merge_fields']


def merge_fields(base, ours, theirs):
    """Recursively combine independent fields and JSON-equivalent target values.

    No profile or lifecycle decision is implied. Even a conflict-free value
    still requires the later resource/history, invariant and writer gates.
    """
    # Validate and detach ALL inputs, even a side an equality shortcut ignores.
    values = [FieldValue._create(value).value for value in (base, ours, theirs)]
    target, conflicts = merge_owned(*values)
    return FieldMergeResult._create(target, conflicts)
