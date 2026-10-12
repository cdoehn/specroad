# Supplied-input semantic comparison

`specroad.query.compare_semantic(before, after, ...)` compares two explicit
`ComparisonInputs` values from the same project. It validates every supplied
artifact's stored fields, then uses the existing canonical artifact/field
comparison. Inputs and results remain owned data. The function performs no file
access, source lookup, Git operation, project mutation or external execution.

The `semantic-diff-v1` result retains exact artifact identities, canonical input
and artifact hashes, presence flags, values and JSON Pointers. It groups the
observed classes without discarding the underlying field differences. Existing
addition, removal, retirement, threshold, exception, relation, document,
verification and code-reference classes remain available. Applicability,
configuration and stored workflow statuses have distinct classes. Evidence
result, binding and other record changes are distinguished; changed evidence
bytes do not establish currency or subject verification.

Unstructured domain text, including criteria, procedures, definitions and
reasons, stays `text_changed` when no stronger declared classification applies.
Text inside namespaced extensions is opaque even when its keys resemble Core
fields such as `timing`, `thresholds` or `verification_result`. Added/removed
text containers retain their full values and presence flags. The classifier
walks JSON values iteratively; it does not parse Markdown, detect languages,
normalize Unicode or interpret numbers and words inside prose. Unknown numeric
or Boolean deltas remain structural `field_changed` observations. Declared
machine values such as enum choices, identities and code paths retain their
existing structural classifications.

Optional `before_configuration` and `after_configuration` must both be typed
`ProjectConfiguration` values matching the project and ID prefix. Comparison
uses the existing semantic configuration projection. Raw declarations remain
hash-bound even when only presentation/operational values differ. With neither
configuration supplied, `project_configuration.state` is `not_supplied` and its
`changed` value is null; absent declarations do not become equal configurations.

Optional `timing_bounds` maps requirement IDs to an explicit `maximum` or
`minimum` interpretation. Both sides must contain that requirement and a valid
duration. The existing exact duration comparison supplies tightened, relaxed,
equivalent or incomparable observations. Policies are validated and bound even
for unchanged artifacts. No direction is inferred from a field name, prose or
numeric movement. Calendar durations do not acquire guessed fixed seconds.

`inventory_delta` reports added/removed IDs only within the supplied artifact
sets. It does not attribute those differences to configuration filtering.
`configuration_scope.state` and `evidence_currency.state` remain `not_evaluated`:
applicability evaluation, resulting model scope and evidence-currentness
selection require their later providers. A field-valid approved record grants
no approval. `full_semantic_validation`, `approval_granted` and `write_authorized`
remain false.

The private `_semantic_classes` module owns declared field classes, opaque-text
recognition, paired configuration comparison and explicit duration policies.
The public `compare_semantic` driver retains input validation, general artifact
comparison, identity/hash bindings and result assembly. This separation retains
the W/R algorithms and behavior; it introduces no additional interpretation.

The kernel materializes both supplied inventories and the full diff. Git/local
source adapters, public Diff CLI,
Work continuation, effective profiles, applicability-derived scope, evaluated
evidence currency and supported-platform/performance acceptance remain open.
