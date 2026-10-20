# Passiver Evidence-Importkern

`12.h.W` bietet `EvidenceExchange`, `map_generic_candidates`, `SarifDocument`,
`SarifMapping` und `map_sarif_candidates` im Core und in der PYZ. Die Aufrufer
übergeben unveränderliche JSON-Bytes und native Requirement-, Test- oder
Verification-Werte. Die APIs lesen keine Dateien und führen keine Programme aus.
CLI, Importpolicy und persistente Veröffentlichung folgen in den vorgesehenen
Importschritten. Die Rückgabe ist kein Evidence-Datensatz.

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
