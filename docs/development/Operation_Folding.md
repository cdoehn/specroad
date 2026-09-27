# Ordered Change Plan field candidates

Plan step 5.c; implementation W. The pure `fold_operations` entrypoint applies
`create` and `update` in the declared array order to private intermediate values.
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
