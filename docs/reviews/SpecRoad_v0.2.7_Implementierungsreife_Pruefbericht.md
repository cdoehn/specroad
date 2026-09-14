# SpecRoad v0.2.7 — Korrektur- und Implementierungsreife-Prüfbericht

**Prüf-ID:** SR-REVIEW-0.2.7-IMPLEMENTATION-2026-09-14  
**Datum:** 14. September 2026  
**Prüfgegenstand:** Veröffentlichte und anschließend aus Gmail zurückgelesene PDF v0.2.7  
**Zielrelease:** SpecRoad Single-Repository Workbench 0.2.0  
**Entscheidung:** **Technische Freigabe für den Implementierungsstart.**

## 1. Entscheidung und Geltungsbereich

Aus dieser technischen Dokumentprüfung wird die SpecRoad-Spezifikation **v0.2.7 zur Implementierung freigegeben**. Die beiden zuletzt offenen spezifikationsseitigen Befunde B01 und A02 sind geschlossen. Im geprüften Zusammenspiel der Korrekturen mit den allgemeinen Work-, Identitäts-, Ausgabe- und Schreibverträgen wurde kein weiterer Freigabeblocker festgestellt.

Die Empfehlung umfasst den spezifizierten Gesamtumfang, einschließlich Mehrsprachigkeit, strukturierter Verbindlichkeit, generischem Analyzer-Datenvertrag und verpflichtend auszulieferndem py3langid-Adapter. Es ist keine Beschränkung mehr auf vom Analyzer unabhängige Core-Komponenten erforderlich. Eine weitere Spezifikationskorrektur wird aufgrund dieser Prüfung nicht als Voraussetzung für den Entwicklungsstart verlangt.

Das ist eine **technische Reviewentscheidung**, keine im Namen Christians abgegebene menschliche Baseline-Freigabe. Die Anforderungen werden nicht automatisch auf `approved` oder `implemented` gesetzt. Weder die Produktabnahme noch nachgewiesene Crashsicherheit, Spracherkennungsqualität oder Leistungswerte werden erklärt. Der im Dokument vorgesehene gesonderte Freigabenachweis wird durch diesen hashgebundenen Bericht dokumentiert; die bereits versendete PDF wird dafür nicht nachträglich verändert.

Eine solche Freigabe bedeutet ausreichende Implementierbarkeit nach der durchgeführten Prüfung, nicht den mathematischen Beweis, dass jeder denkbare Auslegungs- oder Grenzfall eines 248-seitigen Vertrags ausgeschlossen ist. Neu gefundene echte Widersprüche bleiben nach Kapitel 2.1 zu behandeln.

## 2. Tatsächliche Prüfgrundlage und Reihenfolge

Der Nutzer beauftragte die Umsetzung der Empfehlungen aus dem Implementierungsreife-Prüfbericht v0.2.6, den Versand der neuen PDF und **danach** die erneute technische Prüfung. Die Reihenfolge wurde eingehalten:

1. Die vollständige v0.2.7 wurde aus der vorhandenen Markdown-Satzquelle v0.2.6 mit explizit geprüften Ersetzungen erzeugt; die Zielreleaseversion blieb unverändert.
2. Struktur, Änderungssatz und PDF wurden vor Versand geprüft. Diese Vorprüfung nahm die spätere Freigabeentscheidung nicht vorweg.
3. Die PDF wurde an das über Gmail bestätigte eigene Konto `christian.doehn@gmail.com` gesendet.
4. Die gesendete Nachricht wurde gelesen; Empfänger, Betreff, Dateiname und Anhangsgröße wurden kontrolliert.
5. Der Originalanhang wurde erneut aus Gmail abgerufen. Seine Bytes wurden mit dem vor Versand festgehaltenen Hash verglichen.
6. Erst anschließend wurden Strukturprüfung, PDF-Requirement-Abgleich und sämtliche hier genannten Modellfälle erneut ausgeführt und die Freigabeentscheidung getroffen.

