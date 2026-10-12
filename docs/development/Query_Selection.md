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
`verification_plan_status`, `owner`, `tag`, `has_relation`, `missing_relation` and `full_text`.
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
and live project adapter remain open. The fulltext provider from 8.c.W is available; sorting/pagination belongs to 8.d. Release closure, current verification aggregation and
evaluation binding require their actual providers; requesting these filters or
an evaluation currently raises a structured model error even for empty input.
Accepting their passive grammar does not claim their execution. Unknown filter
names, including empty unknown groups, are rejected. No I/O, subprocess, dynamic
callback, cache write or fallback to a previous result occurs in selection.

The development check runs the new selection cases and affected graph, SRX,
scope and query behavior tests in parallel. The complete suite is reserved for
Apply before the commit; requirement records remain partial.

## R: checked normalized input and status boundaries

`NormalizedQuery.from_data` accepts the closed materialized envelope only. It
rechecks canonical SRX hashes, validates every program through the real SRX
parser and rejects unknown fields and non-normalized inputs. A self-consistent
hash cannot turn a foreign operator into an executable query. Supported type,
maturity, stored status and relation filter values use the Core vocabularies;
an invalid alternative is an error even alongside valid alternatives.

Before returning any selection, both known stored status fields are checked over
all supplied sources. An invalid unselected source cannot disappear behind a
filter. An explicit projection of `/verification_result` (including descendants)
requires the actual computation provider, even for empty input or no matches.
It cannot become a fabricated Missing value. Passive extension metadata with
the same nested spelling remains ordinary data. Unknown query-envelope fields
are errors; a valid projection pointer to an absent stored value still returns
the specified Missing marker. Current verification computation, CLI and the live
project adapter remain open; this boundary does not implement aggregation 10.5.

## C: normalization, evaluation and projection

The normalization statements now live in `_query_normalization.py` and the
stored-field projection in `_selection_projection.py`. `selection.py` retains
the public `NormalizedQuery` and `QuerySelection` classes, their module identity,
and the evaluation/selection orchestration. The initializers and projection call
these pure helpers at the same points in the original sequence. All W/R behavior,
errors, result ownership, bindings and provider boundaries remain unchanged.

## Unicode fulltext selection (8.c.W)

`full_text` searches literal substrings in NFC-plus-casefold working copies of
`title`, `description`, `term`, the known type-specific main statement, and
prose/admonition `payload.markdown`. Scenario main-flow entries are separate text
values. The domain mappings include statement, decision, responsibility,
objective and definition; document purpose and proposal rationale are text
inputs where present. Each matching block keeps its own artifact identity.
No include rendering, attachment loading or arbitrary metadata stringification
occurs. Owner, IDs, tags and extension objects are not fulltext fields.

Repeated terms are OR alternatives, combined with the other value groups and SRX
predicates by AND. Matching uses Unicode NFC followed by casefold, without host
locale collation, accent removal, NFKC conversion or regex interpretation.
Projection and source/hash bindings retain the original source data. Known text
fields of the wrong type produce a structured model error. The search is still
the explicit-input selection stage, with no public CLI/page, live model validation,
persistent search index, Work continuation or approval claim. Specialist field
validation and document rendering remain separate providers. The requirement
stays partial pending the R/C and broader product/platform acceptance.


## Unicode source ownership (8.c.R)

Each fulltext comparison now starts from its exact `SourceRelations` input.
`SearchText` in the fulltext module owns immutable original bytes, their raw
SHA-256 and artifact identity separately from its normalized search copies.
Decoded mappings and foreign objects cannot claim this source contract. Query
selection looks up the actual supplied record by the graph-validated identity;
every invocation builds fresh copies, so replacing a source under the same ID
cannot reuse an earlier match. This is an in-memory observation, not a persistent
index, cache hint, canonical writer or project-completeness certificate.

NFC and NFD originals may match the same query while retaining different source
hashes and different projected text. Whitespace and escaped JSON encodings also
remain part of the exact original byte identity. Normalization applies only to
fulltext matching; owner/tag equality and projected values remain exact. Known
malformed prose or scenario text produces the existing structured error and
cannot be converted to Python display text.

