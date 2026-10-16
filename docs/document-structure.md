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