**E-Mail:** „SpecRoad v0.2.7 – Korrekturfassung der Analyzerverträge als PDF“  
**Gmail-Nachrichten-ID:** `1a09f32b5a8ea23c`  
**Gmail-Zeitstempel wie geliefert:** `2026-09-14T09:14:54` (der Connector lieferte hier keinen Zeitzonenoffset).  
**Beginn der Nachversandprüfung in UTC:** `2026-09-14T09:18:11.266342+00:00`  
**Abschluss dieser Reviewentscheidung in UTC:** `2026-09-14T09:22:45.925584+00:00`.

| Datei | Bytes | SHA-256 |
|---|---:|---|
| `SpecRoad_Spezifikation_v0.2.7.pdf` | 919196 | `5a63d018de480d79773e50ec23630832938315a8bc21d53e3ff9f75408ba5137` |
| `SpecRoad_Spezifikation_v0.2.7.md` | 628935 | `128fed57c038ab1af4a3bdbf70d65024c62f09f92866094caf802b8b807bca93` |

Der zurückgelesene Anhang ist **byteidentisch** zur versendeten Veröffentlichungsfassung. Die PDF ist die fachliche Quelle; die Markdown-Datei ist ihre technische Satzquelle. Es wurden keine Inhalte verschiedener Versionen zu einer neuen Prüfgrundlage vermischt.

## 3. Begrenzter Änderungssatz

Alle **730 Requirement-IDs** und ihre Need-, Verification- und Soll-Testfallzuordnungen bleiben erhalten. Es wurden genau sieben bestehende Requirement-Aussagen präzisiert:

| IDs | Korrektur |
|---|---|
| `SR-REQ-0383` bis `SR-REQ-0385` | Receipts, Wiederholung und Idempotenzkonflikte ausdrücklich auf normative Schreibaufträge begrenzt. |
| `SR-REQ-0678` | Vollständigen Identitäts- und Eingangsbindungsvertrag T.3 verbindlich gemacht. |
| `SR-REQ-0691` | Reportpackage bindet sowohl Analysekennung als auch Snapshothash. |
| `SR-REQ-0715` | Analyzerfortsetzung ausdrücklich mit und ohne `--work-dir`. |
| `SR-REQ-0716` | Identische Analysekennung, Request-Snapshot und Engine beim Resume; sonst ausdrücklich neuer Auftrag. |

Begriffsdefinitionen, Kerntypen, Work-Felder, T.3/T.5/T.9, Verifikationen 0046/0048 und der neue Abschnitt 14.12 wurden entsprechend angeglichen. Zwölf gekoppelte Sollfälle R-64 bis R-75 ergänzen Anhang R. Das sind **geplante Produktabnahmefälle**, keine bereits ausgeführten SpecRoad-Szenarien.

Es wurden keine neuen Produktfeatures, Artefakttypen oder Requirement-IDs hinzugefügt. `--analysis-id` schließt die zuvor fehlende Vergaberegel des bereits vorgesehenen Analyzerrequests.

## 4. Befund B01 — automatische Analyzer-Fortsetzung

**Vorheriger Konflikt:** P.2/O.4 erlaubten beziehungsweise verlangten automatische externe Checkpoints bei notwendiger Teilung; T.5 band die Aufbewahrung der Folgearbeit dagegen an ein ausdrücklich angegebenes `--work-dir`.

**Neue Regel:** T.5 übernimmt ohne Analyzer-Ausnahme die Work-Root-Auswahl aus P.2. Ein ausdrücklich gewähltes zulässiges Verzeichnis wird verwendet. Fehlt die Option, erzeugt die Runtime beim ersten notwendigen Checkpoint ein exklusives externes Arbeitsverzeichnis. Kleine vollständig abgeschlossene Aufrufe erzeugen keinen Work-Root.

`continuation_required` mit Exit Code 8 wird erst nach gültiger, dauerhaft und atomar veröffentlichter Checkpointgeneration ausgegeben. Der Aufrufer erhält tatsächlichen Work-Pfad, Work-ID, Analysekennung soweit vorhanden, Checkpointhash, vollständige Restbindung und konkrete nächste Aktion. Es entsteht kein verborgener Prozess- oder Sitzungszustand.

