# Change Plans: data contracts, not writes

`specroad.changes` implements the regular `1.2.0` Change Plan data boundary
from specification §§10.1–10.4. `prepare_change_plan` receives **all** planned
values explicitly, checks them and binds their canonical values. `ChangePlan`
reads a complete, self-hashed raw JSON object and retains its original bytes.
Canonical serialization never changes actor, timestamp, revisions, ordered
operations, result artifacts or arbitrary literal payloads. Existing self-hashes
are not silently recomputed. Only the top-level `change_plan_sha256` is excluded
from its own SHA-256 domain; nested names remain bound.

`change_plan_schema()` returns a detached built-in schema; no external schemas,
callbacks or plugin registry are loaded. Each operation is a tagged immutable
`ChangeOperation` with an exact payload contract. The operation tag is `op`.
Supported data shapes: create, update, relation_add, relation_remove, transition,
retire, evidence_record, attachment_add/remove, representation_normalize,
relation_review_record and the proposal_control specialization of §10.4.

The table in §10.2 gives minimum contents rather than a literal full JSON schema.
This layer expresses create as `{op, artifact, result_id}`, relation_add as
`{op, source, relation}`, and final artifacts as `{artifact, sha256}`. The nested
relation and artifact objects use the existing core field contracts. Reference
strings are actual artifact IDs, never display IDs. Preconditions are tagged
`artifact` (artifact_id with expected_revision and/or expected_sha256), `file`
(path plus expected_byte_sha256) or `absent` (path). They are **declared, not
executed**. Unknown outer fields and operation tags are rejected. Additional
RFC-6902 members remain passive, bound data as required by that patch format.

Generic writes cannot manufacture Evidence, Baselines, Proposals or Relationsreviews.
An update cannot target controlled identity, audit, maturity, status or relation
fields, nor move them away via its `from` pointer. A specialized payload is not
proof of its originating command, trusted human reviewer or valid approval.

Scope of this step: `change_plan_fields_only`, `execution_ready=false`,
`write_authorized=false`. No file or network access, creation/deletion, full
model validation, live revision/hash comparison, RFC-6902 execution, lifecycle
transition, metadata advancement or transaction publication is implemented here.
Regular authoring accepts only `change-metadata-v1`; merge and migration policies
remain explicitly rejected until their separately bound models/services exist.
No actor, request ID, plan ID, time, random identity, result or expected root is
inferred. AI-tagged actors can be read as data; this does not grant write authority.

The subsequent plan steps implement patch execution (5.b), folding (5.c), bound
metadata (5.d), lifecycle (5.e) and transaction gates. Stored target hashes here
are assertions for those later stages, not proof of an observed project state.
The schema is currently exposed as a Python API, not registered as a new CLI command.

The change-plan tests contain the behavioral evidence for this section.
Test execution follows the local `AGENTS.md`; see [Testing.md](Testing.md)
for the technical commands. The CI triggers and modes for Bundles 024/025
were historical rules and no longer govern future runs.

The robust boundary also checks the **declared result-owner set**: modified
artifact identities and declared final artifacts must agree. A sole create and
immutable evidence/review records must match their declared final bytes-by-value
hash; sequences of mutable operations are not simulated here. Duplicate creation
IDs, new relation IDs and overlapping precondition targets are errors. Empty
plans cannot declare a changed model root. These are internal consistency checks,
not proof that the supplied model root or preconditions describe live storage.

Normalization in this regular data API is limited to project configuration,
profile/rule/mapping JSON and ordinary artifact paths. Special-record, generated,
archive, attachment and operational paths are refused. A later specialized
planner can supply any additional state-aware normalization contract; this API
does not guess that a proposal or baseline is still editable. Review withdrawal
owners must be distinct requirements; proposal event sequences must be continuous
and compatible with the declared final control state. Human actor metadata is
required where specified, but is never authentication or review authorization.

The Clean state uses one fixed operation registry tying each tag to its fresh
schema provider, domain validator, result-owner projection and workflow label.
There is no registration API and data cannot name executable providers. The
plan-envelope/result-binding checks and immutable values are separate from these
adapters. Public plan and operation payloads, canonical hashes, original bytes
and structured rejections are unchanged by this internal refactoring.
