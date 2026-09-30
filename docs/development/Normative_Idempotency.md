# Normative request retries

`prepare_authoring_request(...)` supplies the explicit normative identity and
normalized ordered operations to `resolve_normative_request(source, request)`.
No ChangePlan or current TargetModel is needed for that decision. Call it before
a new plan or writer lock; `replay` returns the original `result_object` and
`created_ids`, not a re-execution. Actor, base, target and transaction are kept
in `original_request` for historical interpretation.

The matching key is the case-sensitive normative request ID plus canonical
operations hash. Actor and current model are not substituted for the stored
request; the receipt is not authentication, authorization or a current-target
attestation. Preview requests and omitted optional IDs do not read receipts.
Analysis correlations do not belong to this typed normative API.

Receipt JSON alone is insufficient. The reader requires the existing committed
marker and all linked transaction/request receipts, verifies project and root
identity, hashes and fresh readback. Incomplete/corrupt proof fails closed.
Completed-work cleanup preserves the immutable proof needed for later retries.
No recovery or cleanup runs implicitly in the retry reader.

`new_request` is a non-atomic absence observation, never an ID reservation. The
native publication boundary rechecks under its writer lock, both before and
after trusted callbacks. Completed IDs cannot start another journal/publication.
Concurrent callers still use the existing lock and recovery contracts.

This is the native changes API. It does not install a second generic writer,
a CLI service, automatic recovery or an analyzer receipt store. Public command
wiring remains at its assigned implementation-plan steps.

A changed operations hash raises `RequestIdConflict` (exit code 6). Its
machine-readable diagnostic binds expected/received operation hashes and
distinguishes the prior committed request from the refused current write.
That conflict alone does not require recovery and never authorizes rollback.
