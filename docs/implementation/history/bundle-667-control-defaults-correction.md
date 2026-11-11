# Bundle 667 — Korrektur und vollständiger Rest von Bundle 666

11. November 2026. Maßgeblich ist das native Fehler-Result 666 mit SHA-256
`08880f18a2354f12ba37365c44b30fb91a38957d01f369a8a2834bf972dbbd5b`.
Der Klärungscommit `REVIEW-DECISION-CONTROL-666` wurde nach 7357 bestandenen
Tests als `7de36ebcf1e4eb3b0a40d31f3a7188253ae5a2b8` erstellt und bleibt erhalten.
Das folgende Gate `CONTROL-DEFAULTS-666.W` scheiterte mit 13 fehlgeschlagenen
und 8870 bestandenen Tests; sein vollständiger Arbeitsstand ist die Vorherbasis.

Die Korrektur behebt drei Ursachen: Ein erfolgreicher initialer Bundle-Snapshot
ist kein Apply-Fehler und eröffnet daher noch keine Reparaturfolge. Erst der
erste Apply-Fehler eröffnet fünf Reparaturplätze; die folgenden fehlgeschlagenen
Reparaturen verbrauchen sie. Das bestehende integrierte Zählertestszenario prüft
nun auch den inaktiven Ausgangszähler. Die Konfigurations-Rundreise verwendet
gültige vorhandene Interpreterpfade, ohne diese auszuführen. Bootstrap und
Migration prüfen weiterhin die vollständige geschlossene Konfigurationsstruktur,
einschließlich beider neuer Optionen und ihrer erhaltenen Werte.

Offen bleiben genau `CONTROL-DEFAULTS-666.W/R/C` und `18.i.W/R/C` in der
ursprünglichen Reihenfolge und mit ursprünglichen Rollen. Die native
Korrekturbindung erhält alle sechs IDs. Kein erneuter Klärungscommit, keine
neue Spezifikationsentscheidung und kein erneuter Commit des erfolgreichen
Präfixes. Beide W/R/C-Folgen haben weiterhin echte getrennte Zustände.

Die produktiven Proposal-Reviewänderungen werden unverändert fortgeführt.
Für jedes Gate gelten die fällige N=3-Gruppe und die ungefilterte Pflichtauswahl;
der vollständige Control-Testbereich wird für die drei Control-Stufen ausgewählt.
Erst ein grünes Gate erlaubt den jeweiligen Commit und das Ausbringen der
nächsten Stage. Die vorbereiteten Plan-Zielwerte sind bis dahin keine Abnahme.

Dev führt ausschließlich Syntax-, Collection-, Quellen- und native Paketprüfung
aus. Keine Verhaltenstests in Dev, kein neuer CI-/Control-/Watcherstart und
keine lokale Konfiguration oder Sitzungskennung in der Payload.

Vorbereiteter Stagezustand: `CW`. Die Apply-Abnahme steht aus.
