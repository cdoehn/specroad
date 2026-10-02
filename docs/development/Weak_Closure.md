# Weak closure and boundary references

`resolve_scope_closure` complements, rather than silently changing,
`resolve_strong_closure`. Both use the same required-resource traversal.
The old strong-only API still leaves weak edges pending.

For the stored outgoing `conflicts_with` and `duplicates` edges, `closed`
adds targets and follows all their dependencies to a fixed point. `partial`
follows the strong dependencies and records omitted weak targets instead.
A target selected by another seed or a required path is internal and has no
boundary. No reverse relation is fabricated and no relation is persisted.

Each boundary contains `source_id`, `relation_id`, `relation_type`, `target_id`,
`target_type`, `reason` and `origin_target_sha256`. For these real stored edges,
the relation ID is mandatory. Generated reasons are `boundary_policy_partial`.
The origin hash is JCS/SHA-256 of the complete target artifact, including audit
fields, not a hash of its pretty-printed bytes or a proof of authenticity.
Boundaries sort by UTF-8 `(source_id, relation_id, target_id)`. Separate edges
to the same target retain their identities. No duplicated normative edge arises.

Inputs are explicit `ScopeSeedInputs` and `ClosureBindings` supplied by trusted
readers/resolvers. Even partial generation needs actual origin targets. Missing
strong targets or required observations are errors, never boundary fallbacks.
Configuration filtering needs its future resolver; no implicit unfiltered
result is permitted. Existing specification control exclusions remain active.
Their full diagnostic integration belongs to 3.i.

The result's `closure_complete` is scoped to the supplied inventory and known
binding rules. `validation_scope=closure_over_supplied_bindings` and
`atomic_snapshot=false` distinguish it from a complete, atomic project read or
an approval. No normative Scope-Hash/model root, CLI command, persistent cache,
IO, resource/profile discovery or write authorization is added here.

Tests use owned data and observe membership, values, hashes and errors, not
terminal output, translations, formatting or documentation. Test execution follows
the local `AGENTS.md`; see [Testing.md](Testing.md) for the technical commands.

## Exact partial-reference validation

`validate_boundary_references(local_records, declarations, descriptor=...)`
compares the stored local source relations to exactly the declared omitted weak
endpoints. It rejects missing, duplicate, stray, type-mismatched or source/target-
mismatched declarations. A local target needs no boundary. A strong target
must exist locally, regardless of whether an origin copy or plausible hash was
supplied. Record IDs, relation IDs and external relation identities stay unique.
Both raw seven-field dictionaries and immutable `BoundaryReference` values are
accepted; no filename, URL or arbitrary metadata causes a read or execution.

Without `origin_sources`, omitted target content cannot be observed and
`origin_hashes_verified=false` is explicit. With origin records, local source
content must agree canonically with that origin, every origin relation must
resolve, and the declared target hashes must match actual canonical values.
This proves agreement with the **supplied** origin bytes, not their authenticity
or binding to a verified original model root. Archive/manifest verification,
read-only bundle policy and actual root binding remain tasks for M15.

`require_scope_closure_current` reruns the selection and closure using freshly
supplied observations and rejects old or tampered results. A caller must still
obtain new observations from the live providers first. No filesystem freshness
can be inferred merely from reusing equal in-memory objects.

The R regressions cover all 64 label assignments (absent, strong, duplicates,
conflicts_with) on the three possible edges of a three-node acyclic graph, each
with all three seeds and both policies. Separate cases cover cycles, a chain of
1,100 nodes, 141 boundary records, query pagination, missing providers, origin
changes and real execution in moved module/zipapp distributions. These are
behavioral checks, not assertions on documentation or human-readable output.

## Clean structure

`_boundary_contract` owns the passive field/endpoint rules; `boundaries` owns
immutable values and origin-based generation; `boundary_validation` owns exact
local/declaration matching and optional origin-content checks. Generation and
partial readers share the same endpoint contract. No W/R test or expected value
changes for this cleanup.
