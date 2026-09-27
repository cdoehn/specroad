# Ordered Change Plan field candidates

Plan step 5.c; implementation W/R/C. The pure `fold_operations` entrypoint applies
`create`, `update`, `relation_add` and `relation_remove` in the declared array order to private intermediate values.
`fold_plan_fields` additionally binds an immutable self-hashed plan to explicitly
supplied scope/root observations. Observations are not authenticated live reads.

Plan-wide artifact/file/absence preconditions apply to the initial supplied
snapshot. Per-operation guards inspect the immediately preceding intermediate
artifact. Unknown file snapshots are not interpreted as empty snapshots.

Only one candidate per touched artifact is returned, with the source hash,
pre-metadata candidate hash and the indices of contributing operations. Reverted
or no-op changes stay visible as touched candidates with `changed=false`.
Unchanged artifacts remain in the returned isolated model. Failed operations
raise a structured error; no partial model is returned and subsequent operation
bodies are not executed. Original inputs, stored plans and returned snapshots
are independent. There are no file, process, clock, identity-allocation or network
operations here.

## Boundaries

`validation_scope=ordered_field_candidates_only`. Metadata, lifecycle,
`expected_result` hashes and full target validation are not applied or verified.
The current `revision` stays at its base value; 5.d advances it once per final
semantic change, not per operation. Unsupported specialized operations fail
explicitly; they are never skipped or interpreted as successful no-ops.
Even a successful result is neither execution-ready nor a write authorization.
The library is not a sandbox and cannot atomically copy concurrently mutated
caller-owned objects; callers must stabilize inputs during snapshot creation.

## Verification

Only new/directly affected tests run locally with four xdist workers. Full CI
runs at the final bundle commit. Requirement manifests retain `partial` until
the subsequent planner, lifecycle and transaction gates are integrated.

## Relation reducers

Initial stored edges use the existing reference/matrix/symmetry validation.
Relation additions (including those inside new artifacts) require targets that
exist at that point, unique relation identities, canonical symmetric direction
and non-conflicting external identities. A relation removed during this fold
keeps its ID reserved: a later operation cannot reuse it. Explicit reserved IDs
represent the caller-supplied historical/reservation inventory, not an inferred
complete project history. No random generator is called.

Relation removal checks the hash of the complete current relation, including
its metadata, before replacing the owner's private relation array. A later
artifact update sees that exact intermediate relation state. Net-no-op folds
retain their operation history without inventing a revision or audit change.
Graph-wide cycles, lifecycle duties and authorization remain later target gates.

The supported four reducers do not pretend to implement the other eight workflow
families. Lifecycle/retire, attachments, evidence, normalization, review and
proposal control operations explicitly require their specialized planner. This
is an extensible-by-code boundary, not dynamic code registration from plan data.

## Clean separation

Private source/precondition processing, fixed reducers and final one-per-owner
materialization are separate pure helpers. The public orchestration still
performs each operation in declared order and catches its first error before
calling another reducer. Candidate hashing happens after the sequence, distinct
from intermediate revision/hash precondition checks. W/R test expectations are
unchanged by this structural separation.
