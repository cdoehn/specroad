# Bundle 704 — Create-Testdaten und Testlauf-Overhead

Ausdrücklicher Nutzerauftrag vom 15. November 2026: Die privat vorbereiteten
drei Testlaufoptimierungen aus Dev1 jetzt integrieren. Technische Basis ist
das vollständig geprüfte Fehler-Result von Bundle 703 mit SHA-256
`0adf71ff47d35c99abc91b5b49e8fb6d78f8a9ccc8ea1183b762ae08b8d47c87`.

Bestätigt ist ausschließlich `WRITE-RECEIPTS-703` auf
`302abefc2fdd0f187cd438ffabe0bfaec5ab1121` mit 7.528 bestandenen Tests.
18.t.W scheiterte bei 8.220 Tests mit zwölf Fehlern; W/R/C bleiben offen.
Der erhaltene Arbeitsbaum ist exakt der angekündigte W-Zustand, kein Erfolg.

Alle zwölf Fehler entstehen vor der Publikation aus widersprüchlichen
Create-Testdaten: die neue Goal-Vorlage trägt andere Auditmetadaten als die
im Plan gebundenen ACTOR/TIME-Werte. Die Korrektur setzt ausschließlich bei
den beiden neuen Testartefakten Revision 1 und genau diese Auditdaten.
Der normale Produktionsvalidator, sämtliche Assertions, Test-IDs und die
elf tatsächlichen Prozessabbruchpunkte bleiben erhalten. Derselbe Teststand
wird in R und C weitergeführt; kein erfolgreicher Commit wird wiederholt.
Die ursprünglichen vollständigen 18.t-Gates und Abnahmen bleiben bestehen.

Danach folgt die ausdrücklich beauftragte OFF-PLAN-Gruppe TEST-OVERHEAD:

- W: unveränderte Hostbudgets unter frischer Sperrprüfung ohne Neuschreiben,
  höchstens zwei normale externe Statussnapshots pro Sekunde mit unmittelbarem
  Anfang/Abschluss und Berechnungswiederverwendung je Schedulerentscheidung.
- R: Fehler-, Frische-, Ownerwechsel- und lokale/Proxy-Pool-Abnahmen ergänzen.
- C: die unveränderte Rechenhilfe aus dem Scheduler auslagern.

Diese drei Schritte verändern keine Produktposition. Berechtigungen, live
gelesene Hostvorgaben, durable Start-/Phasen-/Gewinnerbestätigungen und
Laufzeithistorie bleiben erhalten. Queueänderungen verwerfen betroffene
Schätzwerte sofort; jede neue Entscheidung beginnt frisch. Keine Bündelung
von Testfällen oder Datenbanktransaktionen, keine neuen Host-/Workerwerte.
Die technische Bedienung steht in den Entwicklungsdokumenten zu
[Test Control](../../development/Test_Control.md) und
[Remote-Testhosts](../../development/Remote_Test_Hosts.md).

Die private Vorbereitung bringt elf neue Basisfälle in W und zwanzig weitere
Fälle in R ein. Alle alten Testnummern bleiben erhalten. Jede der sechs echten
Stages erhält ihr eigenes gefiltertes N=3-Gate plus vollständige Pflichtauswahl
vor dem Commit. Dev führt ausschließlich statische Prüfung, reine Collection
und native Paketvalidierung aus; kein Verhaltenstest oder gemessener
Geschwindigkeitsgewinn wird behauptet. Die Apply-Abnahme steht aus.

Die fachlichen 18.t-Zielwerte gelten erst nach ihren eigenen erfolgreichen
Gates; danach bleibt 18.u.W die nächste Produktposition. Es gibt keine neue
Spezifikationsklärung oder Budgetänderung und keinen Start der Automatik.
