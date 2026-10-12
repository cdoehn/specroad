# Explicit Git object source

`specroad.query.GitObjectSource(repository_root, reference)` binds raw paths at
the repository root to one resolved commit. `commit_id` is the full object ID;
`paths` is the sorted immutable inventory, and `read_bytes(path)` returns exact
owned blob bytes. A later branch/tag movement does not change the binding.
The working copy need not contain the same files. Missing committed paths fail;
they are never completed from the current working tree.

The private `_git_reader` module owns execution, environment/storage checks and
raw object-hash verification. `GitObjectSource` retains reference selection,
commit/tree inventory binding and resource access. The extracted algorithms and
the public constructor/read methods retain their W/R behavior and source bodies.

Construction is explicit. Importing the query API does not discover or execute
Git. The adapter uses a system Git executable found through the platform's
default executable search path. It needs Git supporting `--no-lazy-fetch`;
missing Git is an environmental failure. Git command/object failures use
`ModelError` reasons without exposing child stderr or source contents.

The command set consists of shell-free argument arrays for `rev-parse --verify
--end-of-options`, `ls-tree` and raw `cat-file` operations. Commit, tree and blob
object hashes are checked. The inventory is reconstructed into raw tree entries
and compared with the verified tree objects, retaining the commit's path-to-blob
binding. The reader never checks out files, changes refs/index, invokes filters,
text conversion, hooks or a pager, or fetches missing objects. Inherited `GIT_*`
redirection/tracing is discarded, global/system Git configuration is excluded,
and optional locks, replacements, protocols and automatic maintenance are disabled.
The work tree is also explicitly bound to the chosen root, overriding local
`core.worktree` redirection. Failure to start Git preserves the OS error number
without publishing an untrusted child filename or diagnostic. A missing Git
executable does not affect non-Git query operations.

Only an ordinary local `.git` directory is currently accepted. Linked worktrees,
alternate/grafted stores, linked/special storage entries, unsafe resource paths,
symlink/gitlink resources and nested project reads are rejected. Git executable
blobs remain data. Raw binary bytes, line endings and Unicode paths are retained.
The child process remains within the explicit repository context; storage/root
boundaries are checked before and after each command.

This W adapter supplies repository bytes, not a validated project snapshot or
write capability. It does not interpret `specroad.json`, combine multiple roots,
validate a complete model, invoke Diff/Work, or grant release approval. Whole
tree inventories and Git-storage checks are materialized; streaming and Work
continuation are not claimed. Common comparison-source resolution, supported-platform acceptance and
broader Git-layout support remain open.

The behavior fixtures build real Git objects as owned temporary data; no Git
write commands run against development or Apply repositories. Independent
oracles compare file bytes, IDs and unchanged refs/index/working/foreign files.

Git contracts: [global options](https://git-scm.com/docs/git),
[revision verification](https://git-scm.com/docs/git-rev-parse),
[tree inventory](https://git-scm.com/docs/git-ls-tree),
[raw objects](https://git-scm.com/docs/git-cat-file) and
[object storage](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects).

R regression includes malformed/ambiguous refs, missing/unusable Git, local
worktree/alias/pager/hook configuration, promisor remotes with missing objects,
inherited config/alternate/trace variables, corrupt trees, indirect/linked/special
Git storage, replacement of a bound Git directory and read-only repositories.
All W oracles remain unchanged; the tests assert bytes, IDs, error contracts and
allowed side effects rather than Git's human diagnostics.
