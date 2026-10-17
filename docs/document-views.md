# Declarative snapshot view data

`specroad.documents.resolve_view(model, view_id)` evaluates a native stored view
in one owned `TargetModel` snapshot. The initial service accepts a closed,
unconfigured project scope and returns immutable `ViewData`. It performs no
file discovery, writes, rendering, approval or external status evaluation.

The filter is an SRX 1.0 document. Sort entries declare `key` and `direction`
(`asc` or `desc`) and use native Query collation with the ascending ID tie-breaker.
All matching rows are returned, without an implicit 100-row page.

Columns declare exactly `source`, `heading`, `data_type`, `format="plain"` and
`missing="error"`. Sources currently have two forms:

- `{"kind":"artifact_field","pointer":"/title"}` uses a static SRX field pointer.
- `{"kind":"relation_projection","projection_id":"dependencies"}` selects a
  declared relation projection. Its type is `array` for `ids`, `number` for `count`.

A projection declares exactly `id`, `direction` (`outgoing`, `incoming`, `both`),
an explicit nonempty list of native relation `types`, nonnegative integer
`max_depth`, and `aggregation` (`ids` or `count`). It traverses the actual bound
project graph. Targets are distinct artifact IDs, ordered by ID; cycles and
multiple paths do not duplicate them. The starting artifact is excluded, so
depth zero returns no related targets. A row filter selects rows without
discarding graph nodes needed by their projections. Missing relation targets
remain graph errors. Native soft work targets are not semantic depth limits.

Grouping entries declare `column` (zero-based index) and `direction`. Only
scalar columns can form groups. Keys follow native null/boolean/number/string
collation, with NFC-normalized UTF-8 string keys. Original row strings remain
unchanged. Each group contains typed keys and row IDs in the view's sort order.

Every declaration is checked even when the filter selects no rows. Foreign
loaders, executable column fields and unavailable formatting, missing-value,
computed-status, configuration or scope providers fail explicitly. Configuration
support and further projection policies follow in 11.l. The existing basic
query/table-block adapter retains its separate narrower contract.

The data binds the original view bytes/revision, full snapshot root/input hashes,
view scope, native query result/hashes, and each row's source/record hashes.
Returned data is detached. It does not certify live project files, complete
validation, document structure, rendering, write permission or approval.
