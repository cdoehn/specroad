# Baseline manifest preparation

`specroad.archive.build_baseline_manifest` returns an immutable `BaselineManifest`
with canonical manifest bytes and deduplicated `SnapshotObject` values. It takes
an effective `ProjectConfiguration`, read binding, resolved scope and explicit
closure dependencies. The caller supplies complete current observations.

`resource_payloads` maps each selected profile/rule/mapping inventory identity
to `(relative_project_path, original_json_bytes)`. `attachment_payloads` maps
each selected attachment path to its exact bytes. Both maps must match the
selected scope exactly. The effective profile is recomposed from its selected
profile bytes. Semantic configuration, effective profile and model manifest
bytes are retained alongside the selected content objects.

Every manifest row binds its logical role, applicable identity/revision/version,
source path, length, media type, SHA-256 and content-addressed object path.
The model root is the existing scope-manifest hash calculated before the new
Baseline artifact exists. `working` and `release` are preparation labels.
`assurance` explicitly reports the limited scope and absence of write/readiness
or complete project-validation authority.

This preparation API supports resolved scopes with JSON artifact/profile/rule/
mapping resources and exact attachments. Configured scopes also retain their
actual selection chain; language/archival providers still require integration.
It writes nothing, obtains
no project lock and creates no Baseline artifact. The following specialized
writer must validate the actual project, enforce readiness where needed and
publish through the existing transaction/journal contract. Owned objects can
already be prepared in the external `SnapshotObjectStore`.

For named publication, pass the planned `baseline_id`. The identity must belong
to this project and must not already occur anywhere in the input inventory,
even outside the selected scope. It is retained as Baseline metadata and never
inserted into its own model root. Omission prepares unnamed data only; the
following writer must supply its planned identity before publication.

The preparation rebuilds inventory/dependency observations from original bytes
before accepting closure. Runtime paths, inode values, display preferences,
soft operational limits and local clock/zone do not enter the semantic root.
Normative JSON values, including stored artifact audit fields, remain bound.

## Native working-Baseline publication

`specroad.archive.creation.prepare_working_baseline` prepares a saveable plan
from a complete supplied `TargetModel`, a host-owned `random128-v1` Baseline ID,
name, actor, timestamp and plan/request IDs. `create_working_baseline` executes
exactly that saved `ChangePlan` through the native authoring transaction. The
embedding host supplies publication authority and all applicable semantic gates.
Preparation alone does not authorize publication; execution checks the actual
complete JSON inventory and every bound input byte under the writer lock.

The native integration supports whole-project working snapshots, optionally
bound to an explicit `configuration_id` during preparation.
It preserves canonical normative JSON and exact attachment, IANA registry and
already bound archive bytes. Snapshot objects extend the target project manifest
under `archive_objects`; all archive-free model hashes remain byte-identical.
Every object is staged, independently read back and published before the new
`sealed`/`approved` record. Content-addressed archive creation never replaces an
existing file. Native receipts identify the new record and make an identical
confirmed saved request replayable without another write.

The built-in gates cover the newly prepared Baseline only. Existing approvals,
older Baselines and other semantic subjects still require their trusted complete
providers; a new Baseline cannot certify them. Other selected scopes,
installed language package snapshots,
CLI wiring and release readiness are separate integration work. Unsupported
inputs or missing providers fail closed. No release approval is inferred.

An interrupted write retains the actual native journal and file state and
reports no completed Baseline. A failure during the no-replace object move can
leave both image names; that state remains recovery-blocked rather than being
silently removed. Prepared journals support independent discard-basis checking.

Before publishing a new archive name, the writer checks the staged image again
after the last boundary callback. It then synchronizes the new archive directory
entry before removing the staged name. A directory-sync failure therefore keeps
the staged bytes and the actual new link available as recovery evidence; it
cannot advance the journal or create the Baseline record. Truncated, missing or
changed staged/published bytes, stale model inputs, unsafe paths and conflicting
saved requests remain blocking. Failures after record publication or during
finalization retain their real state without an automatic retry or a false
completion result.

The public creation facade keeps both function names. Its unchanged saved-plan
preparation lives in the private `_working_plan` module; native publication
remains in `creation`. The separation changes no plan, gate, failure, receipt
or filesystem behavior.

## Read-only verification of archived snapshots

`verify_baseline_snapshot(boundary, baseline_record_bytes)` accepts the explicit
Baseline record and an existing `ProjectBoundary` containing its archive. It
reads content-addressed objects with the existing descriptor-based guards and
reconstructs the semantic configuration, composed profile, model manifest and
precreation root. Original working files and Git are unnecessary; current files
never substitute for missing objects. Objects are re-read before returning.

The current adapter supports closed project snapshots, including an explicitly
stored configuration selection and its complete parent chain,
including binary attachments, IANA registry and referenced archive bytes. Other
scopes and installed language packages fail explicitly. Inert locale/output
values are used only to reuse configuration validation; their exact semantic
projection must equal the stored configuration and no output path is accessed.
The report proves the supplied snapshot bindings only. It grants no authoring
or release authority, historical full-validation proof, atomic observation or
original-project completeness. CLI and shared-validator integration remain
separate work.

