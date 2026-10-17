# Declarative snapshot view data

`specroad.documents.resolve_view(model, view_id, configuration_id=None)` evaluates
a native stored view in one owned `TargetModel` snapshot. The service accepts a
closed project scope and returns immutable `ViewData`. It performs no
file discovery, writes, rendering, approval or external status evaluation.
Private declaration planning validates scope, columns, formats, projection
bounds and grouping before the resolver evaluates rows. Rendering adapters
consume the resulting data separately.

The filter is an SRX 1.0 document. Sort entries declare `key` and `direction`
(`asc` or `desc`) and use native Query collation with the ascending ID tie-breaker.
All matching rows are returned, without an implicit 100-row page.

Columns declare exactly `source`, `heading`, `data_type`, `format="plain"` and
`missing="error"` or `missing="preserve"`. Preserve emits `{"type":"missing"}`
without a value field. Present null/false/zero values keep their actual type and
must still match the declared column type. Sources have two forms:

- `{"kind":"artifact_field","pointer":"/title"}` uses a static SRX field pointer.
- `{"kind":"relation_projection","projection_id":"dependencies"}` selects a
  declared relation projection. Its type is `array` for `ids`/`records`, `number` for `count`.

A projection declares exactly `id`, `direction` (`outgoing`, `incoming`, `both`),
an explicit nonempty list of native relation `types`, nonnegative integer
`max_depth`, and `aggregation` (`ids`, `count` or `records`). A `records`
projection additionally requires a nonempty `columns` list using the same closed
column contract. Its rows bind target ID/type/revision, original source SHA-256,
canonical record SHA-256 and typed cells. Nested columns may reference other
named projections; definition cycles fail before selection. Shared dependencies
are evaluated iteratively in the same snapshot. Every level retains its own
direction, type and depth bounds. It traverses the actual bound
project graph. Targets are distinct artifact IDs, ordered by ID; cycles and
multiple paths do not duplicate them. The starting artifact is excluded, so
depth zero returns no related targets. A row filter selects rows without
discarding graph nodes needed by their projections. Missing relation targets
remain graph errors. Native soft work targets are not semantic depth limits.

Grouping entries declare `column` (zero-based index) and `direction`. Only
scalar columns can form groups. Keys follow native missing/null/boolean/number/string
collation, with NFC-normalized UTF-8 string keys. Original row strings remain
unchanged. Each group contains typed keys and row IDs in the view's sort order.

Every declaration is checked even when the filter selects no rows. Foreign
loaders, executable column fields and unavailable formatting, missing-value,
computed-status or scope providers fail explicitly. The existing basic
query/table-block adapter retains its separate narrower contract.

Declared output formats are the distinct static names `json`, `markdown`, `html`
and `csv`. Unknown provider names and duplicates are rejected before filtering;
accepting a name does not perform rendering. Original source bytes, including
noncanonical whitespace, remain bound separately from canonical model values.
Malformed graph inventories still fail for empty selections. File, process and
network operations are absent from the resolver; data resembling code stays data.

A configuration can be declared in the view scope or supplied through the
keyword-only `configuration_id`. Conflicting explicit and declared IDs fail.
The actual selected record and its parent chain must be in the same snapshot;
missing selections, invalid values or applicability expressions never produce a
partial success. With no selection, potentially applicable variants remain
available and no configuration is chosen implicitly.

Native Query services resolve both the filtered rows and the complete applicable
graph inventory. A row filter may omit an applicable intermediate node without
removing it from relation traversal. An excluded node is never traversed. Sort
ties use ascending artifact IDs, including after descending scalar keys; an
explicit ID sort direction is retained.

`selection_scope_descriptor` binds the effective selection separately from the
stored view scope and the full supplied snapshot root. The query binding carries
the selected configuration ID, revision and effective chain digest. Original
configuration byte changes affect input hashes even when canonical values and
selected results remain equal. This API does not attest a live configured scope
closure or implement the later view CLI/rendering adapters.

The data binds the original view bytes/revision, full snapshot root/input hashes,
view scope, native query result/hashes, and each row's source/record hashes.
Returned data is detached. It does not certify live project files, complete
validation, document structure, rendering, write permission or approval.
