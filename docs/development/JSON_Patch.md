# RFC-6902 value patches and guarded field-update previews

Plan step 5.b, requirements SR-REQ-0160 / SR-REQ-0232. References:
RFC 6902 sections 3–5 and Appendix A; RFC 6901 sections 3–5.

`JsonPatch` owns an immutable copy of all supplied JSON operations. The six
operators add/remove/replace/move/copy/test work on one private document copy,
in array order. A failure yields no partial result and never modifies the
caller's source or patch. Extra JSON members are preserved as passive data and
ignored by execution, as RFC 6902 requires. The shared iterative JSON value
boundary and typed JSON equality are reused; foreign conversion hooks are not run.

The pure `apply_json_patch(document, patch)` accepts arbitrary valid JSON value
roots. `PatchResult.document_exists` distinguishes a removed root from JSON null;
requesting `.data` for an absent root is an error. A later add at the root may
restore a document. Invalid pointer escapes, noncanonical array indices and
missing parents are errors. '-' appends only at an insertion destination; it is
an ordinary object member name otherwise. Move indices resolve after source
removal. Move to a descendant is forbidden. Copy never aliases source containers.

`compile_field_patch(document, options)` takes an ordered sequence of
`('--set', '/pointer=JSON')` and `('--unset', '/pointer')` pairs. This is a pure
conversion API, NOT an implemented CLI command. It splits set at the first '=';
use a full JSON Patch for object names containing '='. No shell expansion occurs.
An existing member/array slot is replaced; a missing object member is added.
An exact array-length destination or '-' appends. No holes, auto-created parent
objects, implicit unquoted strings, defaults or array deduplication. Later options
observe earlier options. This generic helper does not authorize artifact writes.

`preview_update(artifact, operation)` is the artifact-policy boundary. It validates
one existing field-valid artifact and one typed update, matches the actual target,
requires an explicitly supplied positive expected revision OR a canonical artifact
SHA-256, and checks both when provided. It reuses the existing special-workflow
routing and controlled-field protection for all destinations and move sources.
Readonly tests and copies may read controlled fields. A root write cannot replace
an artifact to evade this protection. All final fields are validated after patch
execution; intermediate temporary absence of ordinary required fields is allowed.

The returned `UpdatePreview` has `validation_scope=update_candidate_only`,
`metadata_applied=false`, `write_authorized=false`. It retains revision, actor,
time, identity and lifecycle fields unchanged. No transaction, live file check,
write, persisted revision, approval decision, model-root recomputation or full
Change Plan operation folding is implemented. Those are later 5.c/5.d/transaction
steps. In particular proposal planning must add both revision and hash as required
by its stronger contract; accepting either is the separate authoring input rule.

Local gates: only new/directly affected tests, four xdist workers. Full matrix
belongs to CI; Bundle 025 requires both parallel and serial full tests plus their
bound result comparison. CI observation and capture are unchanged under tools/.
