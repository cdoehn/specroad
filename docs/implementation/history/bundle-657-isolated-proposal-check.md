# Bundle 657 — isolierter Proposal-Check

9. November 2026. Geprüfte Quelle `2c9b3357b165abc90ac6d1b2aaf811f42d4a4b8142a100dbb1f540a929ae2470`,
Base-Commit `fb6a43645341bd2f27e31c6f24c3e25c80b757ec`. Bundle 656 hat 18.f.W/R/C mit
9.093, 9.030 und 8.983 bestandenen ausgewählten Tests sauber abgeschlossen.
Der komplette neue Snapshot stimmt byte- und modusgleich mit dem angekündigten
C-Endstand überein. Keine offenen Reststages, keine Wiederholung dieser Commits.

Ein Klärungspräfix [PROPOSAL-CHECK-657](../decisions/proposal-check-657.md)
präzisiert ausschließlich Audit-/Debugbedienung. Danach folgen die vollständigen
realen Stufen 18.g.W/R/C; jede wird erst nach eigenem Apply-Gate committed.
W: lesender CLI-/Request-Befehl, getrennte materialisierte Basis-/Zielkopien,
Vollvalidierung mit vorhandenen nativen Spezialisten, Core-Lint, Query-/Table-/
View-Auswertung, interne Renderer, semantischer Diff und beidseitiger direkter
Impact; Originalinventare bleiben gleich. Hashgebundener Auditbericht und
explizite Debug-Aufbewahrung, keine Statuspersistenz, keine Schreibfreigabe.
R: vollständige Fehler-/Statusfälle, konkurrierende Quellen, unzulässige
Operand-/Optionspfade, passive Shell/Python/URL-Inhalte, Cleanupfehler und
Austausch des privaten Workspace-Inodes. Fremde Ersatzdaten werden erhalten.
Die bestehende vertrauenswürdige RestoreServices-Schnittstelle reicht native
Nachweise aus dem Aufrufkontext an beide Modellprüfungen weiter; fehlende oder
falsche Originalbytes bleiben Fehler, Projektfelder wählen keine Provider.
C: getrennte Module für temporäre Ablage, native Dienste und Auditinitialisierung;
W/R-Testbytes bleiben identisch. Keine neue fachliche Entscheidung in C.

Die Prepared-Stufe W trägt den Zielzähler 748/900 und nächste Position
18.g.R; das gilt erst nach ihrem erfolgreichen Apply-Gate und Commit.
Keine Tests in Dev ausgeführt. Syntax, reine Collection und native Paket-/
Stufenprüfung sind keine Verhaltensabnahme. Pflichtunion enthält alle neuen/
geänderten Tests und relevante native Proposal-/Restore-, Validator-, Lint-,
Query-/Dokument-/Diff-/Impact-, CLI-/Schema-/Request-/Katalog- und Quellgrenzen-
Regressionen; fällige gefilterte N=3-Gruppe kommt je Commit dazu.

SR-REQ-0166–0170 sind erst im vollständigen R/C-Ziel implementiert. Die weiter
reichenden Audit-/Lifecycle-/Offline-Anforderungen bleiben partial. 18.h und
alle weiteren Planpositionen sind offen; kein Review oder Produktabschluss
wird behauptet. Nach atomarer Übergabe endet dieser Auftrag ohne eigene Apply-
oder Resultschleife. Betriebskonfiguration und Testauswahlpolicy bleiben gleich.
