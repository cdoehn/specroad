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
Encoding-Vermutung oder Ersetzung ungültiger Zeichen. Nicht als UTF-8 darstellbare
dekodierte Auswahlzeichen liefern ebenfalls `code_reference_decode_failed`.
Die H.3-Zustandsentscheidung folgt in 12.s.

## Exakte Auswahlposition und Ankerprofil

`specroad.verification.locate_code_selection(source)` arbeitet ebenfalls nur
auf einem gebundenen `CodeReferenceSource`. Für `line_range` verwendet es die
gespeicherten inklusiven Start-/Endzeilen und das Encoding. Bei `text_anchor`
wertet es das folgende geschlossene Implementierungsprofil aus:

```json
{"format_version":"code-anchor-v1","mode":"text","start_line":1,"line_count":2}
```

Das ist der Inhalt des Felds `anchor`. `encoding` und `selection_sha256`
stehen weiterhin am `code_ref`. `start_line` ist 1-basiert; `line_count` ist
positiv. Die Endzeile ist `start_line + line_count - 1`. Etwaige zusätzliche
Start-/Endzeilen am Datensatz müssen exakt damit übereinstimmen. Normalisierung
und Auswahlhash folgen H.2; der Suchraum besteht ausschließlich aus vollständigen
Fenstern dieser Zeilenanzahl, einschließlich vorhandener LF-Enden.

Das ausdrückliche Byteprofil benötigt kein Encoding und normalisiert nichts:

```json
{"format_version":"code-anchor-v1","mode":"bytes","start_byte":0,"byte_count":4}
```

`start_byte` ist ein nichtnegativer, 0-basierter Offset; `byte_count` ist positiv.
Der Bereich ist halboffen `[start_byte, start_byte + byte_count)`. Jeder mögliche
Byteoffset, auch in überlappenden Fenstern, wird berücksichtigt. Top-Level-Encoding
oder Zeilenpositionen sind in diesem Profil widersprüchlich und werden abgewiesen.
Zahlen müssen ganze Zahlen sein, keine Booleans. Andere Profilfelder sind ungültig.

Vorhandene freie Ankerobjekte bleiben unverändert les- und speicherbar. Der Locator
interpretiert sie nicht automatisch: eine fehlende oder unbekannte Profilversion
liefert `code_reference_anchor_unsupported`. Fehler im bekannten Profil liefern
`code_reference_anchor_invalid`, widersprüchliche zusätzliche Positions-/Encoding-
Angaben `code_reference_anchor_conflict`. Ohne Encoding liefert ein Textanker
`code_reference_encoding_required`. Dies ist keine implizite Datenmigration,
kein Regex-/Symbolresolver und keine automatische Wahl eines Encodings.

Der unveränderliche `CodeSelectionLocation` enthält in `.data` die Projektion
`code-selection-location-v1`, gebundene Quelle und erwarteten Auswahlhash sowie
die gespeicherte Position und deren beobachteten Hash, soweit vollständig vorhanden.
`selection_result` ist genau einer dieser Werte:

- `stored_position`: Die gespeicherte Auswahl stimmt; weitere Vorkommen ändern
  das nicht. `search_performed` ist falsch, `match_count` ist unbekannt (`null`).
- `relocated`: Die gespeicherte Auswahl stimmt nicht oder ist nicht mehr
  vollständig vorhanden, und genau ein anderes Fenster stimmt. `new_position`
  berichtet seine Position. Die gespeicherte Referenz wird nicht geändert.
- `selection_missing`: Kein vollständiges Fenster stimmt; `match_count` ist 0.
- `selection_ambiguous`: Mehrere Fenster stimmen; `match_count` enthält deren
  tatsächliche Anzahl. Es wird keine Position bevorzugt.

Nur die ersten beiden Ergebnisse enthalten `selection_bytes`, deren SHA-256
und eine `matched_position`; sonst sind diese Werte `null`. `new_position`
ist ausschließlich bei `relocated` gesetzt. Ein leerer oder verkürzter Bereich
wird niemals als Ersatz gehasht. Ein passender Rohdateihash ersetzt keinen
passenden Auswahlhash. Ungültiges Encoding und Dekodierungs-/UTF-8-Fehler liefern
dieselben Fehlerklassen wie die gespeicherte Zeilenauswahl, keine fehlende Auswahl.

`.sha256` bindet die kanonische Projektion; `.data` ist abgetrennt und der Wert
ist nicht boolesch auswertbar. `selection_evaluated` und `relocation_evaluated`
sind wahr. `reference_state_evaluated`, `symbol_resolved`, `source_code_executed`
und `write_authorized` bleiben falsch. Die disjunkte H.3-Zustandsentscheidung
und Consumer-Integration folgen in 12.s/12.t. Die Suche hält die Quelle und bei
Text eine normalisierte Kopie samt Zeilengrenzen im Speicher; sie führt keinen
neuen Streaming- oder Ressourcenbudgetvertrag ein.

Die privaten Bausteine `_code_selection_hash.py` und `_code_selection_cursor.py`
trennen Dekodierung/Normalisierung und Auswahlhash von Zeilengrenzen und
Fensterdurchlauf. Der Suchcursor liefert Kandidaten einzeln in der bisherigen
Reihenfolge und zählt weiterhin überlappende Fenster; er materialisiert keine
zusätzliche Liste aller Auswahlen. Die gespeicherte Zeilenauswahl prüft weiterhin
zuerst das vollständige Bereichsende und kodiert erst danach den ausgewählten
Text. Die öffentliche API behält Zulassungsprüfungen, Ankerprofil, Fehlergründe,
Vorrangregeln und Ergebnisprojektionen. Es entsteht keine weitere I/O- oder
Statusentscheidung.

