# Bundle 800 — Korrektur des offenen nativen Authoring-Rests

Datum: 23. November 2026. Grundlage ist das native Fehler-Result
`specroad-apply_Result_054309_1123_1362f6.zip`, SHA-256
`13618ecb18d21670c1add2a354710b6d49efebfd0e600f0b7ef6c2ea62db9ae2`.
Bundle 799 lieferte 26.595 bestandene Tests und 70 Fehlerzählungen
(53 reguläre Fehler und 17 fehlgeschlagene Subtests); keine seiner drei
Stages wurde committed. Der vorher erfolgreiche Klärungscommit bleibt erhalten.

Diese Korrektur führt genau **21.c.W, 21.c.R, 21.c.C** mit ihren ursprünglichen
Rollen `implementation` und jeweils eigenem Apply-Gate vor dem Commit fort.
Sie ergänzt keine normative Entscheidung und keine neue Plangruppe.
Die angekündigten Zielzähler und Checklisten in den Stage-Dateien gelten erst
nach dem jeweiligen erfolgreichen Gate und Commit. Die Vorbereitung ist kein
Erfolgsnachweis für Bundle 798 oder 799.

Korrigiert werden die belegten Ursachen:

- Dokumentkomposition nimmt nur ihre Dokument-/Abschnittskanten auf; die
  vollständige native Hierarchieprüfung einschließlich Plankanten bleibt davor.
- Der JSON-Bericht des Zielzustands serialisiert unveränderliche Plan-Folds als
  JSON-Listen; die Fold-Daten und ihre Validierung bleiben unverändert.
- `view.create` und gespeichertes `change.apply` erhalten das tatsächliche
  Aufrufverzeichnis für relative Eingabepfade.
- Archivierte semantische Projektkonfigurationen behalten ihre native
  Projektversion 0.3; Objektbytes, Manifestbindung, Artefaktversionen und
  zukünftige nicht unterstützte Versionen werden weiterhin geprüft.
- Import-Testprojekte binden Originalattachments an ein echtes synthetisches
  Evidence-Artefakt. Goals erhalten keine unzulässigen Attachmentfelder.
  Importe müssen weiterhin genau die erwarteten neuen Beobachtungen erzeugen
  und alle vorhandenen Originalbytes unverändert lassen.
- Der Schema-Katalogtest umfasst beide nativen Authoring-Ergebnisformate.
  Isolierte `plan_edit`-Operationen bekommen einen eigenen vollständigen
  Schema-/Feldgrenzentest; ihre Vermischung mit generischen Operationen bleibt
  ausdrücklich abgewiesen.

Sechs zusätzliche defensive Fälle werden in R eingeführt und unverändert nach
C übernommen: getrennte Dokument-/Planbäume, ungültige Fremdcontainmentkanten,
beide relativen Eingabepfade bei abweichendem Prozessverzeichnis, vollständige
Baseline-Originalbytes und geschlossene Archivversionsgrenzen. Alle bereits
vergebenen W- und R-Testnummern bleiben erhalten; neue Nummern stehen hinten.
Die bestehenden Pflichtauswahlen und betroffenen Verbraucher bleiben gebunden.

**Abnahmegrenze:** In Dev wurden keine Verhaltenstests ausgeführt. Collection,
Syntax- und Paketprüfung sind keine Verhaltensabnahme. Der aktuelle echte
Analyzer-Messnachweis fehlt weiterhin; `tests/test_analyzer_resources.py`
bleibt unverändert und in jeder Pflichtauswahl. Weder Messungen noch menschliche
Reviews werden ersetzt, übersprungen oder als bestanden markiert. Erst das
nächste native Result kann belegen, welche Fehler tatsächlich verbleiben.
