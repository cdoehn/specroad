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
