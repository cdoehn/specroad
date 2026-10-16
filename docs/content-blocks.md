# Content-block payload contracts

`specroad.documents.content_block_payload_schema(block_kind)` returns a detached,
standalone schema for one of `prose`, `artifact_ref`, `query`, `table`,
`admonition`, `page_break` and `include_document`. It uses the same compiled
payload definitions as the complete stored-record schema. Schema identity and
version are explicit; foreign fields and mixed outer payload branches are not
accepted. There is no user-supplied schema loader or remote schema resolution.

`ContentBlock(raw_bytes, path=...)` loads an immutable, source-bound block through
the existing record reader. The complete common and type-specific field checks
remain mandatory, including the local reference-cardinality/type contract. The
loader retains the original bytes, exposes detached `data` and `payload`, and
identifies the actual `block_kind`.

Its `binding` contains artifact ID, revision, path, original source hash,
canonical record and payload hashes, and the exact payload-schema identity and
hash. Mutating returned data or a returned schema does not change a later read.
The path is source metadata and is never opened by this API. No files or
revisions are changed.

These are passive field contracts. A readable artifact reference is not a
resolved target; a readable query is not an executed query. Prose parsing,
query/table evaluation, include traversal, composition, rendering and write
approval remain separate services. The binding keeps those claims false.
In particular, existing nested query/table field containers are not silently
promoted to a complete query, view or table evaluation contract.

The W tests compare actual payload values, source/schema hashes, allowed
alternative branches, rejection of foreign fields, owned bytes and isolated
Core/PYZ results. They do not compare rendered document output.

The loader also checks every stored relation through `SourceRelations` after the
native record checks. Required relation identity and metadata fields, unique
relation IDs, allowed metadata shapes and relation-field constraints must pass.
The general record reader keeps its existing partial projection; a successful
payload-only schema check cannot stand in for the complete block read. Errors
retain the original source path and the actual relation-array pointer.

These checks inspect supplied bytes only. They do not establish target existence,
graph type-pair validity, review state or inclusion cycles. Complete reference
metadata is retained without normalization or revision changes. The R tests
cover missing relation fields, mixed payload branches, required values, bad
choices, duplicate keys, read-only refusal and isolated Core/PYZ errors.

The internal `model._content_block_fields` module owns the payload definitions
and local reference validator. The ordered block-kind registry is derived from
those definitions. The full record schema and the standalone payload schema
both use this registry. Shared field-shape builders live in `model._field_shapes`;
the existing record-module names remain available through imports. This is a
structural consolidation: schema values, field-error contracts and block
bindings remain unchanged. The complete relation-field validator stays in its
existing graph module and is still called by the typed loader.
