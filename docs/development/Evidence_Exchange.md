# Evidence-Import: Vorbereitung und native Veröffentlichung

`12.h.W` bietet `EvidenceExchange`, `map_generic_candidates`, `SarifDocument`,
`SarifMapping` und `map_sarif_candidates` im Core und in der PYZ. Die Aufrufer
übergeben unveränderliche JSON-Bytes und native Requirement-, Test- oder
Verification-Werte. Die APIs lesen keine Dateien und führen keine Programme aus.
Die Vorbereitungen aus `12.i.W/R` ergänzen für JUnit, Generic und SARIF eine
ausdrückliche Importpolicy. Ihre Rückgabe ist kein Evidence-Datensatz.
`12.j.W` ergänzt die unten beschriebene native Veröffentlichung eines Generic-Satzes;
die CLI folgt in den vorgesehenen Importschritten.

## SpecRoad Evidence Exchange v1

`evidence_exchange_schema()` liefert eine unabhängige Kopie des eingebauten
Schemas. Die folgenden Felder sind Pflicht; die strukturierten Objekte sind
geschlossen, ausgenommen das ausdrücklich freie `environment`:

| Feld | Vertrag |
| --- | --- |
| `format_version` | `specroad-evidence-exchange-v1` |
| `producer` | Native Felder `producer_type`, `producer_id` |
| `tool` | Explizite Strings `name`, `version` |
| `run` | `subject_id`, SHA-256 `subject_state_sha256`, namensraumqualifizierte `run_id` mit nichtleerem Präfix und lokalem Teil, getrennt durch `:` |
| `subjects` | Nichtleere Liste nativer Bindungen aus `artifact_id`, `revision`, `artifact_sha256`, `verification_context_sha256` |
| `results` | Liste der unten beschriebenen Messungen; eine leere Liste bedeutet keine Messung |
| `environment` | Deklarierte JSON-Metadaten; keine Übernahme aus der lokalen Umgebung |
| `attachments` | Native Referenzen `path`, `media_type`, `size`, `sha256`; keine enthaltenen oder automatisch gelesenen Nutzdaten |
| `configuration_policy` | `bound` oder `independent`, ausdrücklich deklariert |
| `configuration_hash` | SHA-256; nur bei `independent` auch `null` |

Jede Messung enthält exakt `target_id`, `check_id`, `test_id`, `result`,
`produced_at`, `subject_ids` und `attachment_paths`. Das Ziel ist eine native
REQ-, TEST- oder VER-ID. `test_id` ist eine TEST-ID oder `null`. Check-IDs,
UTC-Zeitpunkte, Ergebnisstrings und Bindungen verwenden die nativen
Evidence-Feldverträge. Unbekannte Ergebnisstrings bleiben unverändert und
erzeugen keine erfolgreiche Verifikation. Mehrere Messungen werden nicht
zusammengefasst.

Subject-IDs und Anhangspfade beziehen sich exakt auf die deklarierten Listen.
Duplikate innerhalb einer Bindung sind ungültig. Anhangspfade müssen sichere,
kanonische relative Projektpfade sein. Eine Referenz prüft weder Existenz noch
Inhalt des Anhangs.

`map_generic_candidates(exchange, targets=[...])` vergleicht jede deklarierte
Subject-Bindung mit den übergebenen nativen Originaldaten: volle Revision,
kanonischer Artefakthash und fachlicher Kontexthash müssen übereinstimmen.
Ziel- und Test-IDs müssen in diesen übergebenen Daten vorkommen. Die Rückgabe
bindet deren Originalbytes und kanonischen Inhalt. Sie behauptet weder
Projektvollständigkeit noch Aktualität gegenüber einem laufenden Repository.
Check-/Test-Slots, Konfiguration und externe Laufidentität werden hier nicht
autorisiert. Insbesondere bleibt `external_run_verified` immer `false`.

## SARIF 2.1.0, initiales Inline-Profil

