# Language tags and the bound offline registry

Scope of 2.n: structural RFC 5646 parsing and registration relative to explicit
snapshot bytes. This is not language detection, translation, linguistic lint,
content permission, automatic project initialization, or a write authorization.

`parse_language_tag` preserves the original declaration and offers case-only
normalization separately. `LanguageRegistry.inspect` distinguishes
`invalid_syntax`, `registered`, `private_use`, and `unverified_registry`.
Unknown tags do not become syntax errors. Deprecated tags remain readable;
Preferred-Value metadata is returned, never applied. `zh` and `cmn` stay distinct.
Grandfathered tags use the immutable grammar set, then the bound registry.
Duplicate variants/singletons are structural errors. Variant Prefix advice is
not treated as a hard content allowlist. Extension bodies are preserved, but the
separate extension registry and extension-specific semantics are not bound here:
such declarations are conservatively `unverified_registry`, not falsely checked.
`und`, `mul`, and `zxx` are readable and independently flagged unspecified.

## Frozen data provenance

The bundled snapshot represents the historical IANA File-Date **2023-10-16**.
It is NOT a claim to be the newest registry. All 9,851 records/fields in the
installed `liblangtag-common 0.6.7-1` XML snapshot were re-encoded as IANA-format
UTF-8 text; liblangtag expands reserved ranges into individual records. This is
not a byte-identical download of the IANA original file. The metadata records
the actual source XML SHA-256 and the actual re-encoded snapshot SHA-256. No
synthetic language list was substituted. Tests' small synthetic registries are
separate and never supplied as the distribution registry.

Files: `src/specroad/language_data/registry.txt` and `snapshot.json`.
Snapshot SHA-256: `3016607e64244c05b1ee2f9d469e399377fda86169c6f255bffd995b838c2fd4`.
Source XML SHA-256: `d83cb02c1aa49acedbf0a8028dbb9796526f33da9e211136c6db5ff905d8dc48`.
Upstream: https://www.iana.org/assignments/language-subtag-registry/language-subtag-registry
Standards: https://www.rfc-editor.org/rfc/rfc5646.html (sections 2 and 3).

The distribution reader verifies its declared hash/date/count/validator. Module,
wheel package-data configuration, and portable zipapp retain the same resources.
The build identity includes declarative resource bytes as well as Python files.
This remains a development build, not a completed release gate.

## Projects

`read_language_registry(ProjectSource(root))` loads only the configured managed
`profiles/language-data/...` copy. It checks actual hash and File-Date, file
stability and configuration freshness. Missing/damaged registries do not fall
back to the bundled snapshot or the network. `registry_binding` only returns a
proposed four-field configuration value, without creating files or reserving a
write. The resulting registry is an immutable read observation, not an atomic
snapshot of every project file and not a live automatically refreshed cache.

The later init/Change Plan implementation must materialize or explicitly replace
the bound bytes. Installing another SpecRoad version does not upgrade projects.
Language policies, Basic Filtering, label packages and detector integration
retain their separate plan positions. No new CLI command is advertised here.
