"""Central K.3 arithmetic, selected only by source-bound merge preparation.

No caller-selected revision, wall clock, registry callback or write authority.
The regular change-metadata-v1 mechanism remains separate.
"""
from ..model.audit import artifact_audit, actor as read_actor
from ..model.canonical import canonical_json_bytes as jcs
from .metadata_time import _parts, _successor
from .metadata_values import MetadataError

AUDIT = frozenset(('revision', 'created_at', 'created_by', 'updated_at', 'updated_by'))
POLICY = 'merge-metadata-v1'


def merge_creation(values):
    present = [value for value in values if value is not None]
    if not present:
        raise MetadataError('merge_metadata_original_required')
    for value in present:
        artifact_audit(value)
    origins = [jcs({name: value[name] for name in ('created_at', 'created_by')}) for value in present]
    if len(set(origins)) != 1:
        raise MetadataError('merge_creation_origin_conflict')
    return {name: present[0][name] for name in ('created_at', 'created_by')}


def combined_merge_audit(base, ours, theirs, *, resolution_actor=None):
    """K.3: max(side revisions)+1; max(all available update times)+1us."""
    creation = merge_creation((base, ours, theirs))
    sides = [value for value in (ours, theirs) if value is not None]
    if not sides:
        raise MetadataError('merge_metadata_side_required')
    revision = max(artifact_audit(value).revision.value for value in sides) + 1
    jcs(revision)  # Reject a revision that cannot be represented losslessly.
    times = [value['updated_at'] for value in (base, ours, theirs) if value is not None]
    parts = [_parts(value, '/updated_at') for value in times]
    width = max(len(fraction) for _, fraction in parts)
    latest = max(range(len(times)), key=lambda i: (parts[i][0], parts[i][1].ljust(width, '0')))
    actor = {'actor_type': 'tool', 'actor_id': 'specroad-merge'} if resolution_actor is None else read_actor(resolution_actor).as_fields()
    return {**creation, 'revision': revision, 'updated_at': _successor(times[latest]), 'updated_by': actor}
