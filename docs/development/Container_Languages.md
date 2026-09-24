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
