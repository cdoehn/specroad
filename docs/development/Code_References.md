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

Die Dateiquelle bleibt während des gesamten Lesevorgangs unter dem nativen
`opened_resource`-Schutz der Anhänge. Vor Rückgabe werden der geöffnete
Dateideskriptor, die Pfadkomponenten und die Projektgrenze erneut geprüft.
Auch eine erst während des Lesens auftauchende `specroad.json` in einem
Elternverzeichnis macht die Beobachtung ungültig. Geänderte Quellen,
Symlinks, Sonderdateien und nicht verfügbare sichere Deskriptoroperationen
führen zu einem Fehler ohne Hashresultat oder automatischen Wiederholungsversuch.
Bereits beobachtete fremde Änderungen bleiben erhalten. Die Datei wird weiter
als vollständiger unveränderlicher Bytewert gehalten; dies ist keine neue
Streaming- oder Ressourcenbudget-Zusage.

Git-Symlinks, Submodule, verschachtelte Projekte, indirekte oder ausgetauschte
Objektspeicher sowie fehlende und beschädigte Blobs bleiben den nativen
M8-Prüfungen unterworfen. SHA-1- und SHA-256-Git-Objektkennungen werden exakt
gebunden; der Git-Blobhash über Header und Inhalt ist vom Rohdatei-SHA-256
getrennt. Arbeitsdateien werden nicht als Ersatz gelesen und fehlende Objekte
nicht nachgeladen. Die Symbol-, Auswahl- und Statusflags bleiben auch bei
passendem Rohdateihash ausdrücklich falsch.

Die privaten Quellenadapter in `verification/_code_reference_sources.py`
kapseln die unveränderten M2-/M8-Leseoperationen und Git-Bindungsprüfungen.
`code_references.py` behält die öffentliche Datensatz-/Quellenprüfung und
die unveränderliche Ergebnisprojektion. Die Quellenadapter werden erst nach
der vorhandenen Zulassungsprüfung aufgerufen und fangen keine Fehler ab.
