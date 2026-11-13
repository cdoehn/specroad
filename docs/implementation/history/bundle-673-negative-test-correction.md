# Bundle 673 — Testadapter korrigieren, vollständigen 18.j-Rest fortführen

13. November 2026. Quelle ist das native Fehler-Result 672 mit SHA-256
`cfec272180605512e2f724417ad8a66601e0be35b130abb8ae2c3bf37a027c75`.
Der Klärungscommit PROPOSAL-NEGATIVE-672 ist als
`866c9d09992b499bc4abee08a0eb03f85b5570fa` nach 10514 erfolgreichen Tests
abgeschlossen. Er wird weder wiederholt noch geändert. Anschließend scheiterte
18.j.W mit vier Fehlern bei 10412 bestandenen Tests; kein Produktcommit entstand.
Die im erhaltenen Arbeitsstand installierte W-Checkliste ist daher noch kein
abgenommener Fortschritt. Maßgeblich bleiben Commitpräfix und Apply-Log.

Alle vier Fehler liegen in `tests/test_proposal_negative.py`:

- `ReviewCase.decide(actor=...)` erwartet eine Reviewer-ID und erzeugt daraus
  einen menschlichen Actor. Das dort übergebene vollständige Maschinenobjekt
  wurde deshalb fälschlich zu einer Objekt-ID und vor der Sicherheitssperre
  mit Usage-Code 2 abgelehnt. Die drei unveränderten Parametervarianten rufen
  jetzt den nativen Writer mit dem richtigen vollständigen Actor auf. Sie
  verlangen weiterhin Code 7 und nun zusätzlich `human_review_required` als
  konkreten Fehlergrund; der Projektbestand muss unverändert bleiben.
- `CommandResult.result` ist eine unveränderliche interne Darstellung. Der
  JSON-Schemavalidator erwartet das öffentliche JSON-Dokument. Geprüft wird
  deshalb für beide CLI-Eingänge `as_dict()['result']`, ebenso nach der echten
  Publikation. Der Validator, das Schema und der Produktcode werden nicht
  aufgeweicht. Dry-run und die anschließende echte Transaktion bleiben erhalten.

Die Korrektur bindet vollständige Vorherbytes des unsauberen Results. Sie führt
18.j.W, 18.j.R und 18.j.C mit unveränderten IDs, Rollen, Messages und Abnahmen
fort, jeweils mit eigenem N=3-plus-Pflichtauswahl-Gate vor dem Commit. Der erste
Commit umfasst ausdrücklich auch alle bereits ausgebrachten uncommitteten
W-Dateien. R vervollständigt die angekündigten Randfälle; C behält seine reine
Policybereinigung und bytegleiche W/R-Tests. Alle Testidentitäten und Nummern
bleiben erhalten. Spezifikation, Klärungsstand und Budgets bleiben unverändert.

Die ursprüngliche Übergabedokumentation von Bundle 672 bleibt als historischer
Vorbereitungsnachweis erhalten. Dieser Bericht ersetzt ausschließlich ihre
noch offene Ergebnisannahme durch das belegte Fehlerresult und die Korrektur.
Vorbereitete Zähler und Checklisten gelten erst nach dem jeweiligen erfolgreichen
Apply-Gate. Der vollständig erfolgreiche Abschluss von Bundle 673 ist noch offen.
Dev führt nur Syntax-, Collection-, Katalog-, Stage- und native Paketprüfung aus;
keine Testkörper, Fixtures, Test-Unterprozesse, Apply-, CI- oder Dienststarts.
18.k bleibt der nächste eigenständige Planschritt nach erfolgreichem 18.j.C.

Vorbereiteter Zustand: `18.j.R`.
