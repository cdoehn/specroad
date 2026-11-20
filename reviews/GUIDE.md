# Contributing a review

This directory is an extensible review system, independent of SpecRoad's
runtime. The first module is the language corpus. Future acceptance tasks
use the same form, result format and summary command, with their own data.
No external JavaScript, framework, server, account or Python package is needed.
Python 3.10 or later is needed to validate results and regenerate the summary.

## Clone, review, contribute

1. Clone the repository. Open `reviews/index.html` locally in a modern browser.
   In its module picker, select `reviews/modules/language-corpus.json`.
   The explicit file picker works offline; there is no fetch or upload.
2. Enter your name and email. These will be public in the result JSON and Git
   history; the form requires your explicit publication consent. Use an address
   you are willing to publish. Identities are self-declared, not authenticated.
3. Select a section and read each original and its criteria. Confirm only what
   you personally checked. Leave other items unreviewed. For a correction or
   rejection, give a concrete reason; an optional replacement is only a proposal.
   Confirm your competence for each section you submit. The source/permission
   item requires an authorized decision with a concrete evidence note.
4. Export your reviewed points as a compact JSON download. Partial reviews and
   multiple reviewers are supported. Keep the file; closing the page discards
   unsaved work. The form can import your own earlier export for continuation.
5. Place the download at `reviews/results/<module-id>/<review-id>.json`, creating
   the module directory if necessary. Use the UUID filename from the download.
   Keep existing contributions. Each contribution is its own small JSON file.
6. From the repository root, run:

   ```sh
   python3 reviews/manage.py validate
   python3 reviews/manage.py summary
   ```

   `validate` reads only. `summary` validates every module and result before
   atomically replacing `reviews/README.md`. Invalid input leaves the previous
   summary intact; neither command changes module data or review results.
7. Review your Git diff, commit the result and regenerated `reviews/README.md`,
   and submit a pull request (or push if you have repository permission).
   Anyone can review a clone; write permission on the upstream is still needed
   to merge a contribution. Concurrent summary changes are resolved by keeping
   both result files and regenerating the summary, not by dropping a review.

The form downloads a file; it does not silently write into a clone. It never
approves all items automatically. Source JSON, not generated HTML or Markdown,
is authoritative. Do not put private credentials, machine configuration or
session identifiers in notes or attachments.

## What the overview means

`accepted` means at least `minimum_reviewers` distinct email identities have
affirmed that exact item and there is no unresolved correction or rejection.
Repeated submissions from the same case-insensitive email count as one
reviewer, but their individual records remain visible. A pending item has no
sufficient affirmative coverage; `changes_requested` means an objection exists.
The maintainers check contributor identity and authority during contribution
review; JSON cannot prove that someone is a language expert or project owner.

The digest binds the original item, its metadata, criteria, module purpose,
provenance, section attestation and reviewer minimum. A change to any bound
content makes older decisions stale. Changing another item does not discard
an unchanged item's valid reviews. The whole-module digest is retained as
provenance; current item bindings decide validity. Stale decisions stay in
history and are listed, but never counted. Correct the module through a
separate reviewed change and obtain fresh reviews of the changed binding.

Review coverage alone never sets a release or adapter success flag. No real
human review is shipped initially. The language module contains 225 AI-authored
candidates, plus one provenance/permission item. Its long/short partitions and
original hashes are preserved. It has not been selected against detector
results, licensed by an invented decision or frozen as an accepted corpus.
T.10's actual language, negative-case, runtime and resource gates remain due.

## Adding another module

Add one compact UTF-8 JSON file to `reviews/modules/<id>.json`. Modules are
passive data: no executable plugin, HTML, expressions, network references or
renderer-specific code. No change to the common UI or evaluator is required.
Use stable IDs; add criteria in data, and use `required_note` for evidence that
cannot be conveyed by a checkbox. A minimal complete example:

```json
{"format_version":1,"id":"example-acceptance","title":"Example acceptance","purpose":"Review the specified deliverable.","source":{"kind":"project","reference":"a recorded version or hash","note":"Describe origin and current limitations."},"minimum_reviewers":1,"criteria":["Check the supplied evidence."],"sections":[{"id":"part","title":"First part","attestation":"I am competent to review these points."}],"items":[{"id":"case-1","section":"part","title":"First check","text":"The exact subject under review.","criteria":[],"required_note":true,"metadata":{"evidence":"reference or hash"}}]}
```

Module IDs use lowercase ASCII letters, digits and hyphens, start with a letter
and have at most 64 characters. Other IDs use ASCII letters, digits, dot,
underscore and hyphen, start with a letter/digit and have at most 80 characters.
Objects have exactly the illustrated fields; metadata is a flat map of strings.
Sections and items have unique IDs and every section contains an item. Criteria
and attestation text form part of each affected review binding.

Format version 1 limits a file to 2 MiB, a module to 5,000 items/100 sections,
the repository to 100 modules/10,000 result files, and a reviewer minimum to
1–100. Ordinary text is at most 8,000 Unicode codepoints; titles/names 160,
email 254 and metadata values 2,000. Inputs must be regular unlinked files
under regular directories. Unknown fields, duplicate JSON keys, invalid
Unicode, non-finite numbers and malformed evidence are rejected.

Results carry `format_version`, a canonical UUID `id`, `module_id`,
`module_sha256`, `reviewer` (`name`, `email`), UTC `created_at`
(`YYYY-MM-DDTHH:MM:SSZ`), explicit boolean `publication_consent` and
`personal_review`, section IDs in `attestations`, and nonempty `decisions`.
Each decision has `item_id`, `item_sha256`, `verdict` (`accept`, `correct`,
`reject`), `note` and `proposed_text`. A nonacceptance needs a reason; a proposed
replacement is permitted only with `correct`. `required_note` applies even to
an acceptance. One result cannot contain the same item twice.

Digests are SHA-256 over UTF-8 JSON with sorted ASCII field names, no added
whitespace, original Unicode and only schema-defined integer values (no floats).
`item_binding` documents the exact closed digest projection. A case's literal
text hash, where present, is separate from its full review binding. A review
never changes the original or counts as permission to apply its proposed text.

Module authors should separate real judgments from machine-checkable claims.
The repository's Apply tests cover JSON contracts, evidence aggregation and
file effects. They do not review language quality or test UI/Markdown layout.

The module records the provenance and limitations at initial preparation. Current
review progress comes only from result files; do not edit a module title, source
note or criteria merely to update progress, since these are bound review inputs.
