# Requirement approval observations

`specroad.validation.assess_requirement_approval` checks the prerequisites of the
human `in_review -> approved` decision. It has no filesystem reader, writer,
clock, login service, CLI action or automatic detector. Source bytes, status,
revision and audit values remain unchanged. `approval_granted` and
`write_authorized` always remain false.

## Supplied bindings and trust

`ApprovalContext` owns the selected requirement and loaded dependency documents,
selected effective profile, explicitly resolved configuration and semantic field
projections. Its digest includes the exact original source bytes, not only a
mutable title or the requirement ID. There is no claim that these are all live
project files or an atomic snapshot. The caller must stabilize inputs while
constructing values and revalidate under the eventual write transaction.

Each `ApprovalPrerequisite` is an explicitly trusted service observation for
model validity, current verification contract, required relation reviews, active
profile rules, configuration consistency, language policy and placeholder/lint
results. All are required, each is bound to the full input digest, and a passing
observation identifies its own evidence digest. Missing, failed, stale or
unavailable service observations cannot grant eligibility. The value constructor
validates binding shape, not the truth of arbitrary caller-supplied evidence.
It is NOT an authentication primitive and is not a new persisted artifact type.

The same applies to `HumanRequirementReview`: a passive observed review with
exact candidate and force/statement bindings. An actor label `human` is not an
identity proof. A trusted `ReviewVerifier` must explicitly attest that the bound
review belongs to an authenticated human and is current. This version supplies
the integration contract, not an identity provider or review-history selector.
No verifier is inferred from JSON, a module path, an environment variable or an
AI classification. A missing verifier means unavailable, not implicit trust.

The human separately confirms one normative force and one independently testable
proposition, the combined force/statement meaning, scope/conditions,
observability, terminology, consistency and an equivalent verification contract.
A human-confirmed compound observation blocks approval with SRV162. Core never
infers that judgment from words such as "and", syntax or a language detector.

## Formal projections

A detached hypothetical `approved` candidate exercises the existing strict
schemas, rationale and should-deviation requirements, actual target types,
canonical relations, hierarchy checks, profile fields and minimum relations.
It never overwrites the original `in_review` record. Missing origin or
`verified_by` is blocking even when a supplied semantic observation says passed.
Existence of a verification relation is not proof of a current valid oracle;
that independent semantic observation is still required.

Quality measurements are explicitly projected from the existing structured
semantics by rows of four JSON Pointers: property, method, comparison and target.
There must be at least one complete row. Scalars and explicit numerical
`{value, unit}` targets are supported; Core does not guess a measurement from
free text. Interface projections refer to one existing boundary/interface or to
existing source and target components. No new artifact top-level fields, modal
keywords in text or inferred default force are introduced.

`mode="stored"` assesses an already approved loaded record but cannot request a
new transition. `mode="transition"` requires the existing `in_review` state.
A ready observation is only `eligible_for_human_approval`, not a performed
transition or complete product approval.

## Tests

Local W: `tests/test_requirement_approval.py`; local R/C add the directly related
robustness tests. Only these selected files run with four xdist workers. The full
catalog is collected separately without executing a complete suite. Full matrix
runs in GitHub at the last bundle commit; every fifth bundle adds serial and
comparison. Synthetic service fixtures explicitly do not authenticate real users.
