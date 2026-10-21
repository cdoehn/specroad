# Code-Referenzen: sichere Quellenbytes

`specroad.verification.read_code_reference(source, reference)` liest einen
validierten `RecordArtifact` vom Typ `code_ref`. Als explizite Quelle dienen
ein nativer `ProjectBoundary` für die Arbeitsdatei oder ein nativer
`GitObjectSource` für den gebundenen Commitbaum. Beliebige Reader-Callbacks
werden nicht akzeptiert. Pfade bleiben projektrelativ; die vorhandenen
Root-, Symlink- und Nested-Project-Grenzen gelten unverändert.

Alle fünf Referenzarten werden getragen: `file`, `line_range`, `text_anchor`,
`symbol_hint`, `generated_artifact`. `CodeReferenceSource.source_bytes` enthält
die unveränderten gelesenen Bytes. Die abgetrennte JSON-Projektion `.data`
(`code-reference-source-v1`) enthält den vollständigen Referenzdatensatz,
dessen ursprünglichen Bytehash, Quellart, Pfad, Byteanzahl, Rohdatei-SHA-256
und `file_hash_matches`. Bei einer Git-Quelle werden auch der tatsächlich
gebundene Commit und Blobhash ausgegeben. `.sha256` bindet die kanonische
Projektion. Der Wert ist unveränderlich und lässt sich nicht als boolescher
Erfolgs- oder Freigabenachweis verwenden.

Gespeicherte `git_commit`-/`git_blob`-Angaben erfordern die explizite Git-Quelle
und müssen exakt zum ausgewählten Commit beziehungsweise Pfadblob passen.
Ein Widerspruch liefert `ModelError` mit
`code_reference_git_commit_mismatch` oder `code_reference_git_blob_mismatch`;
eine Dateiquelle mit Git-Bindung liefert `code_reference_git_source_required`.
Es gibt keinen Fallback auf HEAD oder Arbeitsdateien. Fehlende Dateien,
fehlende Git-Pfade/Objekte, unzulässige Pfade und veränderte Lesebindungen
behalten die Fehlerverträge der nativen Leser; sie erzeugen keinen Hashwert.
Die Git-Quelle verwendet nur die vorhandenen lokalen Git-Leseoperationen.
Arbeitsbaum und Index bleiben unverändert, ebenso die gespeicherte Referenz.

Dieser erste Ausschnitt liest keine Sprache und startet weder Quellcode noch
Compiler, Parser, Language Server oder Indexer. Auswahlparameter und Anker
bleiben unverändert gespeicherte Daten. Ein Symbolhinweis wird nicht aufgelöst
und beweist keine Aktualität. `selection_evaluated`,
`reference_state_evaluated`, `symbol_resolved`, `source_code_executed` und
`write_authorized` sind ausdrücklich falsch. Normalisierung/Relokation nach
H.2 und Zustände nach H.3 folgen in 12.r/12.s; die Consumer-Integration folgt
in 12.t. Die bestehende native Relation `implemented_by` kann bereits von
Capability, Requirement und Decision auf die gebundene `code_ref` zeigen.
