# Directed trace

`specroad trace <artifact-id> --direction in|out|both --depth <n>` reads the complete
current project relation inventory. Direction and depth are required. CLI and
structured requests represent depth as an ASCII decimal string; the Python API
`specroad.query.trace_artifact(root, artifact_id, direction=..., depth=...)` takes
an exact nonnegative integer. Flags, unknown directions and malformed depths are
usage errors. An unknown start remains an error at depth zero.

The result schema is `artifact-trace-v1` with format version `1.0.0`. `nodes`
contains identities, artifact types and minimum edge distances, sorted by
distance then ID. `edges` contains the directed views actually traversed from
nodes below the requested depth. A boundary node is included and not expanded;
the result is not an induced subgraph of every edge between reached nodes.
Each view retains `relation_id`, traversal `source`/`target`, `inverse`, the
original `stored_source` and complete `stored_relation`. Both directions can
expose two views of the same stored identity without creating a second stored
relation. The named inverse of `supersedes` remains `superseded_by`.

The existing identity frontier orders work by distance/ID and admits an artifact
identity only once. The explicit depth defines semantic scope; the historical
default trace depth does not silently cap it. The synchronous W handler visits
the complete selected scope and keeps its result in memory. Command description
reports `continuation_supported=false`; process-local stepping and broader
cycle/multiple-path/soft-target acceptance belong to R. Durable Work, large
external delivery and supported-platform/performance acceptance remain open.

Coverage binds every current artifact source, including unreachable sources.
Project read preflight runs before model loading and before the final currentness
check. Active writers, unresolved journals, invalid sources and changed membership
or bytes block success. The command does not create caches, acquire writer locks,
repair metadata or write project files. Coverage validates relation references
and canonical storage, with `atomic_snapshot=false`; full semantic validation
and approval remain separate. JSON payload ownership and all source bindings
use the existing Core contracts.
