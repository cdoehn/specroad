# Verification waiver values

The `specroad.verification` embedding API implements the `12.b.W/R` subset of
specification 0.2.9, section 10.5.5. It reads supplied owned values; it does not
open a project, run test code, infer the current time or grant write authority.

Use `waiver_content_projection` / `waiver_content_sha256` on a `DomainArtifact`
of type capability, requirement or task. The exact versioned field list excludes
the waiver and specified workflow/audit fields; full artifact hashes remain
unchanged. Scope and effective configuration are bound separately.

Construct `WaiverContext(subject, ScopeDescriptor(...), evaluated_at=...,
configuration=...)`, where configuration is either the actual resolved
`EffectiveConfiguration` or explicit unconfigured absence. The context owns its
inputs. `prepare_verification_waiver` prepares a passive versioned candidate with
reason, future UTC deadline and a human review ID. It does not invent a review.

`prepare_verification_plan_update` returns a native guarded `ChangeOperation`
containing only the workflow status and, when supplied, the waiver. Pass this
operation to the existing common authoring planner/writer; its native validation,
lifecycle, publication and stale-input checks remain necessary. A prepared
operation does not establish that the waiver is currently effective.

For an actual stored subject, `assess_verification_waiver` checks the current
content hash, exact scope/configuration and UTC deadline against the supplied
`evaluated_at`. A `HumanWaiverReview` binds the complete waiver hash and subject
identity. A trusted host must explicitly supply `WaiverReviewVerifier`; arbitrary
project JSON, a human actor label or an unrelated relation review is insufficient.
A verifier observes typed context/review values and returns a bound
`WaiverReviewVerification`. Missing, stale, rejected, nonhuman or unverified
reviews cannot activate the exception.

The review callback receives detached context/review values. A change to either
callback input, the original inputs or the selected verifier during that call
invalidates the observation (`waiver_review_inputs_changed`). Results retain
their original input hashes. Typed confirmations still require actual booleans;
exceptions produce `waiver_review_verification_failed` without host details.
Every assessment asks the verifier again; a previous success does not override
revocation or authorize reuse for different evaluation inputs. This is an
in-process consistency check on trusted host code, not a Python sandbox.

The returned `WaiverAssessment` reports `waiver_result=waived` or `ineffective`
with machine-readable reasons. It never reports `passed` or writes a normative
`verification_result`. It does not establish scope membership, configuration
applicability, full verification aggregation or release readiness. Those services
must apply the specification's complete precedence rules separately.

Legacy waivers remain byte-preserving readable data and report
`legacy_waiver_unsupported`. The new helper does not reissue them. There is no
automatic deadline interpretation, migration, extension or human confirmation.
An explicit new candidate and matching review are necessary. Event-based expiry
conditions remain unsupported.
