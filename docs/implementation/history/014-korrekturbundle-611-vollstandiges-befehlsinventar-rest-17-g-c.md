# Korrekturbundle 611 — vollständiges Befehlsinventar, Rest 17.g.C

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Korrekturbundle 611 — vollständiges Befehlsinventar, Rest 17.g.C

Maßgeblich ist das nativ geprüfte Fehler-Result
`specroad-apply_Result_204821_1105_85d535.zip`, SHA-256
`e2b393a6a8a7ffc06928596e5a6c86f9da87a5fd01f08fc53ea1fbab01aac9aa`,
HEAD `2c6b308d811c1d66b8965391304ec4c63be05832` und Dirty-Fingerprint
`51ba24ec011da4e9`. 17.g.R ist nach 7832 bestandenen Tests
erfolgreich committed. Bestätigt sind 713/900 und 17.g.R. Der erfolgreiche
Klärungscommit und die erfolgreichen W-/R-Commits werden nicht wiederholt.
Die folgenden 608–610-Abschnitte bleiben historische Entscheidungs- und
Umfangsbelege; es gibt keine neue normative Klärung oder Budgetänderung.

Das C-Gate scheiterte mit einem Fehler und 7856 bestandenen Tests.
`RegistryWorkTests.test_duplicate_and_unavailable_declarations_are_rejected`
enthielt noch das Befehlsinventar vor 17.g.W. Die dort bereits implementierte
und durch 10.15.4 verlangte lesende CLI ist als merge.conflicts registriert.
Die Registry-Erwartungsmenge erhält genau diesen fehlenden Eintrag, analog
zur schon korrigierten Request-Prüfung. Der vollständige Mengenvergleich
und sämtliche Prüfungen auf doppelte oder nicht verfügbare Befehle bleiben
streng erhalten; keine Ausnahme, Teilmengenprüfung oder Handlerattrappe.

Die Suche in den vorhandenen Befehlsinventaren, Request-, Capabilities-,
Description- und Schemakatalogtests ergibt keine weitere überholte
vollständige Befehlsliste. Die Schema-ID und ausführbaren Beispielinputs
enthalten den neuen Befehl bereits. Die gesamte Registry-Testdatei wird
zusätzlich zu allen bisherigen Pflichtdateien ungefiltert ausgewählt.

Einzige verbleibende ID und Rolle: 17.g.C, implementation. Alle erhaltenen
C-Änderungen werden mit vollständigen Vorherbytes fortgeführt. Die passive
Datenmodell-/Parserextraktion bleibt unverändert und AST-gleich zum
committeten R-Verhalten; sämtliche 17.g-W-/R-Testdateien bleiben bytegleich.
Die Registry-Korrektur ergänzt einen bereits in W eingeführten Befehl und
ändert kein fachliches Ergebnis passend zum Refactoring. Produktcode,
normative Spezifikation und aktive Katalogbindungen werden nicht verändert.

Vorbereiteter Commitzielstand: 714/900, danach 17.h.W. Erst das eigene
erfolgreiche Apply-Gate mit Commit schließt 17.g ab und macht Zähler und
Checkbox wirksam. Apply führt einmal die fällige gefilterte N=3-Gruppe
plus vollständige Pflichtauswahl aus. Dev prüft nur Syntax, Collection und
native Paketbindung; kein Verhaltenstest wurde in Dev ausgeführt. 17.h–17.l,
endgültige M17-Abnahme und Produktfreigabe bleiben offen. Kein Start von
CI, Apply, Watcher oder Control, keine lokale Betriebsdaten-Payload.
