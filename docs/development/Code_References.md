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

## Gespeicherte Zeilenauswahl nach H.2

`specroad.verification.select_code_lines(source)` wertet die gespeicherte
`line_range` eines vorhandenen `CodeReferenceSource` aus. Die Funktion arbeitet
auf dessen eigenen Originalbytes; sie öffnet keine Datei erneut und bestätigt
keine zwischenzeitlich geänderte Quelle. Andere Referenzarten werden mit
`code_reference_line_range_required` abgewiesen.

Die vollständigen Bytes werden strikt im gespeicherten Encoding dekodiert.
CRLF und CR werden zu LF normalisiert. Nur LF trennt danach Zeilen; andere
Unicode-Trennzeichen, ein BOM gemäß dem gewählten Encoding, kombinierende
Zeichen und vorhandene abschließende Zeilenumbrüche bleiben erhalten.
Start und Ende sind 1-basiert und inklusiv. Ein abschließendes LF erzeugt
keine zusätzliche leere Zeile; eine leere Datei hat keine auswählbare Zeile.
Die UTF-8-Bytes der ausgewählten Zeilen einschließlich ihrer vorhandenen
LF-Enden bestimmen den Auswahl-SHA-256. Änderungen außerhalb dieser Auswahl
heben einen passenden Auswahlhash auch bei verändertem Rohdateihash nicht auf.

Der unveränderliche `CodeLineSelection` hält diese Bytes in `selection_bytes`.
Seine abgetrennte `.data`-Projektion (`code-line-selection-v1`) bindet den
vollständigen Quellenbericht samt `.sha256`, Encoding, Position, vorhandene
und ausgewählte Zeilenanzahl, erwarteten und beobachteten Auswahlhash sowie
`selection_hash_matches`. `.sha256` bindet die kanonische Projektion.
`selection_evaluated` ist wahr. `relocation_evaluated`,
`reference_state_evaluated`, `symbol_resolved`, `source_code_executed` und
`write_authorized` bleiben falsch; der Wert ist kein boolescher Erfolgsnachweis.

Unbekannte oder nicht textbasierte Encodings liefern
`code_reference_encoding_unavailable`, ungültige Eingabebytes
`code_reference_decode_failed`. Ein nicht vollständig vorhandener Bereich
liefert `code_reference_selection_missing`; es gibt keine gekürzte Auswahl,
Encoding-Vermutung oder Ersetzung ungültiger Zeichen. Die Relokationssuche
und Anker-Auswertung folgen in 12.r.R, die H.3-Zustandsentscheidung in 12.s.