## Disjunkter Codezustand nach H.3

`specroad.verification.assess_code_reference(source, reference)` bewertet einen
validierten `code_ref` an einer expliziten nativen Dateiquelle oder einem bereits
gebundenen Git-Commitbaum. Der erste zutreffende H.3-Fall entscheidet: Ein fehlender
Pfad ergibt `missing` mit `target_missing`; bei `file` entscheidet der Rohdateihash
zwischen `current` und `stale` mit `file_changed`. Bei Zeilen-/Ankerreferenzen wird
die vorhandene exakte H.2-Auswertung verwendet. Ein Treffer an der gespeicherten
Position ist immer `current`, auch bei weiteren Vorkommen oder Änderungen außerhalb
der Auswahl. Bei geändertem Rohdateihash wird dann zusätzlich
`file_changed_outside_selection` berichtet. Genau ein anderer Treffer ist
`relocated`; kein Treffer ist `stale` mit `selection_missing`, mehrere Treffer
sind `stale` mit `selection_ambiguous`.

Der unveränderliche `CodeReferenceState` liefert eine abgetrennte `.data`-Projektion
(`code-reference-state-v1`, Scope `code_reference_state_only`). Sie bindet den
ursprünglichen Datensatz und seinen Bytehash sowie vorhandene Quellen- und
Auswahlberichte samt deren Hashes. `state` enthält genau einen Zustand, `reason`
den fachlichen Grund oder `null`; `new_position` ist nur bei `relocated` gesetzt.
Fehlende Pfade haben `target_present: false` und keine Quellen-/Auswahlhashes.
`.sha256` bindet die kanonische Projektion. `reference_state_evaluated` ist wahr;
`selection_evaluated` gilt nur bei tatsächlich ausgewerteter Auswahl. Symbolauflösung,
Quellcodeausführung und Schreibfreigabe bleiben falsch. Weder die Position noch
andere Daten der gespeicherten Referenz werden automatisch geändert. Der Wert
ist kein boolescher Freigabenachweis.

Fehlende Dateipfade werden mit einem ausdrücklich optionalen Deskriptor-Probezugriff
beobachtet. Dieser prüft die vorhandenen Eltern, die Projektroot und die Abwesenheit
erneut. Ein nachträglich verschwundener oder erschienener Eintrag, Symlinks,
verschachtelte Projekte und Lese-/Berechtigungsfehler liefern keinen Zustandsbericht.
Vorhandene Dateien werden anschließend durch den unveränderten nativen Byte-Leser
gebunden. Der bisherige `read_code_reference`-Fehlervertrag bleibt erhalten.
Die Git-Beobachtung bleibt an die ursprüngliche Root-/Objektspeicherbindung
gebunden; es gibt keinen Ersatz durch HEAD oder Arbeitsdateien.

Die Auswertung entscheidet vorhandene `file`, `line_range` und die ausdrücklichen
Text-/Byteanker aus `code-anchor-v1`. Freie Bestandsanker und fehlerhafte Encodings
bleiben Fehler. Vorhandene `symbol_hint`-/`generated_artifact`-Referenzen liefern
`code_reference_state_kind_unsupported`; ein Hinweis oder Rohdateihash allein
begründet keine Aktualität. Fehlende Pfade haben nach H.3 auch bei diesen Arten
Vorrang. Die Consumer-Integration folgt in 12.t. Dies ist keine neue Freigabe-,
Release- oder vollständige Validierungsprüfung.

`GitObjectSource.read_optional_bytes(path)` ergänzt die Beobachtung einer bereits
gebundenen Quelle. Es prüft den gebundenen Commit, den Wurzelbaum, die Bäume im
angeforderten Pfad und den regulären Zielblob. Dazu fragt der native Git-Leser
jeweils ausschließlich die vollständige Objektkennung über `cat-file --batch`
ab. Nur die eindeutige Protokollantwort für genau diese fehlende Kennung bedeutet
Abwesenheit. Vorhandene Objekte müssen Typ, Byteanzahl, vollständige Antwort und
den hashgebundenen Originalinhalt erfüllen. Ein nicht vorhandener Commit, Baum
oder Blob ergibt `None`; die H.3-Auswertung berichtet dann `missing` mit
`target_missing` ohne Quellen- oder Auswahlhash. Fehlende Pfade werden ebenso
behandelt. Unsichere Eltern, Gitlinks, Symlinks und verschachtelte Projekte sind
Fehler, auch wenn der angeforderte Kindpfad nicht im Baum steht.

Fehlerstatus, stderr, beschädigte Objekte, unvollständige/widersprüchliche
Protokollantworten und Prozess-/Berechtigungsfehler werden nicht zu Abwesenheit
umgedeutet. Alle vorhandenen Git-Sperren gegen Fetch, Ersatzobjekte, Hooks und
indirekte oder ausgetauschte Objektspeicher gelten weiter. Erfolgreiche vorhandene
Quellen werden anschließend über den bisherigen Code-Byte-Leser exakt an den
Datensatz gebunden. Widersprüchliche Commit-/Blobangaben bleiben Fehler. Die
Konstruktion einer nativen Git-Quelle sowie `read_bytes` und `read_code_reference`
behalten ihre bisherigen strikten Verträge; die optionale Beobachtung erzeugt
keine Git-Leseberechtigung aus einer fehlgeschlagenen Quellenkonstruktion. Der
Bericht belegt die beobachtete gebundene Quelle, keine atomare Git-/Dateisystem-
Transaktion und keine automatische Wiederholung eines fehlgeschlagenen Lesens.