Work-Daten bleiben außerhalb des normativen Projekts und seiner `.specroad/`-Betriebsdaten. Ein erfolgloser Speicherzugriff ist kein erfolgreiches Fortsetzungsresultat. Ist nach sparsamem Versuch weder eine sichere externe Sicherung noch ein sicherer vollständiger Abschluss möglich, gilt der echte Blockervertrag mit Code 5; eine bloße Budgetüberschreitung ist kein solcher Blocker. Bei Code 8 bleiben Checkpoints erhalten, bis der bestehende Bereinigungsvertrag P.9 greift.

Ein automatisch gewählter temporärer Pfad ist keine Sicherung gegen vollständigen Sandboxverlust. Für diesen Fall bleiben Work-Export und tatsächlich extern erhaltene Bytes erforderlich. Damit werden keine verlorenen Daten aus Hashes „rekonstruiert“ und keine unbegrenzten Hostressourcen behauptet.

**Geprüfte Bindungen:** `SR-REQ-0715`, `SR-REQ-0716`, P.2–P.4, T.5, T.9, 14.12. Fundstellen in der PDF: **S. 145, 161–162, 218–220, 240–241 und 244**.

**Ergebnis: geschlossen.** Der explizite und der automatische Start haben denselben fachlichen Fortsetzungsvertrag. Das frühere Flag-Gegenteil steht nicht mehr im Dokument.

## 5. Befund A02 — Analysekennung statt Schreib-Idempotenz

**Vorherige Unterbestimmung:** Das Analyzerfeld `request_id` übernahm sprachlich den vorhandenen Request-ID-Vertrag. Dieser war für normative Schreibaufträge mit Receipts, Akteur und Transaktion definiert. Zugleich sollten Analyzer schreibfrei und teilweise ohne Projekt arbeiten.

**Neue Regel:** Das Feld ist nun ausdrücklich `AnalysisRequestId`, eine Analysekorrelation mit eigenem Namensraum. Nur die zulässige Zeichenkettensyntax wird wiederverwendet. Es werden weder Akteurspflicht noch Operationshash, Projekttransaktion, Write-Idempotenz oder Receipts übernommen.

| Fall | Eindeutiges Verhalten |
|---|---|
| Neuer Request ohne Option | Einmalige Erzeugung von `AN-` plus unabhängigem `random128-v1`-Token vor dem ersten Bearbeitungsschritt. |
| Neuer Request mit `--analysis-id` | Gültigen Wert unverändert verwenden; fehlerhafte Option Code 2. |
| `run --request <FILE>` | Enthaltene gültige Kennung erhalten; fehlende/ungültige Pflichtkennung Code 3; Override durch `--analysis-id` Code 2. |
| `work resume` / `work restore` | Analysekennung erhalten; kein Neuvergeben beim Prozess-/Pfadwechsel. |
| `import`, `show`, `evaluate` | Kennung nur aus gebundenen Daten lesen; keine neue vergeben. |
| Bericht gegen Request | Sowohl Kennung als auch `snapshot_sha256` müssen passen; falsche Paarbindung Code 3. |
| Vorhandener Work-Root | Abweichende Kennung, Snapshot- oder Enginebindung nicht unbemerkt fortsetzen; gebundener Konflikt lässt den bisherigen Stand unangetastet. |

Die Kennung allein ist keine Inhaltsadresse und kein Ergebnis-Cache. Derselbe manuelle Wert in getrennten Aufträgen erzwingt keinen Retry. Die normative Write-Idempotenz bleibt unabhängig bestehen; eine Analyse mit gleichlautender Kennung erzeugt, liest oder verändert deswegen keine fachlichen Receipts.

Auch ein früher Checkpoint während des noch offenen Snapshotaufbaus ist geschlossen: Die einmal vergebene Kennung steht in `normalized_arguments.analysis_id`. Ein noch unvollständiger Request wird nicht als fertig ausgegeben. Später bindet das vollständige Eingangsmanifest den datentragenden Request. Die Work-Felder `actor`, `request_id` und `operations_sha256` bleiben bei Analyzerarbeit ausdrücklich `null`.

