# Document roles and primary specification

`specroad.documents.assess_document_roles(model)` checks the document records in
an owned `TargetModel` using the existing record-field schema. Under its full
supplied-project contract, exactly one document whose maturity is not `retired`
must have `document_role=primary_specification`. Other active documents use
`supporting`. A retired former primary remains unchanged and is not counted.

The immutable assessment exposes `roles_valid`, the actual source and canonical
record hashes, the supplied model root, field findings and primary cardinality.
`require_primary_document()` returns a detached selection containing the exact
stored `record`, `artifact_id`, `revision`, `path` and `record_sha256`. Missing or
ambiguous primaries raise `DocumentRoleError` with code 3; no first-document or
supporting-document fallback is selected. Invalid document fields retain the
native reason and source pointer. Missing language is already rejected by the
shared model reader before this assessment can be called.

Only supplied bytes are inspected. The report does not attest discovery or
freshness of the files on disk, complete model validation, composition validity,
rendering, approval or write authority. Section ownership, payloads, includes,
views and their semantic providers remain separate plan steps. In particular,
this role assessment does not stand in for the complete `document_model` gate.
The explicit partial/legacy fallback view belongs to 11.q; this full-project API
does not synthesize a primary document or reinterpret a partial inventory.

The behavior tests cover exact stored selection, order independence, all
non-retired maturity values, rejected missing/ambiguous primaries, required
fields, owned reports, unchanged project bytes and isolated Core/PYZ parity.
They do not compare rendered Markdown, HTML or terminal presentation.
