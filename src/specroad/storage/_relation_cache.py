"""Optional existing adjacency hints; no cache creation, repair or authority.

Only a recorded distribution can reuse these entries. Original project inputs
are already loaded and validated before this adapter runs. Cache failures are
local misses; fresh-source failures stay outside this fallback boundary.
"""

import os

from ..graph.indices import RelationIndex
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from ..runtime.distribution import BuildMetadataError
from ..runtime.resource_profiles import profile_targets
from ..security import SafetyViolation
from ..security.resource_access import opened_resource
from .json_syntax import parse_json_object
from ._relation_cache_values import _FORMAT, _POLICY, _binding, encode_cache, _CacheShape


CACHE_PATH = ".specroad/cache/relation-index-v1.json"


def cache_options(mode, maximum):
    if type(mode) is not str or mode not in ("off", "read"):
        raise ModelError("invalid_relation_cache_mode")
    if maximum is None:
        maximum = profile_targets("constrained", source="default")[
            "effective_budgets"]["persistent_cache_read"]["value"]
    if type(maximum) is not int or maximum < 0:
        raise ModelError("invalid_relation_cache_read_budget")
    return maximum


def _read_cache(boundary, maximum, maximum_marks):
    with opened_resource(boundary, CACHE_PATH) as (descriptor, metadata):
        if metadata.st_size > maximum:
            return None
        shape = _CacheShape(maximum_marks)
        # Grow with actual bytes, not one retained object per short read or an
        # up-front allocation sized from an untrusted file's declared extent.
        data = bytearray()
        remaining = metadata.st_size
        while remaining:
            part = os.read(descriptor, min(65536, remaining))
            if not part:
                return None
            shape.feed(part)
            data.extend(part)
            remaining -= len(part)
        shape.finish()
        # Descriptor size/signature and entry identity are rechecked on exit.
        raw = bytes(data)
    return raw


def read_cache(source, snapshot, references, maximum):
    """Ignore unusable optional work; never retry or touch original input here."""
    if maximum == 0:
        return None
    try:
        binding = _binding(snapshot)
        if binding is None:
            return None
        # Generous linear allowance for this envelope, every input dependency,
        # both source tables and exactly two occurrences of each relation ID.
        # Exceeding it skips optional work; the full normative graph is retained.
        maximum_marks = 256 + 32 * len(references.sources) + 8 * len(references.relations)
        raw = _read_cache(source.boundary, maximum, maximum_marks)
        if raw is None:
            return None
        entry = parse_json_object(raw, path=CACHE_PATH)
        if (set(entry) != {"format", "binding", "order", "order_sha256"}
                or entry["format"] != _FORMAT
                or canonical_json_sha256(entry["binding"]) != canonical_json_sha256(binding)
                or entry["order_sha256"] != canonical_json_sha256(entry["order"])):
            return None
        return RelationIndex.from_order(references, entry["order"])
    except (OSError, SafetyViolation, ModelError, BuildMetadataError, MemoryError, RecursionError):
        return None
