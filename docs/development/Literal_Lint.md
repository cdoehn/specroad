# Glossary and literal checks — 4.l

These are explicitly selected in-memory library checks, not a new `specroad lint`
command, automatic project discovery, profile composition, or linguistic analyzer.
All public machine-readable results state `selected_literal_fields_only`,
`supplied_terms_only`, `project_complete=false` and `approval_granted=false`.
Modality, contradiction, translation and single-obligation review are unavailable,
including when the selected literal checks have no findings. No text is rewritten.

## Term records and loading

`domain_schema("term")` now extends the common envelope with required nonempty
term/definition, language, synonyms/forbidden_synonyms arrays and owner. Empty
synonym arrays are valid. The same resource is available from the schema catalog.
`DomainArtifact(raw, expected_type="term")` keeps the original bytes and returns
independent data. `read_term_artifact(ProjectSource(...), path)` applies the existing
root, path, type and identity checks, then rereads the original bytes. It writes
nothing. This is not an atomic multi-file snapshot or a write authorization.

## Explicit, versioned library policy

`LiteralPolicy` accepts strict JSON bytes with exactly format_version (integer 1),
policy_id, exact numeric version, language, fields, term_ids, placeholders and
references. `LiteralPolicy.from_value` captures JSON-only values. No Python
callbacks, imports, URLs, regexes or paths are loaded from these values. This
library policy is NOT silently added to persisted profile-v1 or language packages.
The next language/package stages must explicitly adapt their own contracts.

`fields` is a nonempty list of distinct JSON Pointers to actual text values. The
caller is responsible for selecting the normative fields relevant to its scope.
Missing or non-text selections are errors, not an empty successful scan. There
is no automatic recursive search of prose, extensions, source text, or metadata.
Selected extension values can be checked explicitly; their contents are not code.

`term_ids` selects exactly which supplied terms provide forbidden synonym rules.
Missing selected IDs and duplicate glossary identities are errors. Only a term
whose declared language exactly matches the artifact AND policy language is used.
Tag case is ignored; no region fallback, alias, macro-language substitution, or
language detection occurs. Basic Filtering/package resolution belongs to 4.m.

Matching is case-sensitive exact Unicode-scalar substring matching, including
overlapping occurrences. There is no stemming, tokenization, inferred word
boundary, case folding, whitespace conversion or NFC/NFD normalization. Findings
contain JSON Pointer and zero-based [start,end) Unicode-codepoint offsets into
the unchanged field, not invented file-byte positions. SRV053 identifies forbidden
synonyms. Duplicate identical strings in one stored synonym array do not cause
duplicate findings; different term IDs remain distinct.

For approved artifacts SR-REQ-0097 always checks TBD, TODO and FIXME in selected
fields, independently of optional language-specific policy applicability. Matching
custom placeholders are added, never substituted for the Core list. Violations
are SRV033/error; draft and other non-approved records are not reported as violating
this approved-only rule. Unknown prose is not an undefined term reference.

`references` contains explicit {pointer, by} selectors, with by=id or by=name.
This is not a new inline markup syntax. Each selected field is one complete term
ID or one exact preferred name/permitted synonym in the declared language.
Name resolution uses the whole field, not substring matching. Unknown prose,
coincidental ID-shaped text, display IDs and forbidden aliases are not references.
Missing selected references, invalid reference values, language mismatches and
ambiguous names produce distinct SRV053 findings. Multiple aliases of the same
term remain one candidate; ambiguous candidates are sorted and never guessed.
All supplied terms are available for reference resolution; term_ids selects only
forbidden-synonym rules. Reference selection does not load files or resolve URLs.
Empty reference selection is not_configured; inapplicable language is explicitly
not_applicable. Invalid selection syntax fails even when its language would not
apply. No actual language-registry validation or detection is claimed.
A result with no applicable checks has literal_checks_passed=null, not a linguistic
success. No global strict/fail-on decision or lifecycle gate is implemented here.

## Development evidence

Every W/R/C commit runs only its selected files with four xdist workers on Pixel.
The collection preflight checks all catalog identities without executing test
bodies. No full local suite or serial local suite. Bundle 016's final commit
requests both full modes and their comparison in the existing GitHub matrix.
Local selected evidence is not full CI or release evidence.
