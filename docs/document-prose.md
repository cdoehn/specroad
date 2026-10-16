# Safe prose data

`specroad.documents.parse_prose(block)` accepts a native `ContentBlock` of kind
`prose` or `admonition`. The immutable `ProseContent` owns the original record
bytes and returns detached semantic data. LF normalization affects parsing and
the normalized-text hash only; the stored payload and its source hash remain
unchanged. The result also binds the block, revision, payload and node hashes.

The parser supports paragraphs, emphasis/strong, inline code,
backtick/tilde fenced code, ordered/bullet lists, block quotes, thematic breaks,
and inline attachment links/images. Paragraph text includes soft line endings;
explicit hard breaks use `line_break`. Code and admonition titles are inert
strings. Code-fence info is data, never an interpreter or plugin selection.
Emphasis follows delimiter flanking; code spans take precedence over inline
markup. Syntax reference: [CommonMark 0.31.2](https://spec.commonmark.org/0.31.2/).

Link/image nodes contain a canonical `attachment_path` below `attachments/`,
optional plain title and child label nodes. Escapes/entities are decoded before
the path check; percent decoding occurs once. URLs, absolute/traversing paths,
query/fragment components and residual percent encodings are rejected. Paths
are checked through the existing native project-path guard. The operation
does not open or resolve any attachment and does not attest its existence,
media safety or inclusion in a complete project snapshot.

Raw HTML/autolinks, active character references, prose headings, reference
definitions and indented code blocks are rejected. Code spans/fences retain
their literal contents without evaluating HTML, scripts or include directives.
There is no extension registry, template engine, process launch or network/file
loader. A renderer must consume the typed nodes and escape text; passing a text
or code field to an HTML interpreter would violate this data contract.

The R implementation supports lazy paragraph continuations inside quotes and
lists, including nested containers. Blank lines and closed code fences end the
relevant paragraph context. Indentation uses four-column tab stops while actual
text/code tabs remain literal. Excess list padding follows the block rules;
an indented code block is still outside the declared subset. Unknown entity
names stay literal, backslash escapes take precedence, and decoded text is never
parsed a second time as markup. Multiline reference definitions are rejected.

Foreign include directives are ordinary text, without extension/loader
semantics. Nested links are refused; attachment query/fragment syntax remains
outside the project-path contract. This is not a claim of complete CommonMark
conformance. Inputs are bounded to 1 MiB UTF-8, 64 semantic nesting levels and a
parser work budget; exhaustion is a structured `ProseError`. The budget also
covers repeated bracket/backtick scans and container probes.

`validation_scope=owned_prose_nodes` and `prose_parsed=true` attest only this
parse. Attachment resolution, whole-project validation, rendering, writes and
approval remain false. The passive `ContentBlock` loader and existing search
APIs keep their prior contracts. Document composition and rendering are later
plan steps; no rendered Markdown/HTML bytes are used as automated test oracles.

Internally, `documents._prose_parser` owns bounded block/inline parsing and path
checks. The public `documents.prose` module owns the native-block boundary,
immutable `ProseContent`, source bindings and detached semantic report. Its
existing error type is passed to the parser explicitly. Neither layer emits
Markdown/HTML or grants rendering authority; later renderers consume these data
through their own format boundary. The C split preserves node values, error
contracts, source hashes, resource limits and allowed side effects.
