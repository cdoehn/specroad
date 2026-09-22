# Declarative profiles (4.j)

`specroad.profiles.ProfileResource` loads strict UTF-8 JSON bytes with
`schema_version=0.2.0` and `profile_format_version=profile-v1`. Its `version` is
an exact SemVer; selections are exact `profile_id@version`, not version ranges.
This is an experimental field-resource API, not a composed project profile.

Required declarations: `required_fields`, `forbidden_fields`, `allowed_values`,
`relation_rules`, `lint_rules`, `severity_overrides`; `description` is optional.
Field declarations explicitly select `artifact_types` and `maturities` (empty
maturities means all). Fields are static JSON Pointers. Presence and allowed
values are separate: null is present, and a missing optional field is not made
mandatory by allowed_values. Actual field types still require the Core schemas.

Rules have identities, exact versions and computed canonical hashes. Minimum
relation declarations feed the existing graph rule type. Lint program bodies
are validated SRX programs, not Python/JavaScript/import/callback configuration.
Loading or checking profile fields does not execute lint or a detector. The
program can later be passed explicitly to the existing SRX evaluator.
Severity overrides are declarations for the later composition step; they do
not lower any existing Core check. No profile composition is claimed here.

Distribution resources: `core@0.2.0`, `software-de@0.2.0`, `software-en@0.2.0`.
They restate existing common/domain field obligations and do not invent extra
mandatory software prose or impose one content language. The two software
profiles share their structural rule definitions; language/locale defaults are
not set. The statement rule checks presence only, not natural-language meaning.
`check_profile_fields` reports `profile_fields_only`; it neither runs relation
reviews nor grants approval. Supplying only a software profile does not replace
the mandatory Core layer of a future composed validator.

The canonical resource SHA-256 covers all JSON values. `source_sha256` is the
separate original-byte SHA-256. Neither is an authenticity/signature claim.
The distribution index binds both. Existing resources are never silently
updated. Future project initialization must explicitly write project copies;
loading bundled resources is not a fallback for missing normative project data.

Resources ship in the module tree, Zipapp and package-data configuration. Their
bytes participate in the existing distribution build identity. No new runtime
or development dependency, CLI command, network loader or writer is introduced.

Local gates use selected behavior-test files with four workers; the complete
catalog is collected without test execution. Full tests belong to GitHub CI.
Bundle 014 uses parallel CI only; the next dual-mode bundle is 016.

## Project reads and robust boundaries

`read_profile(source, path, expected_key=..., expected_sha256=...)` uses the
existing ProjectSource path/root/configuration checks. The expected profile
identity and canonical hash are required and compared. Only normative profile
paths are accepted. Original bytes and configuration are rechecked before return;
a missing, corrupted, changed or wrongly bound file is an error, never a reason
to substitute a bundled profile. No project/cache file is created or repaired.
These are repeated read observations, not an atomic multi-file snapshot.

For field evaluation, artifact type and maturity must be explicitly valid, so an
unknown maturity cannot silently skip approval-specific requirements. Missing
field values remain observations, not autofilled defaults. Lint program syntax
is checked even when its declared target selector would not apply to a later
artifact. Code-like content inside a literal remains JSON data. SRX runtime
errors are not evaluated merely by loading a valid declaration.

Profile resource/rule versions use exact SemVer strings. A valid resource version
does not authorize a different schema/format or SRX version. Unknown requests,
range selectors, duplicate resources and incompatible format versions fail;
there is no latest-version selection, alias expansion or network resolution.
The field-resource API does not claim to enforce downstream Core-security
severity protections or merges; that composition belongs to 4.k.

## Module boundaries after 4.j.C

The stable `specroad.profiles` / `profiles.core` facade delegates to:
`_contract` for closed data validation, `values` for original bytes and detached
values, `resolver` for exact selection from supplied resources, and `fields`
for field-only observations. `storage.profiles` is the separate I/O adapter.
No CLI setting is read by the resolver. The three profile resources, their
bindings and the W/R behavior-test files are unchanged by this refactoring.
