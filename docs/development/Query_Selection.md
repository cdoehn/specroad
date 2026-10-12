# Query selection

`specroad.query.NormalizedQuery` materializes the internal query grammar from
specification 11.6. Filter groups use normalized field names such as
`implementation_status`. SRX operands are complete passive SRX documents, not
filenames. Each operand is validated and bound by its canonical content hash.
Projection pointer order is preserved; equal repeated pointers keep their first
position. The default sort and effective caller-supplied pagination default are
materialized in the scope-compatible query envelope.

`select_query(records, query, project=..., configuration=None)` operates on an
explicit list/tuple of `SourceRelations`. It builds the complete graph of those
inputs, including unselected sources and inverse relation views. Value filters
are OR within each group and AND between groups; repeated SRX predicates are AND
operands. SRX results must be Boolean. Missing, numeric and other results are
errors, never implicit truth values. Empty filter groups contribute true.

Supported selection groups are `type`, `maturity`, `implementation_status`,
`verification_plan_status`, `owner`, `tag`, `has_relation` and `missing_relation`.
Relation filters inspect both computed directions. Missing-relation alternatives
are OR, just like other repeated value filters. Projection returns exact stored
values; absent pointers yield `{"state":"missing"}`. Stored
`verification_result` is rejected and never treated as a computed result.

The returned `QuerySelection` is an owned, unpaged observation with input and
query bindings. `total` counts the complete selection in the supplied inventory;
`pagination_applied` is false. Its stable internal order is `(artifact_type,id)`.
Custom sort, offset and limit remain bound for the subsequent page stage and do
not truncate this selection. The observation is not the six-field public Query
result and does not assert project completeness, current evidence or approval.

This first W state exposes a pure Python kernel. The public CLI/structured request
and live project adapter remain open. Fulltext execution belongs to 8.c and
sorting/pagination to 8.d. Release closure, current verification aggregation and
evaluation binding require their actual providers; requesting these filters or
an evaluation currently raises a structured model error even for empty input.
Accepting their passive grammar does not claim their execution. Unknown filter
names, including empty unknown groups, are rejected. No I/O, subprocess, dynamic
callback, cache write or fallback to a previous result occurs in selection.

The development check runs the new selection cases and affected graph, SRX,
scope and query behavior tests in parallel. The complete suite is reserved for
Apply before the commit; requirement records remain partial.
