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
