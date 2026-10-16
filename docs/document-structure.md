# Section ownership and document order

`specroad.documents.assess_document_structure(model)` inspects the owned bytes
of a `TargetModel`. It requires exactly one incoming `contains` relation for
every supplied section. Two relations from the same parent still count as two.
Native document/section/block fields, reference identities, relation type pairs
and hierarchy checks run before composition. An invalid input yields findings
and no successful document traversal; no orphan is silently promoted to a root.

The immutable report exposes `structure_valid`, source and canonical record
hashes, the supplied model root, section owners and ordered children. A child's
entry retains its exact stored relation, relation hash, identity and position.
`require_document(document_id)` returns a detached document revision, its root
section IDs and a flat preorder traversal with parent, relation, position and
depth. This represents nesting without recursively copying content records.

Only outgoing `contains` relations determine roots and children. The existing
graph order is numeric position, target ID and relation ID. Equal positions are
legal; repeated content-block occurrences retain their distinct relation IDs.
Source-list and relation-array order do not determine composition. A changed
relation array still changes its actual source binding, even when traversal is
unchanged. The assessment performs no writes or revision changes.

The caller must supply the matching complete inventory. The report does not
attest file discovery, primary-role validity, include expansion, payload
semantics, full model validity, rendering or write authority. In particular, an
empty supporting document can have valid structure without being a primary
specification. The role assessment is separate, and the remaining document
services are still required before complete semantic validation or rendering.

The W tests cover stored ownership, nested traversal, order independence,
position/ID ties, duplicate parents, native missing-target and cycle findings,
field failures, owned observations, actual read-only project input and isolated
Core/PYZ parity. They compare data contracts, not rendered output.

An explicit `scope_descriptor` must be an unconfigured, closed project scope.
Partial, configured, document or specification selectors cannot be presented
as a complete section-ownership check. The descriptor is owned; its acceptance
does not prove actual file-inventory completeness. Omitting it retains the
default supplied-project contract.

Parent-cardinality findings include `incoming_relations`: the actual parent ID,
source path, original relation-array pointer, source hash, stored relation and
relation hash. Diagnostic ordering may differ from array order; each pointer
still identifies the original source occurrence. An orphan has an empty list.
Retired records and repeated edges are not silently removed from this check.

Invalid positions retain native reader/field errors. In particular, the document
field contract requires an integer position even where the generic relation
reader accepts an integral JSON decimal. Tests of that boundary supply the
actual original bytes, without canonicalizing the decimal spelling away first.
Equal integer positions remain valid and use the prescribed identity ties.

The internal composition kernel derives parent and child adjacency directly
from validated native relations. Child lists retain the shared graph key; the
public layer owns scope admission, source validation and immutable report
binding. No independently maintained or persisted composition tree is added.
