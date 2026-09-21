# SRX quantifiers — 4.e

Contract: specification 0.2.7, SR-REQ-0292, Annex B.1–B.4.

`any`, `all` and `none` use exactly `op`, `array` and `where`. The array
expression runs once in the enclosing lexical scope. Each element is then
bound to `item` for its predicate. The four supplied context roots are never
modified. A public context or standalone `read_field` cannot supply `item`.

The current W increment supports one quantifier layer. Nested quantifiers
are explicitly rejected until the R increment; even unreachable malformed AST
is rejected before evaluation. Operator-shaped literal JSON remains data.

Quantifiers visit every element in array order until the first evaluation error.
This follows the B.2 each-element contract, not the separate short-circuit
contract for `and` and `or`. A previously decisive Boolean does not conceal a
later type error. Empty `any` is false; empty `all` and `none` are true. An empty
array does not evaluate its structurally valid predicate. Predicates require
Boolean; Missing, null, numbers and containers are not implicit truth values.

Only owned program/context data is used, without I/O, host state, persistent
item caches, random sources or execution of user-defined conversion methods.
Errors retain SRV110, rule identity and expression JSON Pointer. Resource/work
policies, graph operators and rule-consumer integration are later steps. No
new CLI command, structural budget, checkpoint or writing workflow is added.

Development and bundle gates run the full suite only in parallel (four workers).
The existing GitHub CI template keeps the serial reference and comparison;
no repository is created and no CI execution is claimed here.
