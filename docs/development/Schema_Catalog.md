# Schema catalog – 2.q.W

`schema list --format json` and `schema show <SCHEMA-ID> --format json` are
project-free, read-only bootstrap operations. They never resolve IDs as paths,
URLs or executable plugins. Existing projects, profiles and caches are not read
or modified. The result uses the existing 2.0.0 envelope, with independently
versioned `schema-catalog-v1` and `schema-document-v1` payloads (1.0.0).

The current catalog contains 70 resources: 28 common artifact schemas, 13 domain
schemas, 14 record schemas, 1 project configuration schema, 7 result schemas,
6 structured request schemas and 1 local SARIF projection schema. Mapping schema
count is zero because no mapping implementation is installed. The SARIF resource
is the local emitted subset, not the complete third-party SARIF metaschema.
Neither its existence nor the serializer enables SARIF on unsupported commands.

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

No new Core or development dependency is introduced. Development tests remain
parallel via xdist; C includes a serial reference and bound evidence comparison.
No human output/layout/doc tests and no suite/individual-test timeout are added.
A target-device apply or the full supported CPython matrix is not inferred from
local validation. This file is not a release record.
