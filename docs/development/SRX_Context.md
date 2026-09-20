# SRX foundation: 4.a

The Core API `specroad.srx` accepts the versioned SRX 1.0 JSON envelope from
specification §9.9 / Appendix B. This step evaluates **literal only**. All other
operators fail explicitly until their own plan steps; neither the CLI nor its
capabilities advertise a complete SRX implementation.

`SrxProgram(document, rule_id=...)` owns an immutable copy. `evaluate(program,
context)` returns a fresh JSON value, not an automatically coerced Boolean.
Expression-shaped values inside a literal stay data and are never dispatched.

`EvaluationContext(document, rule_id=...)` requires all four explicit roots:
`artifact`, `configuration`, `project`, `relations`. `item` is not an external
root: quantifiers will provide that scoped binding later. Artifact/project are
JSON objects, relations are already-computed JSON object/array projections.
Active profiles and immutable statistics can be supplied as passive fields of
`project`; no new `profiles` context root or implicit profile composition exists.
Configuration is either explicitly null (no selection) or exactly the
`configuration_id`/`effective_values` projection of Appendix I.3. This validates
representation, not configuration identity existence or resolution correctness.

No files, environment variables, clocks, randomness, imports declared by data,
network or callback resolvers are consulted. Non-JSON Python instances and
subclasses are rejected before conversion hooks. Caller-provided data must be
stable while being captured; afterwards edits to inputs or returned copies do
not affect evaluation. This is not an OS sandbox against hostile Python code.

No project/profile loader, approval, graph evaluator, field operator, full
SRX structure/work-budget engine or writing transaction is introduced here.
Structural and parser failures do not return false or a green rule result.

Test policy: behavioral values and structured error contracts only. No output,
layout or documentation tests and no test/suite timeouts.
