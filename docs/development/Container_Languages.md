# Container language mixing (4.n)

The supplied `ContainerModel` owns source bytes. It validates reference identities
and relevant record fields, not completeness of a physical project. Language
mixing uses declared Requirement tags and the explicitly bound registry only.
There is no detector, text-language inference or trace-closure expansion.

`evaluate_project_languages` counts requirements except `retired`, `superseded`
and `rejected`. `evaluate_document_languages` resolves `contains` and displayed
`artifact_ref` blocks, including nested sections and explicitly shown historical
requirements. Every container occurrence has its own set of requirement IDs.
Repeated references count once; parent containers include descendant membership.

`primary_language` and `exact_tag` reuse the language-policy comparison contract.
Private/unverified tags retain the full normalized tag. `und`, `mul` and `zxx`
do not add concrete-language keys; their independent findings remain visible.
`SRV180` is emitted for more than one key unless the container action is `allow`.
A document/section's optional `language_policy_override.mixed_languages` affects
only its own mixing check, never the parent check or project allowlist.

Outputs name all tags, requirement IDs, container occurrence and policy.
Fail thresholds change exit decisions, not diagnostic severities. Results remain
`resolved_container_requirements_only`, `project_complete=false`,
`atomic_snapshot=false`, `approval_granted=false`. No file is written.

## Resolved presentation and configuration boundary

`include_document` traverses the selected document/section, including nested
sections. Cycles fail without returning a partial success. Every occurrence path
is a tuple of actual containment/reference relation IDs; repeated inclusion of
the same document creates independent container checks.

Embedded queries and view tables require `QueryRows` for the exact block and
occurrence. These rows bind the model hash, selected configuration hash (or null),
and complete ordered artifact IDs. Missing, unused, duplicate, stale or incomplete
observations fail. A query's expressions, cell strings, and implicit pages are
never evaluated or guessed here. Nonrequirement rows do not add languages.

`ResolvedRequirementScope` is a required explicit applicability observation when
using a configuration. It binds the model, actual configuration resource ID/hash,
and selected requirement identities, including historical IDs where applicable.
The projection does not itself calculate applicability. Inconsistent query/scope
observations are errors. Unconfigured projection has configuration=null.

These supplied resolver results are structurally and content-bound, not external
attestations. Whole-project/configuration acquisition and actual query execution
remain responsibilities of their later planned services. No false claim of full
renderer, atomic project snapshot or source authenticity follows from this check.

## Responsibility boundaries after C

`container_values` owns byte snapshots and bound resolver value objects;
`_container_projection` handles identity-based selection and presentation edges;
`containers` combines the resulting sets with the existing declared-language
assessment and severity policy. The W/R behavior tests remain unchanged.
