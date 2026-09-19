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
terminal output, translations, formatting or documentation. The existing
parallel development gate and explicit serial reference remain unchanged.
