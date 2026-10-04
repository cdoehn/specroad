# Schema catalog – 2.q.C

`schema list --format json` and `schema show <SCHEMA-ID> --format json` are
project-free, read-only bootstrap operations. They never resolve IDs as paths,
URLs or executable plugins. Existing projects, profiles and caches are not read
or modified. The result uses the existing 2.0.0 envelope, with independently
versioned `schema-catalog-v1` and `schema-document-v1` payloads (1.0.0).

The current catalog contains the implemented common, domain and record artifact
schemas, project configuration, result and structured request schemas, the local
SARIF projection and the regular Change Plan schema. Mapping schema
count is zero because no mapping implementation is installed. The SARIF resource
is the local emitted subset, not the complete third-party SARIF metaschema.
Neither its existence nor the serializer enables SARIF on unsupported commands.

`urn:specroad:schema:1.2.0:change-plan` is an `exchange` resource with the explicit
scope `change_plan_fields_only`. The catalog calls the existing
`changes.schema.change_plan_schema()` factory also used by the Change Plan
validator. No copied schema, latest-version alias or execution permission is
introduced. Structural validation does not replace self-hash, operation/result
bindings, live base checks or publication authorization. The Change Plan format
version `1.2.0` is independent of the supported model schema `0.2.0`.

Each entry binds the exact schema ID, independent version, experimental stability,
category, explicit validation scope and SHA-256 of its RFC-8785 canonical schema
bytes. ID lookup is exact: no unversioned latest alias or remote resolver. Full
schema objects are detached JSON values with their local definitions intact.

The existing validators retain additional instance-local semantic checks (for
example reference consistency and path classifications). Exported schemas are
field schemas, never a claim of graph consistency, authorized writes, verified
Evidence or project approval. The common term schema is explicitly incomplete
for term-specific fields. Unknown/missing future schemas are not fabricated.

ProjectConfiguration evaluates the same published field resource after its
existing detailed checks. Command producers and machine serialization evaluate
published result/envelope field schemas. Command request descriptions and catalog
requests use the same ParameterContract definitions. Bootstrap model exports are
loaded lazily so version/help do not import filesystem safety subsystems.

No new Core or development dependency is introduced. Test execution follows
the local `AGENTS.md`; see [Testing.md](Testing.md) for the technical commands.
A target-device apply or the full supported CPython matrix is not inferred from
local validation. This file is not a release record.

## Hardened resource and annotation contract

Schema resources verify canonical bytes, complete local references, vocabulary,
ID/version/category/scope consistency and immutable metadata. Their schema views
are independent data copies. A malformed resource cannot be called "approved".

Descriptions, examples, enum values and legacy-branch deprecation are exported
from the same owning factories as validation. Known defaults document only the
actual existing policy. Defaults never fill missing fields or alter an instance;
examples never execute. Explicit boolean flags still require `true` when present;
no invalid `false` default is advertised. Requirement obligation has no default.
Unknown assertions and remote references fail closed. Dependent positionals use
the same dependency requirements as the structured request binder.

Result schemas contain the present work, stream and process-limit field contracts.
Additional relational and lifecycle checks are still performed by their owning
validators. The test that a structurally valid milestone can still fail a local
relation requirement intentionally demonstrates this boundary.

## Shared resources and boundaries

`schema_identity` owns only identity metadata, including the shared Change Plan
format version, family, exact ID and field-validation scope. The Change Plan
factory retains its public `FORMAT_VERSION` and `SCHEMA_ID` names as imports of
those values. Provider discovery uses the same identity without importing the
Change Plan package; actual schema retrieval still invokes its trusted factory.
`schema_sources` references the
existing validators' trusted resource factories; it contains no duplicated schema
content. `SchemaResource` owns canonical bytes, validates their binding and
supplies both detached schema retrieval and assertion evaluation from those same
bytes. `SchemaCatalog` only selects and projects these resources. There is no
persistent schema cache, project registration or extensible plugin scheduler.

The Clean step does not change schema IDs, defaults, field assertions, examples,
scopes, categories or fingerprints. Later milestones must add actual resources
and validators together, not placeholder schemas. The original 2.q.C product step reached 93/885;
platform evidence, full semantic checks and overall release readiness stay open.

## Change Plan catalog audit

`AUDIT-CONTRACT-02.R` compares the complete current catalog with every existing
standalone schema factory: `artifact_common_schema`, `domain_schema`,
`record_schema`, `configuration_json_schema`, `change_plan_schema`,
`request_schema` for each installed command and `result_json_schema` for each
implemented result (including the envelope and local SARIF projection).
The comparison checks exact resource membership, complete documents and their
canonical hashes. The audit found no additional missing standalone resource.

`operation_schema`, preconditions, Request-ID, diagnostic, language-policy,
parameter and shared field schemas are embedded contracts. Their containing
resources include them, but they have no independent published schema ID.
The storage `ResourceSchema` descriptor and procedural SRX, transaction and
recovery validators are not separately published JSON Schema documents. The
catalog does not invent resource IDs for them or for future exchange mappings.

Only the exact Change Plan ID with format version `1.2.0` is available. Older,
future, model-version and latest aliases remain unknown, as do case changes,
whitespace and fragment/path suffixes. Changing returned nested operations,
local definitions or catalog metadata cannot alter subsequent retrieval,
canonical hashes or validation. All twelve current typed operation branches
remain present and reject unknown or missing operation fields. The metadata
policy stays `change-metadata-v1`; catalog availability grants no write authority.

These checks extend regression evidence without changing the existing factories,
SchemaResource capture or catalog lookup behavior. Requirement records remain
partial; broader semantic checks and platform/release evidence remain separate.
