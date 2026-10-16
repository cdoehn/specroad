# Artifact references in documents

`specroad.documents.resolve_artifact_reference(model, block_id)` resolves one
`artifact_ref` block from an actual owned `TargetModel`. The caller supplies a
complete project inventory. The function rebuilds the native snapshot, checks
the block's exact fields and one required `references` relation, validates the
supplied relation graph, then reads the target through its native field reader.
It never selects by title, display label, external identity or payload target ID.

The immutable `ArtifactReferenceResolution` retains `block_source_bytes` and
`target_source_bytes`. Its detached `data` binds the project, supplied model root,
input inventory, block, actual relation pointer/hash, and target path, identity,
revision and source/record hashes. `target_record` decodes the retained target
bytes afresh. `render_mode` remains the stored `summary`, `full` or `link` value;
this operation does not format content.

Multiple document blocks can refer to the same target. Their relations remain
independent while each projection reads that target's one normative source.
The returned target record is derived data, not a second manually maintained
payload copy. No file, artifact revision or block payload is written.

Missing targets and invalid relation identities or type pairs are native model
errors. The selected source must be a content block of kind `artifact_ref`, and
the target must satisfy its own type-specific stored fields. All stored edges
in the supplied model must resolve; no partial graph fallback is constructed.

The result resolves the selected reference only. It does not prove completeness
on disk, document ownership/role correctness, include acyclicity, complete model
validation or payload execution. Rendering, writes and approval remain false.
A resolution cannot be converted to a Boolean approval. Document composition
can use these data projections after its own independent structural checks.

The native schema forbids copied target IDs or normative target fields in an
`artifact_ref` payload, even if the copy agrees with the actual target. The
owned model and relation checks reject duplicate identities before resolution
can select a winner. Titles or equal content never substitute for a missing ID.

Resolve again from a new owned model snapshot to observe a changed target. Every
new document projection then uses the new target bytes/revision; block bytes,
block revisions and stored edges remain unchanged. Previously returned values
retain their original snapshot. A byte-only reformat changes source/input hashes
while preserving the canonical record hash, model root and stored revision.
The R tests establish these boundaries through the existing native guards;
no alternate validation path or additional target-copy mechanism is introduced.

Internally, `documents._reference_sources` performs the native snapshot,
selected-block, relation-graph and target-field checks. The public module builds
the same immutable data projection from those source values and retains the
public error class. The helper contains no document ownership decision or
format renderer; those consumers can use the bound result independently.
The existing W/R behavior, field errors, hashes and allowed side effects remain
unchanged across this structural separation.