**Geprüfte Bindungen:** Begriffe/Kerntypen, `SR-REQ-0383`–`0385`, `0678`, `0691`, `0716`, P.3/P.4 und T.3–T.5/T.9. PDF: **S. 9, 108–109, 141–142, 145, 219–220 und 237–244**.

**Ergebnis: geschlossen.** Vergabe, CLI, Datenformat, Fortsetzung, Berichtspaarung und Seiteneffektgrenzen besitzen jetzt eine gemeinsame nachvollziehbare Auslegung.

## 6. Nach dem Versand ausgeführte Prüfungen

### 6.1 Struktur und Rückverfolgbarkeit

| Prüfung | Nachgerechnetes Ergebnis |
|---|---:|
| Requirements | 730, exakt `SR-REQ-0001` bis `SR-REQ-0730` |
| Doppelte IDs / exakt doppelte Texte | 0 / 0 |
| Fehlende oder ungültige Need-/Verification-/Soll-Testfallzuordnungen | 0 |
| Nicht auflösbare numerische Verweise in den geprüften SR-Katalogen | 0 |
| Need-Matrix | 21 Zeilen korrekt |
| Verification-Matrix | 50 Zeilen korrekt |
| Szenario-Matrix | 46 Zeilen mit gültigen Soll-Testfall- und E2E-Zuordnungen |
| Markdown-Tabellen | 119 ohne Spaltenfehler |
| JSON-Beispiele | 14 syntaktisch parsebar |
| Nicht geschlossene Codeblöcke | 0 |
| Zeilenenden / Dateiende | LF / abschließende Newline |
| PDF-Seiten | 248 |
| Requirement-Aussagen im PDF wiedergefunden | 730 von 730 |

Der PDF-Textvergleich normalisiert NFKC, Leerraum, Markdown-Backticks und weiche Trennzeichen; sonstige Interpunktion und Vergleichsoperatoren bleiben erhalten. Er beweist die vollständige Präsenz der Requirement-Aussagen, **nicht** eine vollständige formale Gleichheit aller Prosa, Diagramme und Layoutdetails.

Die PDF wurde vor Versand mit PDFium vollständig gerendert. Geometrieprüfungen ergaben keine außerhalb der Seite liegenden Textblöcke, keine erkannten Ersatzzeichen und keine nahezu leeren Seiten. Alle sechs Kontaktübersichten und ausgewählte Detailseiten wurden visuell angesehen. Nach Versand wurden insbesondere die entscheidenden veröffentlichten Seiten 238, 240 und 241 erneut gerendert und visuell gelesen. Nicht jeder Satz aller 248 Seiten wurde nach Versand erneut visuell gelesen.

### 6.2 Modell- und Konsistenzfälle

| Gruppe | Bestandene Fälle |
|---|---:|
| Neue v0.2.7-Identitäts-, Fortsetzungs- und Quellenbindungsfälle | 61 |
| Bestehende v0.2.6-Mehrsprachen-/Analyzer-/Zahlenorakel | 88 |
| Bestehende v0.2.5-Lifecycle-/Review-/Bundle-/Restore-Modelle | 75 |
| Bestehende v0.2.4-Entscheidungsorakel | 54 |
| **Summe nach Versand** | **278** |

Die neue Gruppe umfasst unter anderem automatische und explizite Analysekennungen, ungültige Kennungen und Overrides, ID-/Snapshot-Paarung, unveränderte Write-Retries, Code-8-Entscheidung, tatsächlichen Blocker, frühe Snapshotpause und synthetische Einzellauf-/Mehrschrittparität.

Ein Teil der Modelle schreibt echte kleine JSON-Dateien und setzt synthetische Arbeit über getrennte Betriebssystemprozesse fort. Dabei werden derselbe Analyse-Identifier, vollständige erledigte/offene Mengen, intakte Checkpointhashes und unveränderte Test-Projektdateien einschließlich `.specroad/` kontrolliert. Diese begrenzte Dateinutzung macht daraus **keine** End-to-End-Prüfung der künftigen SpecRoad-CLI.

