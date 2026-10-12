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

This W implementation is synchronous: the loaded index, predecessor graph and
entire final path set are materialized in memory. `command describe why` reports
`continuation_supported=false`. R/C must add and clean up actual continuation of
search and path production. Durable Work, adaptive runtime admission, external
large-result delivery, effective profile/default resolution and supported-platform
and performance acceptance remain open. Small operational count targets do not
silently reduce the configured semantic depth or the promised path set.