`verify_baseline_objects(record_bytes, objects)` checks the same snapshot from
explicit immutable `SnapshotObject` bytes. A larger inventory may be shared by
several Baselines; the result covers the referenced set only. The host owns
complete live inventory and freshness, and the verifier grants no disk evidence.
`baseline_integrity_gate(objects)` registers that real check through the common
`ModelGate` contract. It binds actual resource bytes, examines every selected
Baseline and preserves each diagnostic location. Historical snapshot artifacts
need no current model counterpart. Other gates, especially lifecycle authority,
remain independently required. There is no cached success or default approval.

The common-pipeline adapter is kept separately in `_validation_gate`; the
verification facade retains the existing public registration function. This
separation changes no object checks, gate binding, diagnostics or authority.


`show_baseline_snapshot(boundary, record_bytes)` returns the stored Baseline
record and a fresh integrity status. A well-formed record with missing or
inconsistent archived bytes has `status: failed`; malformed records, unsafe
paths and host I/O failures raise their existing exceptions. It never writes
or reuses a prior successful report.

`materialize_baseline_snapshot(boundary, record_bytes, destination,
default_locale=..., generated_path=..., protected_roots=(...))` restores the
supported project snapshot into a missing absolute path
under a private owned canonical external parent. The archive is automatically
protected; the host supplies every other protected project/input/output root.
Native Linux descriptor guards and the existing exclusive writer primitives
prevent replacement of an existing destination. The output has only the
precreation project files, including any older Baselines and their referenced
archive bytes. The new Baseline record itself is not inserted into its own root.

The semantic configuration is retained exactly. Locale and generated path were
excluded from its snapshot and therefore require explicit operational values;
no current project supplies missing history. Configuration is written last.
Every output byte is checked and the model root is independently reconstructed
from the actual output files before success. Failure retains partial output;
there is no automatic cleanup, resume or atomic directory-publication claim.
This API does not provide CLI lookup, comparison, historical full validation,
publication approval or release readiness.

Restoration also rechecks the source archive after reconstructing the output.
A removed destination directory never falls back to the process working directory.
Directories are created exclusively, and every output file retains its original
created inode binding. Foreign initial entries and concurrent replacements fail
without cleanup or overwriting. Late missing source objects retain their exact
object path in the machine-readable failure.

The read-only record/view implementation is separated in `_baseline_view`.
The public archive API and the existing materialization-module view alias keep
the same results, exceptions and write boundaries.


`ComparisonSourceSnapshot(root, kind='baseline', reference=baseline_id_or_bytes)`
registers the verified historical whole-project snapshot in the existing source
registry. A Baseline ID reads its canonical record path; explicit bytes support
archive-only roots. Neither mode reads current configuration or artifact files,
uses Git or materializes a temporary project. The source binding includes owned
record/root/object hashes and explicitly retains the limited comparison scope.

`compare_baselines(before_root, before_reference, after_root, after_reference)`
uses the same `compare_sources` / `compare_semantic` contract. Optional timing
bounds and configuration IDs use the existing semantics. Stored earlier Baseline
records are compared as artifacts; their verified content-addressed objects stay
byte-bound without becoming a separate opaque-resource delta. Other resource
bytes, including attachments and the language registry, remain opaque: different
inventories fail explicitly. The current local reader does not capture binary
payloads, so mixed local/Baseline comparisons require matching observed resource
inventories. No complete model equivalence or release approval is implied.
CLI/Work dispatch and additional historical scopes remain separate integrations.

Der Vergleichsadapter meldet einen fehlenden, per ID gewählten Record als
`comparison_baseline_record_missing` mit dem kanonischen Recordpfad. Das gilt
auch, wenn er während des Lesens verschwindet; geänderte Recordbytes ergeben
`comparison_source_changed`. Fehlende Objektbytes bleiben während aller
Leseschritte `snapshot_referenced_object_missing` mit dem Archivpfad. I/O- und
Sicherheitsfehler werden nicht in einen erfolgreichen Vergleich umgedeutet.
Nicht unterstützte historische Schemas werden mit dem bestehenden
`unsupported_schema_version` beziehungsweise bei Profilen
`profile_unsupported_schema` abgewiesen. Ein zukünftiger Legacy-Leser muss
seine Originalhash-/Manifestbindung ausdrücklich bereitstellen.

Die Quellenregistry bleibt für alle Quellenarten derselbe Einstieg. Der
Baselineadapter bereitet die geprüften Snapshotbytes vor; die abschließende
Record-/Objektbeobachtung und ihre unveränderbaren Nachweise liegen in einem
eigenen internen Modul. Der gemeinsame semantische Vergleich bleibt unverändert.

## Configured snapshot preparation

