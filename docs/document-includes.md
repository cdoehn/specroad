# Document include composition

`specroad.documents.compose_document(model, document_id)` accepts an owned native
`TargetModel` and one exact document ID. It rebinds the snapshot and checks the
complete supplied document structure, section ownership and native relations.
Every `include_document` block must have its one actual `references` relation:
`mode="content"` targets a document and `mode="section"` targets a section.

Before expanding the selected document, the service checks the union of all
stored `contains` edges and include references with the existing iterative graph
cycle checker. This includes other supplied documents, not just the selected
root. A cycle raises `DocumentIncludeCycleError` with reason
`document_include_cycle`, a closed artifact-ID path, relation IDs and the exact
source paths, pointers, original relation data and hashes. Ordinary artifact
references remain passive references and do not become include edges.

`DocumentComposition.data` contains a flat preorder of `occurrences`. The root
has index zero, no parent and depth zero. Every later occurrence has a parent
index, depth, artifact identity/revision and its actual incoming relation.
Contains children follow position, target ID and relation ID. An include expands
its referenced container and descendants. A content include retains a document
container; a section include retains its section container. These are data
ancestry levels, not rendered heading levels or layout rules.

Repeated includes produce repeated occurrences with distinct ancestry. The
`records` map retains one bound record per original artifact identity, and
`source_files` returns a detached map of original source bytes for those records.
No source is copied back into the project, renumbered or revised. Re-evaluation
of changed input produces new bindings while previously returned values remain
unchanged. The traversal and cycle check use no recursive Python frames.

The report binds the full supplied model/input hashes, project scope, structural
assessment, selected document revision and include edges. Its scope is
`supplied_snapshot_document_composition`. It proves structure/include admission
for that supplied snapshot; it does not verify the on-disk inventory, primary
role, every block's payload semantics, whole-project validity or rendering.
Prose, query, table and artifact-reference payloads remain passive data here and
need their own semantic services before rendering. No file discovery, external
include loading, process execution, writes or approval occurs.
