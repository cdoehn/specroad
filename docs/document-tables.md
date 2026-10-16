# Query and table block data

`specroad.documents.resolve_table_block(model, block_id)` accepts an owned native
`TargetModel`. It rebuilds the snapshot from its original bytes, checks the
selected `ContentBlock` and the complete supplied relation graph, then returns
immutable `TableBlockData`. It performs no file discovery, writes or rendering.

There are three row sources:

- An embedded query uses `NormalizedQuery.from_data` and `query_records`, with
  its exact filters, bound SRX documents, ordering, offset and limit. The native
  six-field result is retained as `query_result` with query/input hashes.
- A `source="view"` block resolves its one actual `references` relation to a
  native view record in the same snapshot. The basic view supports a closed
  project scope, its SRX filter, artifact-field columns and native sort keys.
  A selected configuration is resolved by the existing query engine from the
  same records. All matching rows are returned without an implicit 100-row cap.
- A literal table retains its declared row order. Every row must match the
  column width; cells are typed JSON data. Nested objects carrying a copied
  artifact identity/type pair are rejected as manually duplicated model data.

Query-block columns may use the closed form `{"field": "/title"}`. Full view
columns declare exactly `source={kind:"artifact_field", pointer:...}`, `heading`,
`data_type`, `format="plain"` and `missing="error"`. The current basic adapter
rejects unsupported formatting/missing-value providers, grouping, relation
projections and non-project scopes; the complete view service follows in
11.k/11.l. A query block may provide its own columns over a referenced view;
the view's original column declarations are still checked, even for empty
results. Every view column must use the full form; the query-only `field`
shorthand cannot replace its required declarations.

Literal columns declare `field` and may add `heading` and `data_type`. Declared
types are `null`, `boolean`, `number`, `string`, `array` or `object`; there is no
coercion. Without a declaration the actual JSON type remains explicit. Dynamic
cells additionally distinguish `missing` from `null` and from an object whose
contents happen to be `{"state":"missing"}`. Strings remain inert data even
when they resemble a template. Column definitions have no executable fields.

Table columns form their own explicit field projection from the selected
snapshot rows. They do not rewrite a query's stored `select` declaration or its
native result. Field access uses the existing static SRX pointer resolver, not
JSONPath, a template language or a URL/file loader. Selected row records pass
their native type-specific stored-field reader. Missing computed verification
providers remain errors rather than invented stored values.

The report binds project/model/input hashes, block bytes/revision, optional view
bytes/revision/reference/scope, query/configuration hashes and each dynamic row's
identity, revision and source/record hashes. Re-evaluating a new model observes
changed rows without rewriting the block or mutating previous returned values.
`block_source_bytes` and `view_source_bytes` retain the owned original records.

For an empty query page, `empty_policy=omit` or `message` produces that semantic
outcome without generating human text; `error` raises `table_query_empty`.
The native filtered total remains available even for `limit=0`. An empty literal
or view table has outcome `empty` unless a query block declares another policy.

The scope is `supplied_snapshot_table_projection`. Complete on-disk inventory,
whole-project validation, document structure, rendering, writes and approval
remain unproved. Tests compare typed rows, bindings, errors and side effects;
they never compare rendered table layout, Markdown or HTML.

Invalid block/view references, external-source fields, executable declarations,
unsupported scopes and unavailable providers fail before any table result is
created. Empty filters and query-column overrides do not suppress declaration
validation. Byte-only source changes update source/input hashes while preserving
semantic model roots, revisions and query results. The owned snapshot is resolved
without opening source paths, running processes or accessing the network.

The private table projection adapter owns closed column/cell/literal/view
declarations. The public service retains snapshot binding and calls the native
query engine. This separation introduces no block query language or additional
execution provider. Public values and error classes retain their contracts.
