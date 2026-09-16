# Canonical JSON and full-value hashes

Implemented by plan step `2.j` for SpecRoad 0.2.0. The normative foundation is
RFC 8785, especially sections 3.2.2–3.2.4 and Appendix B:
https://www.rfc-editor.org/rfc/rfc8785.html

## API and trust boundary

`specroad.model.canonical` provides `canonical_json_bytes(value)` and
`canonical_json_sha256(value)` for JSON values, plus `canonical_object_bytes(raw)`
and `canonical_object_sha256(raw)` for original UTF-8 object bytes. Optional
`path` is diagnostic context only; no helper reads or writes that path.

Only exact built-in `dict`, `list`, `str`, `int`, `float`, `bool` and `None`
are accepted. Custom mappings, tuple/set/generator, Decimal, conversion hooks,
non-string keys and lone surrogate codepoints are rejected. Shared children
are allowed; active ancestor cycles are rejected. Inputs must be owned and
not concurrently mutated by their caller. The encoder uses iterative frames;
it does not introduce a recursive walk through deeply nested in-memory values.
The existing raw JSON parser keeps its own safety/recursion boundary.

The returned digest is exactly SHA-256 of RFC-8785 UTF-8 for the entire supplied
value. No prefix, wrapper, implicit field exclusion, default, array sorting or
Unicode normalization is applied. Arrays retain order; object keys use UTF-16
code-unit ordering. Canonicalization emits no BOM, trailing newline or layout.
That exact byte sequence is an integrity contract, not a human presentation.

A full-value hash includes revisions, audit fields and even a supplied
`content_sha256` field. Application-specific hashes must first form their exact
specified projections. This step does not implement model roots, relation-review
context projections, verification contexts, manifest domains or self-hash
exclusions. A caller must never label a full-value digest as one of those domains.
Likewise, an original-file byte digest remains a separate transport/provenance
binding: whitespace changes can alter it without altering canonical values.
Existing developer-evidence hashes are not silently migrated by this patch.
No hash is a signature, proof of origin, review decision or write authorization.

## Numbers

The supported Core runtime is CPython with binary64 floats. Its shortest-roundtrip
float significand is formatted using ECMAScript's fixed/scientific thresholds,
not Python's default JSON formatting. Negative zero becomes `0`; nonfinite
numbers fail. No Decimal-context arithmetic or locale-aware formatting is used.

An already-created Python float has already lost any original source-token
precision; no serializer can recover that token. External object bytes therefore
must use the strict raw-object helpers. They apply the existing SpecRoad decimal
roundtrip policy before hashing. For example, `0.1` is accepted, while
`1.0000000000000001` and `1000000000000000128` are rejected as source numbers.
Large values with the same canonical decimal roundtrip (for example `1e23`) are
accepted; this is not an arbitrary absolute 2**53 limit. Python integers are
checked against the same policy. Higher-precision numbers need explicit string
contracts. RFC's introductory overprecise token is tested as an already-parsed
binary64 value and separately rejected by SpecRoad's strict token boundary.

## Implementation and checks

Scalar encoding, iterative traversal, complete-value SHA-256 and original-object
adapters are separate modules. The C commit retains public function names and
all W/R tests unchanged. Human-readable serializers and the colored CLI are
unmodified. The Core gains no third-party runtime dependency.

Versioned RFC number vectors are in `tests/data/jcs-rfc8785-v1.json`. They cover
negative zero, normal/subnormal limits, large finite values, rounding ties and
notation boundaries. Additional behavior tests cover full RFC UTF-8 bytes,
control escapes, UTF-16 key order, NFC/NFD distinction, cycles, private hash state,
lossless input, unchanged artifacts and relocated module/Zipapp distributions.
Tests use owned temporary paths and run with the existing pytest-xdist setup.
No terminal/layout/documentation tests or artificial test timeouts are introduced.

An additional external preparation check compared 105,611 distinct finite
binary64 values (seed 8785 plus decimal-boundary neighborhoods) with Node/V8
v22.16.0 on the preparation host, with no differences observed. Node is not a
product or test dependency and is not bundled. This sampled comparison is not
an exhaustive binary64 proof or a supported-platform release certification.
The patch entrypoint runs the repository's full behavior gates on the target;
the successful target run is known only from its returned Result Bundle.
