# Scope hashes and comparison primitives – step 3.j

The pure `fingerprint_scope` adapter revalidates the supplied ScopeClosure against
its dependency observations before projecting a canonical model manifest.
Its `scope_sha256` binds the descriptor, selected artifact/value hashes,
versioned resources, attachment metadata, boundaries and semantic policy hashes.
It uses the exact existing `model-manifest-v1` projection. Existing supported
manifest inputs retain their previous hashes. Original JSON whitespace,
observation fingerprints, roots, inode numbers and traversal order are absent
from this semantic hash. Full artifact values, including revision/audit values,
are NOT silently excluded.

Opaque resource IDs are connected to explicit ManifestResource records; registry
path/size and normative profile/rule/mapping ID/version are never inferred from
filenames. Archive resources require the future verified object provider and
fail with `scope_hash_archive_expansion_required`, not an invented hash of a
partial archive. Configured scopes still require their planned resolver.

This is a pure operation over supplied data. It neither reads current files nor
certifies freshness outside those observations, full inventory completeness,
profile composition, origin authenticity or atomicity. ModelManifest retains
its conservative `manifest_inputs_only` flags; no write approval is issued.

`ComparisonInputs` and `compare_artifacts` compare explicitly identified artifact
sets from the same project. Added and removed mean presence in these input sets,
not an authorized create/delete operation. Identical canonical JSON values do
not generate changes. `field_diff` emits JSON Pointer locations, explicit
presence flags and detached old/new values. Missing and null differ; booleans
and numbers differ. Arrays remain atomic ordered values, not guessed element
identities. The result is an observation, NOT an executable JSON Patch.

Unstructured statement changes are `text_changed`; no keyword or numeric prose
heuristic interprets natural language. `direct_impact` includes both incoming
and outgoing stored edges grouped by stored relation type, retains all relation
IDs, and does not expand transitively. It accepts the complete supplied resolved
relation set, not a page of presentation output. Superseded-by views keep the
underlying supersedes identity. No presentation, environment, Git, network,
clock or filesystem adapter is involved.

The existing noninteractive CLI, its colors, runtime dependencies, pytest-xdist
configuration and all previous PRoot safeguards are unchanged. These are
preparatory APIs for the later Change Plan and Diff/Impact command providers,
not newly registered commands. Tests assert data and behavior only, no rendered
strings, documentation checks or layout snapshots.
