# Shortest origin paths

`specroad why <artifact-id>` and `specroad.query.why_artifact(root, artifact_id)`
return every shortest path from the start to each reachable Goal, Need and Source.
The depth comes from the project's explicit `resource_limits.trace_depth`.
A missing declaration produces model error `why_depth_not_configured`; the
example configuration's value is not guessed as an effective profile default.
Zero is valid. A known origin start has one zero-edge path to itself; an unknown
start remains an error. No CLI depth override is currently registered.

Connectivity follows stored directed relations and the inverse views of the two
symmetric types, `conflicts_with` and `duplicates`. Ordinary incoming directed
relations are not reversed. This uses the specification's directed relation
model; no extra origin-type filter, status filter or inferred text edge is added.
All relation references, canonical storage and protected hierarchies are checked
over the complete current inventory. This is a graph explanation with explicitly
limited validation coverage, not full semantic approval or release readiness.

The shortest distance is determined separately for each reachable origin.
Reaching a Need or Goal does not stop exploration toward another origin. All
equal-distance predecessors are retained, including distinct stored relation
identities connecting the same artifact sequence. Only distance-increasing
predecessors participate in materialization, so cycles cannot create repeated
walks. An iterative enumeration emits all shortest paths; no representative path,
sample or implicit count cap is substituted for the requested set.

The `artifact-why-v1` result contains the start, configured depth, traversal policy,
targets with exact distance/path count, all `paths`, exact total `path_count`, and
coverage of every current artifact source. Targets sort by type/ID, and their
paths sort by artifact-ID sequence, relation-ID sequence and inverse flags.
Each path uses the existing `PathRecord` contract: complete artifact identities,
stored relation identities and direction flags. The output preserves a symmetric
edge's one normative identity. Result values are owned copies.

Project read preflight occurs before graph loading and again before the final
currentness check. Active writers, unresolved journals, invalid unreachable
sources and changes to any observed source or configuration block success.
The command creates no project cache, writer lock or other project file.
`atomic_snapshot=false` and `full_semantic_validation=false` remain explicit.

The public command drives `WhyTraversal(index, artifact_id, depth=...)`
synchronously. The producer accepts an immutable `RelationIndex` and exposes
`advance(units)`, `state`, `result`, `checkpoint()`, `restore(...)` and `close()`.
A positive exact integer work target advances individual node, edge or path-frame
operations. Search retains its pending nodes, current adjacency offset and every
minimum-distance predecessor; path enumeration retains its stack and already
produced prefix. An incomplete, closed or failed producer cannot publish a result.
Changing operational targets never changes depth, path completeness or ordering.

`checkpoint()` returns canonical JSON bytes containing both frontiers and the
complete produced prefix. The owner persists these bytes and independently
retains their SHA-256. `WhyTraversal.restore(index, raw, expected_sha256=digest)`
checks that trusted digest before parsing or visiting the graph, validates a
closed data contract and rebinds every artifact identity and stored relation
value, including unreachable relations. Artifact contents outside the supplied
graph projection are not available to this producer; the public command retains
its separate complete-project currentness check. Array order does not change the
graph binding. The algorithm version and semantic start/depth belong to the
checkpoint. Restoration reconstructs the actual position without replaying
completed search or already produced paths. No imports, callbacks or executable
payloads are loaded from checkpoint data.

A checksum supplied by an untrusted checkpoint is not an independent trust anchor.
The codec itself performs no file writes, atomic publication or fsync and makes
no claim that exported bytes are already durably stored. Caller-owned files and
a separately retained digest can cross a process restart, as verified by native
subprocess tests. This is not admission to the generic Work-v1 store or a public
`work resume` integration; `command describe why` continues to report
`continuation_supported=false` and producer state reports `durable_checkpoint=false`.

Input/hierarchy validation, target/path sorting, checkpoint encoding and final
projection are indivisible. The index, predecessor graph and full result prefix
remain materialized in memory. Private graph modules now separate predecessor search from path materialization;
the public producer still owns one unchanged checkpoint across both phases.
Durable Work integration, adaptive runtime admission, external large-result
delivery, effective profile/default resolution and supported-platform/performance
acceptance remain open. No sample or implicit count cap replaces the full set.
