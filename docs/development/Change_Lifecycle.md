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

Test execution follows the local `AGENTS.md`; see [Testing.md](Testing.md)
for the technical commands.

## Complete candidate verification

`prepare_plan_lifecycle` recomputes final candidate status and audit fields from
actual supplied base values and ordered operations before comparing every stored
result hash. Supplied scope/root must match the plan. A self-consistent hash on
a forged approved result is not sufficient. No final project root is asserted.

`prepare_change_lifecycle_bytes` accepts actual UTF-8 bytes, not path strings,
and retains exact source bytes on the candidate. Duplicate/malformed JSON fails.
`previously_approved_ids` is an explicit history observation; known IDs stay
reserved even outside the current selected scope. The current approved source
ID is retained when its candidate becomes proposed/retired. The API has no
physical-delete operation and makes no claim of complete historical discovery.

Successor evidence is checked in the final supplied model; a removed edge or a
wrong-direction edge cannot satisfy supersession. Protected hierarchy cycles
are rejected using the existing graph validator. Repeated guarded retirement
of an already retired value is a no-op; no transition out of retired is allowed.

A pending legal approval edge is checked only after content conflicts, so an
attempt to reapprove changed base-approved content in the same plan is never
accepted. Complete approval integration remains a required dedicated gate;
`human` labels and arbitrary transition metadata cannot supply it.

Approved-only field obligations are evaluated against the pending proposed
candidate. Intermediate revision/hash/from guards still see the actual ordered
values. The private validation projection never changes the input or silently
relaxes the common field contracts.

## Responsibility boundary after C

The fixed transition table, six-field content projection and final lifecycle
postconditions live in `_lifecycle_policy.py`. The public planner owns ordered
operation orchestration, explicit history observations and raw/saved-plan
adapters. The unchanged metadata materializer stamps only the already decided
candidate. No filesystem writer is aware of the lifecycle policy.