Das Profil liest Inline-Runs und deren Driver-Daten. Die SARIF-Semantik folgt
der [OASIS-Spezifikation 2.1.0](https://docs.oasis-open.org/sarif/sarif/v2.1.0/os/sarif-v2.1.0-os.html).
Ein Schweregrad bezeichnet keinen erfolgreichen Test. Ein erfolgreicher
Werkzeugaufruf allein belegt ebenfalls kein bestandenes Produktkriterium.

Die R-Prüfungen berücksichtigen die Referenzverträge für Regeln und
Invocations (§§3.27.5–3.27.7, 3.48.6) sowie Baseline und Suppression
(§§3.27.23–3.27.24) derselben OASIS-Spezifikation.

`sarif-mapping-v1` ist eine geschlossene JSON-Zuordnung mit:

- `format_version`, `source_sha256` für die exakten SARIF-Originalbytes,
- `exchange`: ein vollständiges Objekt des obigen Exchange-v1-Schemas,
- `bindings`: explizite Zuordnungen mit `exchange_result_index`, `run_index`,
  `result_index`, `rule_index`, `invocation_index`, `artifact_indices`.

Alle Indizes sind ganze Zahlen ab null. `rule_index` und `invocation_index`
dürfen ausdrücklich `null` sein; `artifact_indices` darf leer sein.
Jede Exchange-Messung wird genau einmal an eine eindeutige SARIF-Result-Position
gebunden. Die Reihenfolge der Zuordnungen bleibt erhalten. Das Mapping muss
keinen erfolgreichen Gesamtlauf behaupten.

Ausgewählte Driver-Regeln müssen zu vorhandenen `ruleId`-/`ruleIndex`-Angaben
passen. Nur ausdrücklich ausgewählte Regeln, Invocations und Artifacts gehen
in die Kandidaten ein. Ihre JSON-Pointer und kanonischen Hashes bleiben
erhalten. Nicht ausgewählte Result-Positionen stehen in `unmapped_results`;
`import_policy_applied` bleibt `false`. Opaque Erweiterungen erzeugen keine
zusätzlichen Messungen. URIs, Kommandozeilen, Umgebungsangaben und Inhalte sind
passive Daten. Es werden keine externen Schemas, Dateien oder URLs geladen.

Das W-Profil erlaubt die expliziten Paare `pass` → `passed`, `fail` → `failed`
und `notApplicable` → `skipped`. Fehlendes `kind` bedeutet gemäß SARIF `fail`.
Andere Paare werden zurückgewiesen. Nicht-Fehler-Kinds dürfen keinen
Fehlerschweregrad tragen. Eine ausgewählte fehlgeschlagene Invocation kann
kein `passed` stützen. Explizit als `pass` gemeldete Daten bleiben dennoch
unbeglaubigte Kandidaten.

Komponentenqualifizierte Rule-Referenzen und ausgelagerte SARIF-Properties
gehören nicht zum initialen Mappingprofil. Ebenso fehlen eigenständige
Anhangsimporte ohne Result-Zuordnung, weitere Kinds und eine umfassende
SARIF-Schemavalidierung. Diese API beansprucht keine vollständige Erfüllung
von SR-REQ-0336/0337; die Anforderungsnachweise bleiben `partial`.

## Grenzen und Fehler

Pro Eingabe gelten 4 MiB UTF-8-JSON, höchstens 10.000 Einträge pro Container,
100.000 Werte insgesamt und Tiefe 64. Die ausgegebene Kandidatenstruktur ist
auf 16 MiB und 100.000 Werte einschließlich Objektschlüsseln begrenzt;
gemeinsam referenzierte Metadaten zählen bei jeder Wiederholung.
Doppelte JSON-Schlüssel, nichtendliche
Zahlen, ungültiges Unicode, nicht unterstützte Versionen sowie unvollständige
Bindungen werden zurückgewiesen. `EvidenceImportError` ist ein strukturierter
`ModelError` mit Code `SRV091` und Exitcode 3; Diagnosen geben keine
Eingabeinhalte aus.

Originalbytes und getrennte Roh-/Inhaltshashes bleiben unterscheidbar.
Ausgaben sind unveränderliche Werte mit unabhängig lesbaren Datenkopien.
Weder boolesche Auswertung noch direkte Konstruktion eines Kandidatenobjekts
stellt Verifikations- oder Schreibautorität bereit. Attachments,
Produktlauf, Konfiguration und Veröffentlichung erfordern spätere explizite
Prüfungen; lokale Konfigurationen und Zugangsdaten werden nicht gesammelt.

## Ergänzungen aus 12.h.R

Die unveränderten W-Formate erhalten zusätzliche Prüfungen für ausgewählte
SARIF-Daten. Regel-ID und Index müssen auch dann zueinander passen, wenn keine
Regel importiert wird. Eine alleinige Regel-ID darf nicht mehrdeutig auf mehrere
Deskriptoren zeigen. Der ausdrücklich gewählte Invocation-Index darf keinen
anderen, im Result referenzierten Aufruf ersetzen. Fehlt die Referenz, gilt bei
genau einer Invocation deren SARIF-Standardzuordnung; diese Prüfung fügt keine
ungewählten Anhänge hinzu. Ein bekannter fehlgeschlagener Aufruf stützt kein
`passed`, auch wenn er nicht als Anhang gewählt wurde.

`baselineState=absent` liefert keine Messung des aktuellen Laufs. Das
konservative Importprofil lehnt außerdem ein `passed` zusammen mit einer
nichtleeren Suppressionsliste ab. Unterdrückte Fehler bleiben Fehler; eine
Suppression erteilt keine SpecRoad-Ausnahme oder Freigabe.

Bekannte Metadatenfelder ausgewählter Results, Driver, Regeln und Artifacts
werden typgeprüft. Artifact-Indizes und vorhandene URI-/Basisangaben müssen
widerspruchsfrei sein. Indizes werden vor Zahlenkanonisierung aus den
Originalbytes geprüft; `0.0`, boolesche Werte und Strings werden nicht als
Ganzzahlindizes umgedeutet. URIs bleiben passive Zeichenketten. Ungewählte
Fremdeinträge erzeugen weiterhin keine Messungen; die API behauptet keine
vollständige SARIF-Schemavalidierung. Unbekannte Eigenschaften bleiben opaque
Daten. Die spätere Importpolicy wird hier nicht vorweggenommen.

Generic-Producer-ID, Werkzeugname/-version, Produkt-ID und Ergebnis dürfen
nicht ausschließlich aus Leerraum bestehen. Andere ausdrücklich deklarierte
Zeichen werden unverändert erhalten. Für übergebene native Ziele gelten
höchstens 10.000 Einträge und zusammen 16 MiB Originalbytes. Ein zu großes
Ziel wird vor erneuter nativer Interpretation zurückgewiesen.

Fehler im eingebetteten Exchange tragen den Pointer-Präfix `/exchange`;
Fehler an den separat übergebenen Zielen bleiben unter `/targets`.
Auch ein Fehler nach gültigen Messungen liefert keinen teilweisen
Evidence-Satz und verändert keine Projektdateien. Die bestehenden
Autoritätsgrenzen, W-Erfolgsausgaben und Statusflags bleiben erhalten.

## Gemeinsame Kandidatenstruktur aus 12.h.C

JUnit, Generic und SARIF verwenden intern denselben Aufbau für Ziel, Ergebnis
und Herkunft einer einzelnen Messung. Formatspezifische Daten bleiben daran
unverändert erhalten. Auch das Einfrieren der Ergebnisbytes, das abgetrennte
Lesen, der kanonische Ergebnishash und die gemeinsamen Autoritätsflags liegen
in einem privaten Modul.

Die öffentlichen Typen, Formatversionen, JSON-Felder, Roh- und kanonischen
Hashbindungen sowie Diagnosen bleiben gleich. Die Adapter behalten ihre
bisherigen Parser, Zuordnungen und Größenbegrenzungen; insbesondere erhält
JUnit dadurch keine zusätzlichen Generic-/SARIF-Grenzen. Die Bereinigung
ändert weder Importpolicy noch Laufprüfung oder Veröffentlichung.

## Originalbindung und erste Importpolicy aus 12.i.W

`prepare_junit_import(document, mapping, targets=[...], policy=..., tool=...,
external_identifiers=...)` verwendet die vorhandene vollständige JUnit-Analyse.
`document`, `mapping` und der optionale Sidecar sind die bisherigen unveränderlichen
Core-Werte. `tool` enthält ausdrücklich deklarierte native Strings `name` und
`version`; eine lokale Installation oder Umgebung wird dafür nicht abgefragt.

`policy` muss genau einen dieser Werte enthalten:

- `abort_import`: Jede Mapping-Diagnose führt zu `decision="aborted"` und einer
  leeren Kandidatenliste. Auch sonst gültige Kandidaten werden zurückgehalten.
- `skip_invalid_with_diagnostic`: Unabhängig gültige Kandidaten bleiben erhalten,
  sämtliche Diagnosen und ungültigen Testcase-Indizes werden ausgewiesen.

`rejected_testcase_indexes`, `withheld_testcase_indexes` und die übernommenen
Kandidaten erklären zusammen jede beobachtete Testcase-Position. Diagnosen ohne
Testcase, etwa eine unbenutzte Mappingzeile mit unbekanntem Ziel, bleiben ebenfalls
sichtbar. Ein fehlgeschlagener Test ist eine gültige fehlgeschlagene Messung und
wird nicht allein wegen seines Ergebnisses übersprungen. Ein leerer Bericht
erzeugt keine erfolgreiche Messung. Ungültige globale Eingaben, beispielsweise
defekte XML-/Mappingbytes oder ein falsch gebundener Sidecar, bleiben unter beiden
Policies Fehler; sie werden nicht still in einen leeren Import umgewandelt.

Die Rückgabe `EvidenceImportPreparation` enthält eine versionierte Provenienz
mit Importformat, Parserprofil, Werkzeugdeklaration, tatsächlicher
SpecRoad-Importerversion und den Größen und Rohhashes von Quelle, Mapping und
gegebenenfalls Sidecar. Mapping und Sidecar tragen zusätzlich ihre kanonischen
Hashes und Formatversionen. Jede übernommene Messung bindet den kanonischen
Hash dieser Provenienz. `original_files` liefert eine abgetrennte Rollenabbildung
auf die unveränderten Bytes; diese Rollen sind keine Dateipfade.

`decision="prepared"` bedeutet nur, dass die ausdrückliche Policy auf die
beobachteten Mapping-Ergebnisse angewendet wurde. Laufbeglaubigung, Projekt- und
Contract-Slot-Prüfung, Freigabe und Veröffentlichung sind damit nicht erteilt.
Die API liest keine Dateien, Umgebungsvariablen oder Uhrzeit und führt keine
Programme aus. Die bestehende Grenze für expandierte Kandidaten gilt auch für
die Vorbereitung. Die Generic-/SARIF-Erweiterung aus `12.i.R` steht unten;
die Strukturtrennung aus `12.i.C` steht im abschließenden Abschnitt.

## Vollständige Datensatzbehandlung aus 12.i.R

`prepare_generic_import(exchange, targets=[...], policy=...)` akzeptiert
`EvidenceExchange` oder originale JSON-Bytes. `prepare_sarif_import(document,
mapping, targets=[...], policy=...)` akzeptiert entsprechend die bisherigen
SARIF-Core-Werte oder deren Originalbytes. Der Bytes-Eingang erlaubt die
Diagnose einzelner unvollständiger Pflichtnachweise, die ein strikt konstruierter
Eingabewert bereits ablehnt. Die bisherigen strikten Parser und Mapper behalten
ihre Verträge; insbesondere liefern sie weiterhin keinen Teilsatz bei Fehlern.

Beide Vorbereitungen prüfen den globalen Vertrag vollständig. Defektes JSON,
fehlende oder ungültige globale Angaben, unsichere Anhangspfade, ungültige
native Ziele, eine falsche SARIF-Quellhashbindung und überschrittene
Ressourcengrenzen bleiben unter beiden Policies Fehler. Fehlende oder
ungültige Pflichtfelder einzelner Ergebnisdatensätze werden dagegen mit ihrer
ursprünglichen Position diagnostiziert. Subject-Bindungsfehler verwerfen nur
die abhängigen Datensätze; eine ungültige unbenutzte Subject-Deklaration bleibt
als Diagnose ohne Ergebnisposition sichtbar und löst bei `abort_import`
ebenfalls den Abbruch aus.

Generic trägt seine expliziten Ziel-/Check-/Test-/Subject-Zuordnungen selbst.
Deshalb bindet der Mappingnachweis das gesamte unveränderte Exchange-Dokument:
`mapping.source_role="source"`, Rohhash, Größe, kanonischer Hash und Formatversion.
SARIF erhält Quelle und Mapping als getrennte Originaldateien mit eigenen
Rohhashes; zusätzlich wird der kanonische Mappinghash gebunden. Beide Formate
übernehmen die ausdrückliche Tooldeklaration des Exchange. Sie authentifizieren
weder den Reporter noch den behaupteten externen Lauf.

Die neuen Vorbereitungen verwenden für jede Quellposition einen JSON-Pointer
in `occurrences`. Kandidaten tragen `source_pointer`; `rejected_occurrences`
und `withheld_occurrences` ergänzen die übernommene Menge lückenlos und
überschneidungsfrei. Jede Diagnose enthält `input_role`, den ursprünglichen
Fehlerpointer und betroffene `occurrences`; zusätzlich verweisen
`result_indexes` auf die ursprünglichen Exchange-Messungen beziehungsweise
`binding_indexes` auf Mappingzeilen. Eine globale Zuordnungsdiagnose ohne
Quellvorkommen bleibt sichtbar. Indizes werden nicht nach Auslassungen neu vergeben.

Generic erkennt widersprüchliche Ergebnisdeklarationen für denselben expliziten
Ziel-/Check-/Test-/Subject-Satz innerhalb des deklarierten Laufs. Alle betroffenen
Vorkommen werden verworfen, auch wenn eines zusätzlich ein anderes ungültiges
Pflichtfeld enthält. Gleiche wiederholte Messungen bleiben einzelne
Vorkommen; die spätere Idempotenzprüfung wird nicht vorweggenommen.
SARIF diagnostiziert ungewählte Quellvorkommen, ungebundene Exchange-Messungen,
ungültige oder mehrdeutige Zuordnungen sowie Fehler ausgewählter Result-,
Rule-, Invocation- und Artifact-Daten getrennt. Eine fehlerhafte doppelte
Mappingzeile lässt keinen benachbarten günstigen Treffer gewinnen.

`abort_import` hält bei jeder Diagnose sämtliche ansonsten gültigen Kandidaten
zurück; `skip_invalid_with_diagnostic` erhält nur die unabhängig gültigen
Vorkommen samt sämtlichen Diagnosen. Fehlgeschlagene Messungen bleiben
fehlgeschlagen. Ein `prepared`-Entscheid kann auch null Kandidaten enthalten
und stellt keinen erfolgreichen Verifikationslauf dar.
Eingaben, ausgeweitete Metadaten und Diagnosen bleiben begrenzt. Die
Vorbereitung greift weder auf Hostdateien, Netzwerk, Prozesse, Uhrzeit noch
Hostkonfiguration zu. Vollständige Lauf-/Projekt-/Slot-Autorisierung,
Anhangspublikation, Idempotenz und atomare Evidence-Erzeugung bleiben den
folgenden Planstellen zugeordnet.

## Trennung von Analyse und Policy aus 12.i.C

Die privaten Analysefunktionen bilden Kandidaten und vollständige Diagnosen,
ohne eine Importpolicy auszuwerten. Die getrennten Policyfunktionen erhalten
diese fertige Analyse und entscheiden ausschließlich, welche gültigen Kandidaten
übernommen oder wegen `abort_import` zurückgehalten werden. Generic und SARIF
teilen dieselbe Entscheidung für Quellpointer; JUnit behält seinen bestehenden
Testcase-Index-Vertrag. Die öffentlichen Adapter binden weiterhin die Originale
und frieren die Entscheidung zusammen mit deren unveränderten Bytes ein.

Die Bereinigung erhält Prüfungsreihenfolge, Fehler und Diagnosepositionen,
Grenzwerte, Provenienz- und Ergebnishashes sowie sämtliche Autoritätsflags.
Die öffentlichen Signaturen, Ergebnisfelder und zulässigen Seiteneffekte
bleiben gleich. Die vorhandenen W-/R-Verhaltenstests werden unverändert verwendet.

## Generic-Satztransaktion aus 12.j.W

`specroad.authoring.evidence_import.preview_generic_import` nimmt ein vollständiges
natives `TargetModel` sowie `source_path`, `policy`, `evidence_ids`, `title`,
`actor`, `planned_at`, `change_plan_id` und optional `configuration_id`, `request_id`
und Host-Gates entgegen. Die Originaldatei muss bereits als expliziter Projektanhang
mit Descriptor und Originalbytes im Modell vorliegen. Das gilt auch für jeden
referenzierten Anhang. Es gibt keine implizite Suche oder Übernahme externer Dateien.

Der erste Writer unterstützt nichtleere Generic-Sätze mit ausdrücklich benannten
Verification-Zielen. Requirements und optionaler Test müssen genau zum nativen
Contract-Slot und zum deklarierten Subject-Satz gehören. Die ausdrücklich gewählte
Konfiguration, Laufidentität und alle Subject-Hashes werden aus den nativen
Modelldaten erneut geprüft. Der Host liefert für jede akzeptierte Beobachtung
eine eigene neue Evidence-ID. Der Import erzeugt selbst keine IDs.

Alle akzeptierten Beobachtungen bilden zusammen einen Change Plan. Jede
`evidence_record`-Operation trägt denselben geschlossenen `import_context`:
`format_version="evidence-import-context-v1"`, `import_format="generic"`,
`source_path`, `source_sha256`, `preparation_sha256` und `policy`.
Der Vorbereitungshash bindet die vollständige Analyse einschließlich
Zuordnungen, Diagnosen und Policyentscheidung. Der Preview gibt diese
Vorbereitung unter `import_preparation` zurück; bei ausdrücklichem Skip sind
Diagnosen und verworfene Quellpositionen damit direkt verfügbar. Die dortigen
passiven Autoritätsflags bleiben unverändert. Abweichende, verkürzte,
umgeordnete oder gemischte Operationssätze werden zurückgewiesen.
Jeder Evidence-Datensatz referenziert das unveränderte Original als Anhang
und bindet dessen Rohhash, die versionierte Importprovenienz, den
Vorbereitungshash, die Policy und seinen Quellpointer in `provenance`.

`import_evidence(saved_plan, model, transaction_id=..., authority=...)` verwendet
den bestehenden nativen Writer mit Lock, Frischeprüfung, Journal und dauerhafter
Receipt. Er veröffentlicht den vollständigen Satz in einer Transaktion.
Subjects, ihre Revisionen und Status sowie vorhandene Anhänge bleiben unverändert.
Ein importiertes `passed` autorisiert weder eine Requirement-Freigabe noch einen
berechneten Gesamtverifikationserfolg.

Ein Retry übergibt denselben gespeicherten Plan und dieselbe Request-ID.
Der bestätigte native Request liefert den ursprünglichen Satz und dessen IDs
ohne neue Planung, ID-Vergabe oder Schreibtransaktion zurück, auch in einem
neuen Core-/PYZ-Prozess. Dies bestätigt den früheren Import, nicht seine
heutige fachliche Aktualität. Neue IDs oder veränderte Operationsdaten
sind kein identischer Retry.

Dieses W-Profil umfasst vorhandene Projektanhänge und Generic. Eingangsreplay
vor einer ID-Vergabe, semantische Duplikate ohne Request-ID, zusätzliche
Fehler-/Crashfälle und die weiteren Formatwriter bleiben Folgearbeiten.
Die Anforderungsnachweise bleiben `partial`; die API startet keine Tests oder CI.

## Eingangsreplay und Fehlerfälle aus 12.j.R

`specroad.authoring.evidence_import.resolve_generic_import_request` erhält eine
native `ProjectSource`, die unveränderten `source_bytes`, `source_path`, `policy`,
`title`, `actor`, `request_id` und optional `configuration_id`. Der Host ruft diese
Funktion **vor** neuer ID-Vergabe und Planung auf. Eine bestätigte native Receipt
mit vollständigem Commitnachweis liefert den ursprünglichen Ausführungsbefund
und den gesamten Evidence-Satz samt ursprünglichen IDs und Auditdaten zurück.
Es wird kein aktuelles TargetModel benötigt. Das Ergebnis bestätigt den früheren
Import, nicht die heutige Aktualität seiner Subjects oder Anhänge.

Quelle und Pfad, im Generic-Original enthaltenes Mapping und Laufkontext,
Importpolicy, explizite Konfiguration und Titel müssen mit dem bestätigten
Request übereinstimmen. Abweichungen unter derselben Request-ID sind
`request_operations_conflict` mit Exit-Code **6**, auch bei Wiederverwendung der
ID einer anderen Operation. Actor- und Requestpolicy werden vor dem Receiptlesen
geprüft; der Actor eines Retry ersetzt nicht den ursprünglichen Audit-Actor.
Die vorhandenen W-Receipts sind ausreichend; es gibt keinen zweiten Receiptstore.

`None` bedeutet ausschließlich, dass keine bestätigte passende Request-Receipt
gefunden wurde. Es erteilt keine Schreibfreigabe. Der gespeicherte Plan wird
weiterhin durch `import_evidence` und dessen erneute Receiptprüfung unter dem
nativen Writer-Lock veröffentlicht. Beschädigte Belege, unsichere Pfade und
widersprüchliche Commitnachweise sind Fehler, keine unbemerkten neuen Requests.
Unsichere Receiptpfade liefern einen maschinenlesbaren Fehler mit Code **7**,
Receipt-Lesefehler Code **5**; beide bleiben unbestätigt und recoverypflichtig.

`specroad.changes.evidence_import.diagnose_generic_import_duplicates` prüft einen
Generic-Satz gegen bereits vorhandene native Evidence-Datensätze, ohne IDs oder
Dateien zu erzeugen. `matches` benennt Kandidatenindex, ursprünglichen
`source_pointer`, `semantic_sha256` und alle passenden historischen Evidence-IDs.
Die Version `evidence-semantic-duplicate-v1` hasht ein kanonisches JSON-Objekt
mit genau `format_version`, `subjects`, `configuration_hash`,
`configuration_policy`, `producer`, `tool`, `run_context`, `result`, `produced_at`
und `environment`. Nur `subjects` wird nach `artifact_id` sortiert; seine kompletten
Bindungen bleiben enthalten. Alle übrigen Werte werden exakt verglichen.
Evidence-ID, Titel, Record-Audit, Herkunftsformat, Importprovenienz und
Anhangsverpackung sind nicht Teil dieser Messungsidentität. Die Diagnose behauptet
weder eine Beglaubigung der Messung noch die heutige Gültigkeit ihrer Bindungen.

Ohne bestätigtes Request-Replay lehnen Preview und nativer Satzplanner einen
historisch duplizierten Kandidaten mit `evidence_import_semantic_duplicate` und
der vollständigen Trefferliste ab. Sie übernehmen keinen Teilsatz und verwerfen
keine Beobachtung still. Gleiche wiederholte Vorkommen innerhalb einer neuen
Quelldatei bleiben getrennte Evidence-Datensätze. Unterschiedliche Ergebnisse,
Läufe, Zeitpunkte, Subject- oder Konfigurationsbindungen werden nicht vereinigt.

Ein fehlgeschlagener Schreibversuch behält Journal und tatsächliche Projektbytes;
er bestätigt keinen halben Satz als Erfolg und startet keinen automatischen Retry.
Bei einem abgebrochenen mehrteiligen Commit gelten die vorhandenen nativen
Recovery-Verträge: Ein unvollständiges Ziel wird ausdrücklich zur vollständigen
Basis zurückgerollt; ein vollständig geschriebenes Ziel wird anhand des Journals
mit den ursprünglichen Receipts abgeschlossen. Erst nach zugehöriger Recovery
und Cleanup wird der alte Request erneut ausgewertet. Ein Prozessabbruch mit
verbliebenem Lock benötigt die ausdrücklich autorisierte, journalgebundene
Recovery-Übernahme. Bereits veröffentlichte Records werden dabei nicht erneut
als neue Messungen angelegt. Subjects und Originalanhänge bleiben unverändert.

Dieser R-Stand vervollständigt den begonnenen Generic-Writer mit vorhandenen
Projektanhängen. Weitere Formatwriter, externe Anhangsübernahme und CLI-Anbindung
bleiben getrennte Folgearbeiten; daraus entsteht kein vollständiger Releasebeleg.
