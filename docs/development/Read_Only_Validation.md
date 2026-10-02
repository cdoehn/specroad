# Read-only validation and diagnostic exceptions – 4.r

## Interfaces and evidence boundary

`specroad.storage.read_only.validate_project_read_only` captures the current artifact
sources from an explicitly selected existing project root and uses the real shared
model validator and fail-policy. Profiles are explicit versioned `ProfileResource`
inputs; selection uses Core first and the configured or explicit CLI profile list.
Composition conflicts are returned before artifacts are read. This API does not
silently substitute distribution profiles for missing project resources.

`lint_project_read_only` applies one explicitly supplied `LiteralPolicy` to selected
artifact IDs, using current stored term artifacts as its glossary. It never guesses
reference fields or executes a project analyzer. No applicable literal check is
reported as a passed language check. These are library entrypoints, not new CLI
commands or a complete resource/profile/graph acceptance claim.

`diagnose_read_only` reads shallow operational names/types without loading
`specroad.json`, artifacts, journal payloads or caches. It remains available with
corrupt/missing configuration and reports unresolved metadata without treating the
model as valid. It grants no recovery permission and does not clear locks.

## Conservative operational boundary

Missing or empty `.specroad/` needs no write. Cache and completed receipt subtrees
are not required input. Entries in `.specroad/transactions/` other than its receipts
directory, and entries in `.specroad/recovery/`, require explicit investigation:
normal validation and lint return code 5 before loading the model. Unknown
operational entries are blocked as unknown; no PID/host heuristic declares a
writer dead. Even a journal claiming completion is not trusted without the later
transaction resolver. No journal, receipt, cache, lock or missing file is created,
updated or deleted, including when `auto_recover` is enabled.

This is NOT the complete N.2 preflight, journal validator or lock engine. Metadata
is shallow-enumerated, not a bounded/resumable journal detail scan. Future
transaction/lock implementations must provide their complete state protocol and
fresh ownership checks rather than weakening these conservative failures. No
whole-project validity is inferred from an empty active namespace.

## Freshness and permissions

Existing descriptor-relative Core readers reject linked paths and special files.
Configuration, artifact membership, exact original bytes and the operational
observation are checked again before results are returned. Observed changes fail;
there is no promise of an atomic multi-file snapshot or exclusion of concurrent
writers. This API never calls preliminary write-target authorization, starts a
subprocess, probes writability, repairs a file or creates a cache.

Explicitly supplied `ModelGate` callables are trusted application code operating
on detached model data. A Python library cannot sandbox arbitrary trusted
callbacks; the read-only contract remains their responsibility as well.

## Tests and integration

The new behavior tests compare source/operational/generated inventories and trap
write attempts even when the runner can bypass POSIX mode restrictions. They also
exercise readonly file and directory modes, real parsing/model/literal results,
recovery blocking and metadata-only diagnosis. Text layout and documentation are
not test oracles. Test execution follows the local `AGENTS.md`; see
[Testing.md](Testing.md) for the technical commands. These behavior cases remain
part of the suite and do not define a separate Apply selection.

Source-bound observations must not be reused as transaction write authorization.
The later planner/writer must independently revalidate state under its own lock.

## Completion and failure contracts

The reader rechecks operational metadata immediately before starting the normal
model read, after profile composition. Creation of recovery metadata at that
boundary blocks model loading. Configuration and complete artifact membership
are checked before and after the final content pass; the source observation
binds exact config bytes and source hashes, not only mtimes or file sizes.
`freshness_verified` certifies only these repeated observations. It is not an
atomic snapshot or reusable write token. Recognized changes discard the proposed
successful validation/lint result; no stale success body is returned.

Facade exit codes follow the operation boundary: usage/configuration/profile
conflicts 2, malformed model 3, I/O/recovery/unavailable checks 5, unsafe paths 7,
and a reached lint threshold 1. Producer-specific diagnostics are retained, with
an explicitly named producer exit code when their narrow library classification
differs from this facade. Missing applicable lint checks yield `passed=null` and
`status=incomplete`; a successful metadata diagnostic has no model-pass claim.
Warning severity is not raised by `strict`, only the failure threshold changes.

No project-path output parameter is exposed here. Explicit report-file outputs,
full N.2 preflight accounting, ownership resolution and persistent transaction
changes remain in their own planned components. This layer does not declare
journals committed by reading a string, probe process IDs, or fall back to an old
cache. It does not attempt to repair permissions after a denied read.

## Internal separation

`read_only.py` exposes the three library operations and re-exports the owned result
type. `_read_only_inputs.py` owns only observation/capture/recheck operations;
`_read_only_reporting.py` projects independent failures and blocked-state reports;
`read_only_values.py` owns immutable detached reports. None is a publisher or a
future transaction writer. The refactoring changes no file-selection rule, hash
input, diagnostic decision or side effect; the W/R behavior tests remain intact.
