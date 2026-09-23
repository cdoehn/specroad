# Explicit profile composition (4.k)

`compose_profiles(resources, core_key=..., project_profiles=(), cli_profiles=())`
selects exactly one Core version first. A nonempty explicit CLI list replaces the
project list. These are supplied argument values, not newly installed CLI flags.
No environment, filesystem, default Core version or latest-version lookup occurs.
Duplicate selected profile identities (including different versions) are errors.
Available but unselected resources do not affect the resulting hash.

Required/forbidden fields are unions; allowed values are intersections per
artifact-type/maturity cell. Empty maturity selectors expand to all maturities.
Thus differently scoped rules only conflict where their selectors overlap.
Null is present; a value restriction never makes an optional field mandatory.
Relation and lint identities must have identical version and canonical definition
hash on repetition. Rules retain their first position. Overrides apply after
identity resolution; later profiles win, but no Core minimum can be lowered.
Core structural/integrity/identity/evidence/transaction/path and execution
diagnostics from chapter 13 have immutable error floors. A code-level override
cannot selectively downgrade SRV027 review outcomes without also downgrading its
structural failures; such code-wide weakening is rejected.

The complete immutable `EffectiveProfile.data` is the JCS/SHA-256 hash preimage:
ordered profile identities/hashes, language bindings and the materialized merge.
`source_sha256`/file formatting and the origin of selection (project vs CLI) do
not change its semantic hash. Profile resource descriptions ARE part of the
original canonical resource hash. This is not an authenticity/signature proof.

`check_composed_fields` reuses the single-resource field observer. It does not
run lint programs, perform a full project scan, or approve a lifecycle operation.
`minimum_relation_rules` exposes the effective rules to the existing explicit
graph checker, whose built-in Core obligations remain independently enforced.
On conflict `ProfileCompositionError` carries SRV142/exit 3 and no effective
profile. Diagnostic consumers may display the exception, not treat it as a model.
The later full validation/CLI pipeline must propagate this failure; it is not
implicitly connected to the still-unimplemented model commands here.

The W subset rejects nonempty language bindings and has no scalar/limit
composition yet. The R state completes those explicit contracts.
Local bundle gates run selected files with four xdist workers, never a full
serial or parallel suite. Full CI belongs to the final commit of Bundle 015.
Bundle 016 retains the periodic serial plus parallel reference.