### 6.3 Fachliche Gegenprüfung über die Korrekturgrenzen

Die Prüfungen wurden nicht allein aus „Datei lässt sich parsen“ abgeleitet. Gegenübergestellt wurden ausdrücklich: Analyzer als nicht normativer Befehl versus erlaubte externe Work-Ausgaben; planmäßige Teilung versus harte Hostgrenze; generierte Korrelation versus unveränderte Snapshotprojektion; projekteigene Receipts versus projektlose Analyse; vorhandener Work-Root versus neuer Analyseauftrag; zeitlich früh vergebene ID versus noch nicht fertiges Eingangsmanifest.

Die vorher behobenen Themen zu Lifecycle, negativen Reviews, Bundle-Klassen, nichtrekursiven Manifest-Hashes, Restore, Proposal-Basen, Evidence-Auswahl und SRX-Präzision wurden nicht durch neue pauschale Regeln ersetzt. Die genau sieben Textänderungen und ihre koordinierten Detailverträge sind im mitgelieferten Diff überprüfbar. Die vorhandenen kleinen Regressionsorakel bestehen weiterhin; das ist eine begrenzte Regression, kein neuer Vollbeweis aller früheren Algorithmen.

## 7. Was noch während der Implementierung nachzuweisen ist

Die Abnahmeverträge bleiben vollständig verbindlich. Insbesondere sind ein echter py3langid-Worker mit tatsächlichem Modell, Offlinepakete für die vorgeschriebenen Python-Laufzeiten, Korpustests, Worker-/Pfadsicherheit, reale CPU-/RSS-Messung, vollständige CLI-Workflows, globale Modellregeln und Crash-Injection an echten Persistenzgrenzen noch zu implementieren und auszuführen.

Für diese Prüfung wurden **keine** SpecRoad-Produktbinärdatei, kein echter py3langid-Sprachtest und keine reale CPU-/RAM- oder Crash-Recovery-Abnahme ausgeführt. Die im Dokument festgelegten Zielwerte sind daher weiterhin Sollwerte, keine hier gemessenen Produktleistungen. Die zwölf neuen R-Fälle bleiben bis zu entsprechenden Produkttests offen als Nachweisarbeit.

Diese Aufgaben sind reguläre Implementierungs- und Verifikationsarbeit. Sie sind nicht die Fortführung von B01/A02 als verdeckte Spezifikationsauflage. Ein Fehlschlag der späteren Umsetzung ist über den vorgesehenen Änderungs-/Prüfprozess zu behandeln und darf nicht durch stilles Weglassen von Anforderungen oder nachträgliches Umdeuten eines Tests verdeckt werden.

## 8. Nachvollziehbarkeit und verbleibende Grenzen

Das Prüfunterlagen-ZIP enthält den unveränderten Änderungssatz, Hashbindungen, maschinenlesbare Struktur-/PDF-Ergebnisse, ausgeführte Modellskripte samt Ergebnissen und einen wiederholbaren Prüfaufruf. Die Standards- und Bibliotheksquellen der Vorgängerversion bleiben als deren Provenienz erhalten; für diese eng begrenzte Dokumentkorrektur wurde keine neue externe Recherche oder neue Bibliotheksgütebehauptung verwendet.

Die Modellskripte implementieren keine vollständigen SpecRoad-Schemas und keine allgemeine JCS-Referenzimplementierung. Ihre JSON-Hashhilfen sind nur für die ausdrücklich verwendeten kleinen Fixtures geeignet. Sie testen keine vollständigen Dateisystem-Recoverygarantien, keinen untrusted Analyzer und keine Produktionssicherheit. Auch die Zahl bestandener Fälle ist kein Vollständigkeitsbeweis.

**Abschließende Freigabeentscheidung:** Auf Grundlage der tatsächlichen Nachversandprüfung ist v0.2.7 eine ausreichende technische Grundlage für den Implementierungsstart des spezifizierten Zielreleases. **Offene spezifikationsseitige Freigabeblocker aus dieser Prüfung: keine.** Menschliche Baseline-Governance und spätere Produktabnahme bleiben getrennt.
