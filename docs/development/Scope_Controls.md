# Permanent specification-scope control exclusions

`proposal` and `baseline` are permanently excluded from `specification`, not
merely omitted from its seeds. Every followed stored relation, evidence subject,
selected current review and explicit resource binding passes admission before
its target enters the identity worklist. An excluded required artifact raises
`ScopeControlDependencyError`, a `ModelError` with `code=SRV140`,
`reason=scope_control_dependency`, `exit_code=3`, source ID, target ID, and the
original relation ID or JSON pointer. No closure result is returned on failure.

`partial` does not weaken strong dependencies. A weak target not followed under
`partial` retains the existing boundary-reference contract, including its origin
hash. Such a scope is not a valid proposal basis. This step does not implement
proposal workflows or their CLI argument error classification.

`project`, `document`, `explicit`, `release` and `query` keep their own scope
rules: a control artifact is not universally forbidden. Ordinary text and
extensions are passive, never interpreted as relation instructions.

The pure admission policy recognizes configuration wrappers around specification.
Actual configured selection remains blocked pending its configuration resolver;
this helper does not discard filters or claim to evaluate applicability.

Unreferenced control changes do not change the selected non-control member
values or their canonical hashes. Inventory/closure observation hashes STILL bind
all supplied inputs and may change: they are not normative model-root hashes.
Scope-hash primitives are a separate plan step. Live completeness, transactions,
atomic snapshots and full proposal lifecycle enforcement are not certified here.
No file access, write, cache creation, CLI command or new dependency is added.

## R-23 and partial-input validation

Stored relations are considered in their stable relation-ID order for deterministic
error choice; diagnostics retain the index from the original source relation list.
Required references to control artifacts are rejected before their missing review,
usage or archive providers could be interpreted as permission to omit the target.
The caller must still supply observations for the source being processed.

The partial-relation reader applies the same admission policy to its supplied
local members, including configuration wrappers. An origin inventory is not a
local membership list: omitted control targets remain legal origins of weak
partial boundaries and are not accidentally admitted by hash verification.
A local control supplied as a seed is diagnosed with its target ID and a
`/sources/<index>/id` input pointer; it has no fabricated referring source ID.

Regression cases include a 1,100-view reference chain, document composition,
evidence subjects, coexistence of weak/strong edges, current-review type misuse,
passive identifier-looking strings, stable repeated diagnostics and relocated
module/zipapp execution. The process regression returns the model error's code 3;
no new CLI command or proposal workflow is implied.
