# SRX fields, Missing and type boundaries

## 4.b.W

The Python API supports literal, field and exists. field requires a static named
root and RFC-6901 string pointer, not a URI fragment, relative pointer, filesystem
path, JSONPath or dynamically calculated expression. Empty pointer selects the
root; an empty token selects an empty object key. ~1 and ~0 are decoded once in
that order. Unicode and percent sequences are not normalized or URI-decoded.
In addition to the RFC grammar, SpecRoad rejects exact . and .. tokens under
SR-REQ-0518. Keys merely containing periods remain ordinary object keys.

Valid but absent members, out-of-range array indices, the nonexistent array
member '-' and navigation beyond scalar values produce MISSING. Invalid array
index syntax on an actually reached array is SRV110, not a successful false.
Missing is a nonserializable internal sentinel distinct from null; exists is
false only for Missing. No Boolean conversion or missing-to-null fallback.

Programs and contexts remain owned snapshots. Returned containers are fresh.
SrxProgram.value retains its literal-only meaning; contextual programs need
 evaluate(program, context). Unsupported future operators remain rejected.

This is read-only in-memory evaluation, not a rule engine CLI, file resolver,
profile composer, global item context or a budget/checkpoint implementation.
