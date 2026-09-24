# Shared loaded-model validation (4.o)

`specroad.validation.validate_model` accepts immutable `ModelDocument` values
(logical source label and exact bytes), an explicitly composed `EffectiveProfile`,
an optional nonempty ID selection, and explicit trusted `ModelGate` instances.
It reads no files, executes no external tools and changes no inputs. The source
label is diagnostic data, never a path to open. There is not yet a validate CLI.

All supplied sources undergo parsing, full existing type-field schemas, identity
and reference checks. The pipeline reuses Core readers, the relation matrix,
canonical symmetry validation, hierarchy checks and profile/minimum rules. A
narrow selection still checks the structure of all provided sources: malformed
outside data must not hide incoming dependencies. Semantic subjects are expanded
conservatively along both directions of stored and declared field references and
along registered gate dependencies. This can include more than a minimal closure.

Specialized validators are REQUIRED when applicable. Current evidence, sealed
baseline integrity, historical lifecycle legitimacy, current reviews, language
policy, full document semantics, external-resource integrity and configuration
resolution are not certified by their field schemas. Missing hooks return
`unavailable`; missing profiles do likewise. No passed stubs are installed.

A gate is explicitly supplied trusted Python, not an extension loaded from JSON.
Dependency observations must name all applicable source IDs, including empty
lists, and checks must cover all scoped subjects. Both carry a SHA binding to
sources, profile, selection, gate/version and phase. Incorrect/stale/incomplete
returns and exceptions do not produce success. The dispatcher is not a sandbox
for malicious trusted callbacks and does not authenticate their external inputs.

`model_valid` is false for an observed blocking failure, null for otherwise
incomplete checks, and true only if all applicable stages passed (or are genuinely
inapplicable). It concerns the supplied loaded model, not filesystem completeness.
`approval_granted`, `write_authorized`, `project_files_verified` and
`atomic_snapshot` remain false. Reports preserve individual stages and diagnostics.
A reusable CLI/planner/adapter facade is separate from the later diagnostic UI and
failure-threshold policy. Structural prerequisite failures block semantic gates.

Local gates: only the new validation test files, four workers, no full or serial
suite. The unchanged CI workflow runs the complete suite. Bundle 020 requests
parallel plus serial and the existing comparison on Python 3.10–3.14. The generic
CI observer remains development tooling under tools/, not src/specroad/.

## Right-stage coverage and external bindings

Known field references (interface endpoints, verification subjects and slots,
evidence subjects, configuration parents, review endpoints, provenance and waiver
reviews) join the stored relation graph. The semantic scope expands in both
directions; a missing field target never counts as valid structure. The current
checker does not parse arbitrary prose or extension strings for references.

A gate can additionally carry `resources_sha256` for its explicitly captured
external inputs; this digest participates in the per-call binding. It is provided
by the trusted caller, not derived by opening files or authenticated by this API.
A changed digest, source byte, selection, profile or phase invalidates reuse.

Gate diagnostics cannot name an artifact outside their checked subjects. Callback
failures are sanitized rather than leaking arbitrary exception content. A report
raises on implicit Boolean conversion: callers must inspect `report.passed`,
`report.complete`, individual stages and actual diagnostics. Missing validators
are never resolved with no-op default callbacks.

## Clean-stage structure

`values.py` owns immutable source, gate and result contracts. `_model_checks.py`
owns the single Core applicability policy and known field-reference expansion.
`core.py` orchestrates the existing structural validators and registered semantic
services. All integrations call the same `specroad.validation.validate_model`
facade; they must not implement independent success or missing-gate rules.

These boundaries do not add a CLI command or install dummy specialist validators.
The product validation package contains no CI polling or evidence transport code;
the existing development observer under `tools/` is unchanged.
