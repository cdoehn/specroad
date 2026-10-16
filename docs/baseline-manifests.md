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

This W API supports unconfigured resolved scopes with JSON artifact/profile/rule/
mapping resources and exact attachments. Configured scopes and language/archival
providers fail explicitly pending their integration. It writes nothing, obtains
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

The initial integration supports unconfigured whole-project working snapshots.
It preserves canonical normative JSON and exact attachment, IANA registry and
already bound archive bytes. Snapshot objects extend the target project manifest
under `archive_objects`; all archive-free model hashes remain byte-identical.
Every object is staged, independently read back and published before the new
`sealed`/`approved` record. Content-addressed archive creation never replaces an
existing file. Native receipts identify the new record and make an identical
confirmed saved request replayable without another write.

The built-in gates cover the newly prepared Baseline only. Existing approvals,
older Baselines and other semantic subjects still require their trusted complete
providers; a new Baseline cannot certify them. Selected/configured scopes,
installed language package snapshots, a general historical Baseline verifier,
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

The current adapter supports unconfigured closed whole-project snapshots,
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
supported unconfigured whole-project snapshot into a missing absolute path
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
