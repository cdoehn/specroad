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

## Explicit policy and language inputs

Optional `hard_limits` declarations accept positive integer values for the known
hard structure/format limits: artifact_file_bytes, json_depth, xml_depth,
srx_nodes, srx_depth, archive_uncompressed_bytes. The minimum of all active
profiles wins. No soft work budget, trace/query default or unknown limit is
reclassified as a hard cutoff; such declarations are rejected.

Optional `normative_policy` is a map of named scalar normative values. Multiple
profiles must agree on a value's canonical JSON value (bool is not number).
Omission makes no declaration; null is an explicit value. No merge-by-last-writer
or inferred nested-object merge. Language/default-locale, analyzer and SRX policy
remain in effective project configuration, not in this generic scalar map.
This data contract does not itself inject names into project configuration.

Optional `language_registry` accepts an explicitly supplied LanguageRegistry;
`language_packages` accepts explicitly activated LanguagePackage objects. Their
bytes and metadata are rechecked. Registry identity/version/hash/validator and
ordered package identity/version/ranges/hash are included in the full preimage.
Identical package duplicates coalesce; conflicting bytes under the same package
key fail. An explicit null registry and no packages mean absent bindings, not a
claim that a real project's language dependencies are resolved. A future project
consumer must supply its actual required bindings; it may not omit them and
claim a fully validated project. No package is found via locale, I/O or fallback.
These inputs do not change stored content language or translate any artifact.
Local bundle gates run selected files with four xdist workers, never a full
serial or parallel suite. Full CI belongs to the final commit of Bundle 015.
Bundle 016 retains the periodic serial plus parallel reference.


## Module boundaries after 4.k.C

The `profiles.composition` facade owns explicit selection and typed language
binding checks. `composition_values` owns immutable results and SRV142 failures.
`_composition_merge` centralizes the ordered mapping from each declaration family
to its merge strategy (union/intersection/identity/later-wins/minimum/equality).
The strategy registry is fixed trusted code; profiles cannot supply callbacks.
The field observer is shared with individual ProfileResource checks. No behavior
or test expectation changes in C. Complete materialized values and failures are
additionally compared to R on a separate 70-case local projection corpus.
