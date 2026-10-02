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

Test execution follows the local `AGENTS.md`; see [Testing.md](Testing.md)
for the technical commands. Bundle 025's dual CI mode was a historical rule
and no longer governs future runs. CI observation and capture remain under tools/.

## Robust adapters and error behavior

`JsonPatch.from_bytes` accepts the complete original UTF-8 patch array. It keeps
these bytes separately from its owned values, rejects duplicate members, invalid
Unicode, trailing values and number precision loss using the existing strict JSON
reader. Wrapper-relative line/byte positions are not fabricated as source positions.
A Python-value input cannot reconstruct numeric precision already lost by an
external JSON parser; use this raw-byte API for untrusted encoded patches.

`preview_update_bytes` similarly preserves both supplied original artifact and
operation bytes. `preview_field_update` binds the explicitly supplied revision/hash
before attempting any set/unset option. Missing and explicit null guard arguments
are different; invalid null is never interpreted as permission to omit a guard.
Controlled destinations are checked before comfort operations are simulated.
The normalized patch and its expected conditions remain in the returned typed
operation. No result claims a persisted revision, live freshness or authorization.

Root removal in the generic engine has a distinct absent-document result. It
can be followed by root add (or a generic set converted to add), but not by a
read/test/remove/replace of a fabricated null. Artifact preview rejects all root
writes, even a replace that would end up restoring the original identity.
The exact failure includes its patch-operation index and document pointer; no
operand contents are included in structured diagnostics.

The conformance cases cover the RFC 6902 Appendix A value examples (the duplicate
`op` member in A.13 is tested through the raw parser), all array move positions
for lengths 1–15 and 100 independent 25-operation list-splicing examples. These
are bounded independent checks, not a claim of exhaustive verification of every
possible JSON document. Deep value copies and equality do not use recursive
Python calls; the existing raw parser can conservatively reject excessive depth.

## Clean layering

`json_patch` owns only the pure execution engine. `field_patches` converts ordered
comfort options through that engine. `update_preview` owns explicit artifact
preconditions and candidate validation. `_patch_pointer` provides shared pointer
syntax, and `_patch_policy` keeps the controlled-field rules shared with the
existing ChangeOperation/ChangePlan validators. `patching` remains a stable facade.
No new execution hooks or writer adapters are introduced by this split. All W/R
behavior tests, expectations, raw vectors and requirement mappings are unchanged.