R behavior tests switch real locales only in an isolated test subprocess, never
in parallel pytest workers or the product. `C` is mandatory; additional available
UTF-8/German/Turkish/English locale spellings are checked when installed. Exact
hits, input/query bindings, projected NFC/NFD text and source bytes are compared
across every successful switch. This measures the current environment and does
not replace supported-platform acceptance. Public CLI/live-project integration,
public page delivery and broader product/Work validation remain open.


## Unicode separation of responsibilities (8.c.C)

`_full_text_working_copy.py` contains the unchanged pure field selection and
NFC/casefold derivation. It accepts only the already decoded artifact value and
returns text copies; it has no source record, canonical writer or cache role.
`full_text.py` retains `SearchText`, exact original-byte/hash ownership and the
literal matching entrypoint. Calls remain at the same points. No storage format,
search result, error, source binding or allowed side effect changes. The existing
W/R tests remain byte-identical; an AST comparison against the bound Result also
checks the exact moved function and unchanged remaining source module.


## Complete sorting and exact pages (8.d.W)

`query_records(records, query, project=..., configuration=None)` uses the complete
`select_query` result and returns an owned `QueryPage`. Its detached `.data`
contains exactly `items`, `total`, `offset`, `limit`, `returned` and `truncated`.
`total` counts all filtered matches; only `items` is sliced after complete sorting.
`returned` is the delivered item count and `truncated` is exactly
`offset + returned < total`. Query/input hashes and source count are separate
observation attributes, not additional fields in that six-field result object.
The existing `select_query` API remains explicitly unpaged.

Sort values come from original source fields even when projection omits them.
Ascending precedence is Missing, null, Boolean, number, string. Numbers compare
numerically and strings use NFC UTF-8 bytes without casefolding or changing the
projected original. Each key has its own direction; the final ID tie-breaker
stays ascending. Default sorting is `(artifact_type, id)`. Every selected sort
operand is validated before pagination, including for limit zero: objects and
arrays produce `query_sort_value_not_scalar`. Computed verification-result keys
require the actual provider even for an empty inventory. Filtered-out extension
metadata is not a sort operand. Other unavailable semantic providers retain
their existing explicit errors.

This W kernel is synchronous and keeps the supplied inventory and selected rows
in memory. It does not silently cap results at the historical soft count target.
R/C will address large resumable selection and M6 spooling. Public CLI/live-project
integration, current verification aggregation, supported-platform acceptance and
full durable Work execution remain open; six-field kernel output is not a claim
that all public query semantics or whole-project validation are complete.

## Live external sorting and paging (8.d.R)

`QueryWork(spool_root, records, query, project=..., protected_roots=...,
configuration=None, batch_bytes=65536)` captures the supplied selection, then
uses the existing M6 sorter for real input, bounded sorted runs and pairwise
merges. The explicit new spool directory must be outside every protected
project/input/output boundary. Existing paths and symlink ancestry confer no
storage authority. There is no implicit project write or temporary-directory
choice. Native I/O errors propagate; closing or failing preserves owned files.

`advance(units)` advances actual sort and forward-only delivery operations.
`state` is a detached process-local description with `durable_checkpoint=false`;
it cannot be imported or used to reopen an arbitrary path. `result` becomes an
owned `QueryPage` only after every matching sort value and the complete external
sort have been processed. A partial prefix is never a complete query result.
Empty inputs, offsets at/beyond the end and zero limits retain the exact six
fields and the specified `truncated` formula. A large requested limit is not
capped at the historical soft count target. M6's batch byte goal limits encoded
sort batches, with its existing allowance for one oversized record.

Per-key directions, Missing/null/Boolean/number/string order and the final
ascending ID tie-breaker also govern external merges. Projected items are encoded
as owned JSON text inside spool rows so M6's outer JSON key sorting cannot reorder
requested projection pointers. Original Unicode values and source/query hashes
remain unchanged. The synchronous `query_records` API retains its existing pure,
in-memory behavior and errors.

The behavior checks compare single/multiple advance calls, independent page and
count oracles, an actual 10,001-item result, protected inputs, cancellation, native
write failure and run tampering. All previous tests remain unchanged. Upstream
selection still materializes the supplied inventory and matches; the requested
page is also retained in memory. This is bounded external sorting and live page
construction, not a whole-query RSS bound, process restart, adaptive-runtime
admission or durable `work-v1` implementation. Public CLI/live-project delivery,
current semantic providers and broader platform/product acceptance remain open.
