# Bundle 668 — Dauerhafter Stopp bei erschöpftem Korrekturbudget

11. November 2026. Native Quelle ist Fehler-Result 667 mit SHA-256
`fdee2ca8662f979d35bf265e6b901cf611ae8a8f311dcf86ddbebac22955df9f`,
HEAD `7de36ebcf1e4eb3b0a40d31f3a7188253ae5a2b8` und vollständig erhaltenem
Arbeitsstand. Das Gate CONTROL-DEFAULTS-666.W ergab 8764 bestandene und
einen fehlgeschlagenen Test. Kein zusätzlicher Commit entstand.

Das integrierte Szenario bestätigt nun die richtige Zählung vom initialen
Apply-Fehler bis zu fünf verbrauchten Reparaturplätzen. Beim versuchten sechsten
Aufruf wurde korrekt vor dem Modellaufruf abgebrochen; die Budget-Ausnahme
lag jedoch außerhalb der bisherigen Fehlerbehandlung und wurde durchgereicht.
Der erwartete dauerhafte Fehlerstatus fehlte.

Control behandelt genau diesen Budgetstopp vor dem Anlegen eines Versuchs:
Quellauftrag und Zähler bleiben erhalten, `correction_budget_exhausted`
wird im Ledger und Status gespeichert, `halted=true` und `again=false`
werden an den vorhandenen Worker zurückgegeben. Andere Fehler werden nicht
als Budgeterschöpfung abgefangen. Der bestehende Worker übernimmt das Pausieren.

Die W-Abnahme prüft zusätzlich den sichtbaren Stopzustand, ein fehlendes neues
Versuchsverzeichnis und einen wiederholten Aufruf ohne Verbrauch oder Modellstart.
Die R-Abnahme prüft einen echten Engine-Neustart mit geänderter Konfiguration
nach Erschöpfung; die gebundene Budgethistorie bleibt unverändert. Bestehende
Assertions und Testidentitäten bleiben erhalten. Kein Testkörper läuft in Dev.

Die ursprünglichen sechs IDs und Rollen bleiben in Reihenfolge erhalten:
CONTROL-DEFAULTS-666.W/R/C und 18.i.W/R/C. Der erfolgreiche Klärungscommit aus
Bundle 666 wird nicht wiederholt. Keine neue Klärung, keine Budgetanhebung,
kein neuer fachlicher Umfang. Die übrigen vorbereiteten Änderungen bleiben
erhalten. Jede Stage erhält einzeln ihr N=3-plus-Pflichtauswahl-Gate vor dem
Commit; erst danach darf die nächste Stage ausgebracht werden.

Vorbereitete Fortschrittswerte sind bis zum erfolgreichen Apply Zielwerte.
Dev prüft ausschließlich Syntax, reine Collection und native Paket-/Quellbindung.
Lokale Konfigurationen, Zugangsdaten und Sessionkennungen sind nicht enthalten.
Kein Dienststart oder Resume als Nebenwirkung dieser Korrektur.

Vorbereiteter Stagezustand: `CR`. Apply-Abnahme steht aus.
