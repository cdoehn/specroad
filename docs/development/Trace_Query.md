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
default trace depth does not silently cap it. `TraceTraversal(index, artifact_id,
direction=..., depth=...)` accepts an immutable resolved `RelationIndex` and
advances real graph work through `advance(units)`. The exact positive integer
budget counts node removals and individual directed edge checks. A paused object
keeps both pending identities and the current adjacency position; a high-degree
node does not consume all its edges in one unit. Cycles and alternative paths
retain each node once at its minimum distance and each traversed relation view
once. Changing the budget never changes the selected depth or final graph.

`advance` returns true only after the entire requested scope is complete.
`result` then returns owned `nodes`/`edges`; incomplete, failed or closed work
cannot publish a result. `state` is an owned progress observation, explicitly
`supplied_relation_set_only` and `durable_checkpoint=false`. Invalid budgets do
not consume work. `close()` cancels live continuation and is idempotent; failed
work cannot be restarted as a successful partial answer.

The public project handler drives the same engine in batches of 128 graph steps,
then applies its existing full observation checks. The index, accumulated graph,
and final sorted output remain in memory; loading, adjacency lookup and output
projection are not bounded by the graph-step budget. This API is process-local
and does not serialize or admit durable runtime Work. Command description keeps
`continuation_supported=false`. Durable Work, adaptive runtime admission, large
external delivery and supported-platform/performance acceptance remain open.

The private `graph._trace_frontier` module owns the existing cooperative engine
and its node identities. The public `query.trace.TraceTraversal` class keeps its
name, defining module and docstring and inherits that implementation. The project
adapter retains argument handling, complete source observation, preflights,
currentness checks, error mapping and result-schema validation. This separation
changes no graph rules, lifecycle transitions or output contracts.

Coverage binds every current artifact source, including unreachable sources.
Project read preflight runs before model loading and before the final currentness
check. Active writers, unresolved journals, invalid sources and changed membership
or bytes block success. The command does not create caches, acquire writer locks,
repair metadata or write project files. Coverage validates relation references
and canonical storage, with `atomic_snapshot=false`; full semantic validation
and approval remain separate. JSON payload ownership and all source bindings
use the existing Core contracts.
