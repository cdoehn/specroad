"""Optional existing adjacency hints; no cache creation, repair or authority.

Only a recorded distribution can reuse these entries. Original project inputs
are already loaded and validated before this adapter runs. Cache failures are
local misses; fresh-source failures stay outside this fallback boundary.
"""

import os
import sys

from .. import _build
from .._metadata import MODEL_SCHEMA_VERSION, __version__
from ..graph.indices import RelationIndex
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..runtime.distribution import BuildMetadataError, distribution_identity
from ..runtime.resource_profiles import profile_targets
from ..security import SafetyViolation
from ..security.resource_access import opened_resource
from .json_syntax import parse_json_object


CACHE_PATH = ".specroad/cache/relation-index-v1.json"
_FORMAT = "specroad-relation-index-cache-v1"
_POLICY = "canonical-relations-and-view-order-v1"


def cache_options(mode, maximum):
    if type(mode) is not str or mode not in ("off", "read"):
        raise ModelError("invalid_relation_cache_mode")
    if maximum is None:
        maximum = profile_targets("constrained", source="default")[
            "effective_budgets"]["persistent_cache_read"]["value"]
    if type(maximum) is not int or maximum < 0:
        raise ModelError("invalid_relation_cache_read_budget")
    return maximum


def _binding(snapshot):
    identity = distribution_identity(_build.BUILD_METADATA, loader=__loader__)
    if identity["build_identity_status"] != "recorded":
        return None
    binding = snapshot.binding
    return {
        "tool": {"version": __version__, "build_sha256": identity["build_sha256"],
                 "hash_algorithm": identity["build_hash_algorithm"]},
        "runtime": {"implementation": sys.implementation.name,
                    "version": list(sys.version_info[:3]),
                    "cache_tag": sys.implementation.cache_tag, "platform": sys.platform},
        "schema_version": MODEL_SCHEMA_VERSION,
        "policy": _POLICY,
        "dependencies": {
            "project_id": binding.project_id,
            "configuration_sha256": binding.configuration_sha256,
            "resources": [{"path": path, "sha256": digest} for path, digest in binding.resources],
        },
    }


def encode_cache(index):
    """Pure bytes for an explicit caller; not permission to write a cache.

    An unrecorded checkout has no persistent tool identity and returns None.
    This observation may already be stale; readers always inspect fresh inputs.
    """
    binding = _binding(index._snapshot)
    if binding is None:
        return None
    order = {direction: {source.id: [view.relation_id for view in
                index.adjacency.for_artifact(source.id, direction=direction)]
            for source in index.adjacency.references.sources}
        for direction in ("outgoing", "incoming")}
    return canonical_json_bytes({"format": _FORMAT, "binding": binding,
                                 "order": order, "order_sha256": canonical_json_sha256(order)})


def _read_cache(boundary, maximum):
    with opened_resource(boundary, CACHE_PATH) as (descriptor, metadata):
        if metadata.st_size > maximum:
            return None
        chunks = []
        remaining = metadata.st_size
        while remaining:
            part = os.read(descriptor, min(65536, remaining))
            if not part:
                return None
            chunks.append(part)
            remaining -= len(part)
        # Descriptor size/signature and entry identity are rechecked on exit.
        raw = b"".join(chunks)
    return raw


def read_cache(source, snapshot, references, maximum):
    """Ignore unusable optional work; never retry or touch original input here."""
    if maximum == 0:
        return None
    try:
        binding = _binding(snapshot)
        if binding is None:
            return None
        raw = _read_cache(source.boundary, maximum)
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
