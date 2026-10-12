# Direct Impact

`specroad impact <artifact-id>` and `specroad.query.impact_artifact(root, id)`
report every direct incoming and outgoing stored relation, grouped by its stored
relation type. Each connection retains its normative relation identity, physical
source/target, related ID and direction. Symmetric views retain one stored
identity. Distinct relations to the same neighbour remain distinct; a structurally
invalid self-reference appears in both physical directions and once in the
review grouping. No transitive-only neighbour or operational count cap is added.

The current complete artifact inventory, including all relation-review records,
is read through the existing protected project boundary. Appendix J review
selection supplies `unreviewed`, `current`, `suspect` and `invalid`, with exact
reason, selected review and matching/historical review IDs. Four separate
`review_groups` list relation IDs and affected endpoint IDs. Grouped connections
explain the relation type and both endpoints for each finding. Referenced missing
IDs remain visible with `related_present=false`; no artifact is invented for them.

Structural invalidity, including missing targets, forbidden endpoint pairs,
self-relations and noncanonical symmetric storage, remains visible. A matching
rejected review remains invalid with `current_review_rejected` and SRV027/error.
The completed direct assessment returns exit 1 with its complete result when a
direct relation is invalid; unreviewed/suspect use existing Core warning defaults
and do not alone change exit 0. This command does not resolve effective profile
severity policy and reports `profile_policy_applied=false` explicitly. Malformed
source or review fields abort with model error rather than return a partial list.

The assessment is one hop from the requested existing artifact. Unrelated
structurally invalid relations are outside that direct assessment; all source
bytes and membership still participate in the currentness binding. An isolated
artifact has complete empty groups. An unknown start is a model error. Read
preflight occurs before capture and before the final complete-inventory byte,
membership and configuration check. Active writers, unresolved journals and
observed changes prevent success. No cache, lock or project file is written.

The closed `artifact-impact-v1` result, version `1.1.0`, declares depth 1, `transitive=false`, exact
groups and review partitions, and current-inventory coverage. Groups sort by
stored relation type; connections sort by related ID, direction and relation ID;
ID lists sort lexicographically. Coverage is artifact-field and review-status
validation, not full hierarchy/lifecycle/release validation or an atomic snapshot.
Review history is observed from current project records, not authenticated by
this command. No risk, priority, verification or downstream consequence is inferred
from absent domain information. All result values are owned copies.

`artifact_observations` covers exactly the start and its direct endpoints, sorted
by artifact ID. Each row reports actual presence and the stored artifact type;
a missing target has `present=false` and `artifact_type=null`, without inferring
its type from the ID. The declared `priority` and `verification_plan_status`
fields each have one of three states: `present` with the literal stored value,
`missing` for an absent field on an existing artifact, or `unavailable` for an
absent artifact. Invalid declared values remain model errors. Text, extensions,
review confirmations and neighbouring artifacts cannot supply a missing value.

Every row declares `verification_assessment.state=not_performed`. A stored
verification workflow state, including a structurally readable waiver, is not a
computed verification result. The impact reader does not select evidence or
perform the verification aggregation in specification section 10.5. Reordering
sources or stored relations preserves the affected sets and review selections;
diagnostic locations still identify the actual stored relation. Passive cache
contents cannot replace current artifacts or alter the assessment. The final
inventory check also guards the projection of these domain facts.

The command is synchronous and materializes the inventory and result. Public Work
continuation, external large-result delivery, effective profile policy, alternate
base providers and supported-platform/performance acceptance remain open. The
planned C step shares the calculation with planner
callers; existing supplied-input direct-impact primitives remain available.