A configured `build_baseline_manifest` result stores `configuration_binding`
with the selected configuration ID, revision and the existing effective-chain
SHA-256. Its `effective_configuration` object contains the exact canonical
configuration manifest, including all parent bindings and effective values.
All selected-chain configuration artifacts must themselves be retained in the
scope; otherwise preparation fails with `baseline_configuration_chain_not_retained`.
Applicability and required dependencies use the existing scope services.

`configuration_hash` continues to identify the semantic project configuration.
The model manifest's `configuration_sha256` is the existing combined project/
selected-chain scope hash. These distinct inputs are never substituted for one
another. The exact descriptor and resulting artifact inventory remain in the
same shared model-manifest contract.

The objects may be saved to an external `SnapshotObjectStore` and the selection
can be resolved from those archived configuration records without original files.
This pure preparation API returns inert data. The native project provider also
accepts `configuration_id` in `prepare_working_baseline` and
`build_project_baseline_manifest`. It resolves actual configuration and parent
records, checks applicability and required dependencies, and retains the exact
selected artifact set. The closed native scope also requires all stored relation
targets; other scope kinds and explicit boundary providers remain separate work.
Existing identity reservations are checked against the full project first.
Only archives referenced by retained older Baselines enter the variant snapshot.
The native writer preserves all original working artifacts and applies the
existing complete target-validation and transaction gates.

Historical verification rebuilds the effective selection from archived records,
checks its exact stored object and manifest binding, and reports
`configuration_binding`. Changed current parent revisions, selections or project
files do not affect the stored variant. Missing archive bytes never fall back to
current data. Show, materialization and Baseline comparison use this same verifier;
materialization and comparison evidence retain the checked selection binding.
Other historical scopes, CLI/Work dispatch and installed language packages remain
explicit integrations. Snapshot integrity is not historical full validation or
release approval.

The closed native variant selection is isolated in `_configured_project`;
verification and materialization share the metadata-only role set in
`_snapshot_values`. These internal boundaries preserve the same snapshot bytes,
selection checks, diagnostics and publication contracts.

## Release-Baseline admission boundary

`archive.creation.prepare_baseline_creation(..., baseline_kind='working')`
uses the same saved-plan preparation and native publication contract as
`prepare_working_baseline`, including an optional configuration selection.
An explicit `release` request requires its stored `release_id` and reaches the
closed readiness boundary; it never falls back to a working snapshot.

`assess_release_baseline_readiness(model, release_id=...)` returns an owned
read-only observation of actual stored Release fields. It binds the Release ID,
revision and record hash, and the optional stored evaluation hash. Presence of a
descriptor does not validate its schema, model state, required runs or Evidence.
The report always exposes the unavailable provider, unevaluated readiness and
absent publication/release authority. `require_ready()` refuses with
`release_baseline_readiness_required`; no release plan, object or transaction is
created. Existing inert `build_baseline_manifest(..., baseline_kind='release')`
values remain prepared data without release permission.

M13 must supply the complete stored-selection and readiness contract before
release publication can be enabled. Caller success labels and a general
publication authority are no substitute for that service.

The optional `evaluation` argument to the admission API may repeat the stored
selection only. Non-null selections must be objects. A different external
selection raises `ReleaseBaselineSelectionConflict` (`exit_code=6`); without a
stored selection, external input raises `stored_release_evaluation_required`.
This Baseline boundary does not provide provisional general release evaluation.
The report owns the complete `stored_evaluation` value and its canonical hash;
even an identical external value cannot authorize publication. Structural object
checks do not validate the descriptor's semantics. Working requests reject an
external release selection instead of discarding it.

Stored-selection binding is kept in an internal helper. The public observation
and its closed admission method retain the same values, conflicts and no-write
contract; integrating a real readiness service remains M13 work.

## Baseline capture and Work continuation

`archive.work.BaselineSnapshotTask(model, block_bytes=...)` uses the existing
`InputSnapshotTask` to capture exactly the supplied TargetModel's source files.
`advance(max_units)` retains live progress with reads capped at 65536 bytes.
After sealing, every captured byte must match the owned model; a different
source or root is a `BaselineSnapshotConflict` with `exit_code=6`. The observation
identifies its supplied-input scope and grants no write or completeness claim
about an independently discovered project.

`prepare_working_plan(...)` then returns the ordinary working-Baseline preview.
`prepare_work(registry, ...)` requires successful target validation and returns
the existing inert normative WorkManifest with its original saved ChangePlan.
The caller explicitly persists it using the normal WorkDirectory/CheckpointStore.
`advance_baseline_work(...)` supplies the native Baseline gates to each existing
Work preparation phase. `publish_baseline_work(...)` uses the original Work
transaction, current checks and authority, and replays a confirmed receipt.
The caller still supplies its current model, actor, request ID and authorization.

Capture can be divided across calls in one invocation; it is not itself a
durable checkpoint. Durable continuation begins with the complete WorkManifest.
Planning and the Work codec retain their existing whole-byte memory behavior.
There is no partial Baseline publication, new snapshot store, automatic recovery,
CLI registration or release permission. The adapters do not mark final Work
result delivery completed.
