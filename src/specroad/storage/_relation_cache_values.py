"""Cache envelope, version/dependency binding and incremental shape checks.

These helpers transform observed values and recorded runtime metadata only.
Native file access and the optional-failure boundary stay in _relation_cache;
the authoritative current-project reader remains independent of cache data.
"""

import sys

from .. import _build
from .._metadata import MODEL_SCHEMA_VERSION, __version__
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..runtime.distribution import distribution_identity


_FORMAT = "specroad-relation-index-cache-v1"
_POLICY = "canonical-relations-and-view-order-v1"


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


class _CacheShape:
    """Cheap streaming rejection before optional JSON objects are allocated.

    This is not a JSON validator. It bounds nesting and structural marks for
    this fixed cache format; the strict decoder still validates all syntax.
    Quotes/escapes span native short reads, including one-byte chunks.
    """
    def __init__(self, maximum_marks):
        self.remaining = maximum_marks
        self.depth = 0
        self.quoted = False
        self.escaped = False

    def feed(self, raw):
        for byte in raw:
            if self.quoted:
                if self.escaped:
                    self.escaped = False
                elif byte == 92:
                    self.escaped = True
                elif byte == 34:
                    self.quoted = False
            elif byte == 34:
                self.quoted = True
            elif byte in (123, 125, 91, 93, 44, 58):
                self.remaining -= 1
                if byte in (123, 91):
                    self.depth += 1
                elif byte in (125, 93):
                    self.depth -= 1
                if self.remaining < 0 or not 0 <= self.depth <= 8:
                    raise ModelError("relation_cache_structure_too_expensive")

    def finish(self):
        if self.quoted or self.depth != 0:
            raise ModelError("invalid_relation_cache_structure")
