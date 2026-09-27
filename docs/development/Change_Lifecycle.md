# Standard lifecycle candidates (5.e)

`prepare_change_lifecycle` combines the existing ordered field/relation reducers
with typed `transition` and `retire`, applies section 9.6.3 to the folded model,
then reuses `change-metadata-v1` once per identity. Nothing is written.

The full content projection omits only the six top-level fields `revision`,
`created_at`, `created_by`, `updated_at`, `updated_by`, `maturity`. In particular,
relations, owner, provenance, planning, Extensions and title remain content.
Equal nested field names remain content. This projection is NOT the narrower
relations-review context hash.

Content changes to a base-approved artifact yield proposed. Pure retirement or
supersession is not reset afterwards. A contradictory explicit target fails as
an authoring error (2), or as an invalid saved plan (3). No-op/reverted content
keeps all base values. Later audit stamping runs once, not per operation.

Transition events retain the explicit reason/metadata and the bound actor/time
outside the artifact. A declared human actor is not authenticated by this API.
The previous approved revision is never overwritten or removed from the input.
There is no delete operation. A successor is an incoming stored `supersedes`
edge from a different same-type artifact in the final supplied model.

The standard transition matrix is fixed. The legal edge in_review -> approved
is refused with `approval_gate_required` until complete dedicated approval
services are wired into target planning. Creating a non-draft cannot smuggle in
approval. Special artifacts keep their dedicated workflows. Retired has no
outgoing status transitions; this does not invent content immutability for all
retired standard artifacts (immutable evidence/baselines are a separate rule).

The result is `standard_lifecycle_candidates_only`: metadata_applied and
lifecycle_checked describe candidate construction, not write authorization,
history completeness, final model-root verification or product approval. Earlier
field-only and metadata-only APIs retain their explicit narrower contracts.

Testing follows TD-001/TD-002: only new/directly affected tests locally with four
xdist workers; the full matrix runs in GitHub, and every fifth bundle includes
the serial reference. No presentation or documentation tests are introduced.
