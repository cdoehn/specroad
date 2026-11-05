"""Pure JSON field merging, before identity, metadata and target-validation gates.

The caller supplies three present JSON values of the same logical resource.
Missing object members are distinct from JSON null; a missing RESOURCE is not
an input to this function. Results neither change the source inventory nor
authorize deletion/publication. Only an explicit built-in schema ID enables
declared collection semantics; otherwise concurrent arrays remain unresolved.
"""
from .field_values import FieldValue, FieldConflict, FieldMergeResult
from ._field_merge import merge_owned


__all__ = ['FieldValue', 'FieldConflict', 'FieldMergeResult', 'merge_fields']


def merge_fields(base, ours, theirs, *, schema_id=None):
    """Recursively combine independent fields and JSON-equivalent target values.

    No profile or lifecycle decision is implied. Even a conflict-free value
    still requires the later resource/history, invariant and writer gates.
    """
    # Validate and detach ALL inputs, even a side an equality shortcut ignores.
    values = [FieldValue._create(value).value for value in (base, ours, theirs)]
    resource, rules = None, None
    if schema_id is not None:
        from ..model.schema_catalog import SchemaCatalog
        from .schema_collections import collection_rules, check_collections
        resource = SchemaCatalog().get(schema_id)
        rules = collection_rules(resource.schema)
        for value in values:
            resource.validate(value)
            check_collections(value, rules)
    target, conflicts = merge_owned(*values, rules=rules)
    if resource is not None and not conflicts:
        from ..model.errors import ModelError
        try:
            resource.validate(target)
        except ModelError:
            conflicts = (FieldConflict('', 'schema_invalid_combination',
                *(FieldValue._create(value) for value in values)),)
    return FieldMergeResult._create(target, conflicts)
