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

## 4.b.R

`read_field` provides the same static selector validation for embedding callers.
It accepts only the exact owned EvaluationContext type; no callbacks or attribute
resolution are permitted. `require_type` exposes the SRX type boundary without
converting values, with structured SRV110 type diagnostics. Missing cannot be
nested inside JSON data, and no default replaces it. No per-test timeout.

Regression cases cover RFC example pointers, malformed full paths, 10,000-digit
out-of-range indices, raw duplicate keys, 1,400-level paths and expressions,
foreign conversion hooks, immutable copies and relocated portable distributions.

## 4.b.C

Pointer grammar and traversal are centralized in pointers.py; fields.py owns
named-context access. Closed operator-field signatures are shared by the AST
validator. Public names, errors, Missing behavior and all W/R tests are unchanged.

## 4.c.W

Boolean not/and/or and eq/ne/lt/lte/gt/gte now execute through the same SRX entry.
Boolean operands require Boolean, not truthy numbers, strings, null or Missing.
and/or evaluate left to right and stop at their decisive Boolean value, with
empty identities true/false respectively. All AST syntax is validated upfront;
short circuit suppresses evaluation-time errors, not malformed program syntax.
Comparisons evaluate both arguments left to right before applying Missing rules.

If either operand is Missing, eq and all ordering comparisons return false and
ne returns true. Otherwise equality/inequality require the same top-level SRX
kind. Nested kind differences in arrays/objects mean unequal JSON structures.
Booleans are not numbers. Number covers integers and finite floats; mixed numeric
values are compared without casting integers to floats. No locale or Unicode
normalization affects string equality/ordering. Array order is significant.

The expression API remains in-memory, without filesystem or environment lookup.
These operators do not add arithmetic, quantifiers, graph operators, a CLI rule
command, profile composition or an assertion that all SRX requirements are done.

## 4.c.R

Deep equality is iterative as well as expression execution. Instrumented field
access proves stable operand order and that decisive and/or operands prevent
later evaluation; a Missing comparison operand does not skip evaluation of the
other operand. Invalid full AST syntax remains an upfront error in all branches.

Regression cases include all top-level kind pairs, Missing versus each value
kind, all three-Boolean truth combinations, nested Boolean/Number distinctions,
1,600-level comparisons and logical expressions, 601-operand conjunctions,
finite numerical boundaries, malicious hooks and relocated distributions.
